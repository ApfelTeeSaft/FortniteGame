"""Compare recovered functions with the reference image and record verified results.

For every analysis/functions.json entry that names an object file and symbol:

* raw bytes of the compiled function are compared with the reference bytes over the
  manifest range [start_rva, end_rva). A relocation field counts only when its symbol
  resolves through evidence independent of the bytes under test. Allowed sources are
  analysis/symbols.json, import tables, unique import thunks, unique data content
  (symbols_auto.py), or another function already matched exactly (iterated to a fixpoint).
  Unresolved fields are never treated as equal; a function that matches apart from them is
  ``relocation-equivalent``, not ``exact``;
* reference bytes come from the original file where they are plaintext on disk. Otherwise
  they come from the validated decrypted image (ingest_dump.py, local only), giving
  reference_state ``decrypted``. Without either, encrypted bodies are ``unknown``;
* the compiled unwind record and C scope table are compared with the reference
  records in plaintext .rdata. Scope entries are compared as offsets from the
  function start, and the handler RVA is reported, never assumed.

Usage:
  python tools/matching/compare.py [--build] [--check]
    --build   rebuild FortniteGameCode.sln (ClientShipping|x64) first
    --check   do not write; exit 1 if the manifest's recorded results are stale
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import symbols_auto  # noqa: E402
from coff import REL_FIELD_SIZE, CoffObject  # noqa: E402
from dump import DecryptedImage  # noqa: E402
from pe import REPO_ROOT, PEImage  # noqa: E402
from unwind import UNW_FLAG_CHAININFO, parse_unwind, verify_prologue  # noqa: E402

MANIFEST = REPO_ROOT / "analysis" / "functions.json"
SYMBOLS = REPO_ROOT / "analysis" / "symbols.json"
SOLUTION = REPO_ROOT / "FortniteGameCode" / "FortniteGameCode.sln"
OBJ_ROOT = REPO_ROOT / "FortniteGameCode" / "Build" / "ClientShipping" / "obj"
DECRYPTED_REPORT = REPO_ROOT / "analysis" / "decrypted-reference.json"
DECRYPTED_IMAGE = REPO_ROOT / "local-output" / "reference-dump" / "FortniteClient-Win64-Shipping.decrypted.image"
DECRYPTED_PRESENT = DECRYPTED_IMAGE.with_suffix(".present")
COMPUTED = ("reference_state", "match", "original_sha256", "decrypted_sha256", "candidate_sha256",
            "byte_diff", "structure", "compiler")
DECRYPTED_STATES = ("decrypted", "decrypted-unverified")


def hx(v: int) -> str:
    return f"0x{v:08X}"


def comp_id(obj: CoffObject) -> str | None:
    for s in obj.symbols:
        if s is not None and s.name == "@comp.id":
            return f"prodid {s.value >> 16} build {s.value & 0xFFFF}"
    return None


def load_decrypted(img: PEImage) -> DecryptedImage | None:
    if not DECRYPTED_REPORT.exists() or not DECRYPTED_IMAGE.exists():
        return None
    report = json.loads(DECRYPTED_REPORT.read_text(encoding="utf-8"))
    data = DECRYPTED_IMAGE.read_bytes()
    if (not report["validation"]["accepted"]
            or hashlib.sha256(data).hexdigest() != report["normalized_image"]["sha256"]):
        print("decrypted image not validated or hash mismatch; ignoring it", file=sys.stderr)
        return None
    present = DECRYPTED_PRESENT.read_bytes() if DECRYPTED_PRESENT.exists() else None
    return DecryptedImage(img, data, present)


class Resolver:
    """Symbol -> reference RVA, each with the evidence that established it."""

    def __init__(self, img: PEImage, dimg, manual: dict[str, int]):
        self.known: dict[str, list[tuple[int, str]]] = {
            k: [(v, "analysis/symbols.json")] for k, v in manual.items()}
        for k, lst in symbols_auto.build(img, dimg).items():
            self.known.setdefault(k, [(x["rva"], x["evidence"]) for x in lst])
        self.functions: dict[str, tuple[int, str]] = {}
        self.data_cache: dict[tuple[str, str], list[tuple[int, str]]] = {}
        self.data_notes: dict[tuple[str, str], str] = {}
        lo = symbols_auto._iat_rdata_extent(img)[1]
        exp_rva, exp_size = img.directory(0)
        self.hay_rva, self.hay = lo, img.read(lo, exp_rva + exp_size - lo)

    def resolve(self, obj: CoffObject, objpath: str, symbol: str) -> list[tuple[int, str]]:
        """All independently evidenced reference addresses of `symbol` (usually one)."""
        if symbol in self.functions:
            return [self.functions[symbol]]
        if symbol in self.known:
            return self.known[symbol]
        key = (objpath, symbol)
        if key not in self.data_cache:
            rva, why = symbols_auto.resolve_data_symbol(obj, symbol, self.hay, self.hay_rva)
            self.data_cache[key] = [(rva, f"data symbol: {why}")] if rva is not None else []
            self.data_notes[key] = why
        return self.data_cache[key]


def reference_state(img: PEImage, rf, ref: bytes, cand: bytes) -> str:
    if ref == cand:
        return "plaintext"
    if rf is None:
        return "unknown"
    verdict, _ = verify_prologue(img, rf.begin, parse_unwind(img, rf.unwind))
    return {"verified": "plaintext", "mismatch": "encrypted",
            "undecodable": "encrypted"}.get(verdict, "unknown")


def decrypted_state(dimg, rf, ref_file: bytes, ref_dec: bytes, cand: bytes) -> str:
    if ref_dec == cand:
        return "decrypted"
    if ref_dec == ref_file:
        return "encrypted"
    if rf is None:
        return "decrypted-unverified"
    verdict, _ = verify_prologue(dimg, rf.begin, parse_unwind(dimg.original, rf.unwind))
    return "decrypted" if verdict in ("verified", "no-codes") else "decrypted-unverified"


def _field_value(kind: str, target: int, addend: int, start: int, offset: int, image_base: int) -> int | None:
    if kind == "ADDR64":
        return image_base + target + addend
    if kind == "ADDR32NB":
        return target + addend
    if kind.startswith("REL32"):
        extra = 0 if kind == "REL32" else int(kind[-1])
        return target + addend - (start + offset + 4 + extra)
    return None


def resolve_fields(cand: bytes, relocs, start: int, image_base: int, resolver: Resolver,
                   obj: CoffObject, objpath: str, ref: bytes | None = None):
    """Apply resolvable relocations as the linker would at the original placement.

    When a symbol has several independently evidenced addresses (an import with both an
    original and a protector IAT slot), the one whose field equals the reference is used.
    The choice and its evidence are recorded. Any field that no candidate can produce stays
    a byte difference.
    """
    buf = bytearray(cand)
    unresolved, resolved = [], []
    for r in relocs:
        size = REL_FIELD_SIZE.get(r.kind)
        targets = resolver.resolve(obj, objpath, r.symbol) if size else []
        if not targets:
            unresolved.append((r.offset, size or 4, r.symbol, r.kind))
            continue
        addend = int.from_bytes(cand[r.offset:r.offset + size], "little", signed=size == 4)
        options = []
        for target, via in targets:
            val = _field_value(r.kind, target, addend, start, r.offset, image_base)
            if val is not None:
                options.append(((val & ((1 << (8 * size)) - 1)).to_bytes(size, "little"), target, via))
        if not options:
            unresolved.append((r.offset, size, r.symbol, r.kind))
            continue
        chosen = options[0]
        if ref is not None:
            chosen = next((o for o in options if o[0] == ref[r.offset:r.offset + size]), chosen)
        buf[r.offset:r.offset + size] = chosen[0]
        resolved.append({"offset": hx(r.offset), "symbol": r.symbol, "rva": hx(chosen[1]), "evidence": chosen[2]})
    return bytes(buf), unresolved, resolved


def byte_diff(ref: bytes, cand: bytes, unresolved, resolved=()) -> dict:
    masked = set()
    for off, size, _, _ in unresolved:
        masked.update(range(off, off + size))
    n = min(len(ref), len(cand))
    diffs = [i for i in range(n) if ref[i] != cand[i] and i not in masked]
    masked_diff = [i for i in sorted(masked) if i < n and ref[i] != cand[i]]
    return {
        "reference_size": len(ref),
        "candidate_size": len(cand),
        "differing_bytes": len(diffs) + abs(len(ref) - len(cand)),
        "first_difference": hx(diffs[0]) if diffs else None,
        "resolved_relocations": list(resolved),
        "unresolved_relocations": [
            {"offset": hx(o), "size": s, "symbol": sym, "kind": k} for o, s, sym, k in unresolved],
        "bytes_differing_only_in_unresolved_fields": len(masked_diff),
    }


def classify(state: str, diff: dict) -> str:
    if state in ("encrypted", "unknown"):
        return "unknown"
    same_size = diff["reference_size"] == diff["candidate_size"]
    if same_size and diff["differing_bytes"] == 0:
        return "exact" if not diff["unresolved_relocations"] else "relocation-equivalent"
    return "partial" if diff["differing_bytes"] < diff["reference_size"] else "unmatched"


def obj_unwind(obj: CoffObject, symbol: str):
    """Locate the compiled UNWIND_INFO for `symbol` via the object's .pdata relocations."""
    for sec in obj.sections:
        if sec.name != ".pdata":
            continue
        by_off = {r.offset: r for r in sec.relocs}
        for base in range(0, len(sec.data), 12):
            r0, r8 = by_off.get(base), by_off.get(base + 8)
            if r0 is None or r8 is None or r0.symbol != symbol:
                continue
            for sym in obj.symbols:
                if sym is not None and sym.name == r8.symbol and sym.section > 0:
                    xsec = obj.sections[sym.section - 1]
                    add = struct.unpack_from("<I", sec.data, base + 8)[0]
                    return xsec, sym.value + add
    return None


def compare_structure(img: PEImage, rf, obj: CoffObject, symbol: str, start: int,
                      funclet_rvas: dict[str, int]) -> dict | None:
    loc = obj_unwind(obj, symbol)
    if loc is None or rf is None:
        return None
    xsec, xoff = loc
    d = xsec.data
    count = d[xoff + 2]
    hdr_len = 4 + 2 * count
    ref_ui = img.read(rf.unwind, hdr_len)
    # pdata_size_matches is filled in by the caller, which knows the candidate size.
    out = {"pdata_size_matches": None, "unwind_codes_identical": d[xoff:xoff + hdr_len] == ref_ui}
    flags = d[xoff] >> 3
    tail = xoff + 4 + 2 * (count + (count & 1))
    if flags & UNW_FLAG_CHAININFO or not flags & 3:
        return out
    rel = {r.offset: r for r in xsec.relocs}
    ref_tail = rf.unwind + 4 + 2 * (count + (count & 1))
    hsym = rel.get(tail)
    out["handler"] = {"candidate_symbol": hsym.symbol if hsym else None,
                      "reference_rva": hx(img.u32(ref_tail)),
                      "status": "unresolved-relocation (reported, not compared)"}
    if hsym is None or hsym.symbol not in ("__C_specific_handler",):
        return out
    n = struct.unpack_from("<I", d, tail + 4)[0]
    ref_n = img.u32(ref_tail + 4)
    entries, ok = [], n == ref_n
    for i in range(min(n, ref_n)):
        fo = tail + 8 + 16 * i
        cand_vals = struct.unpack_from("<IIII", d, fo)
        ref_vals = struct.unpack_from("<IIII", img.read(ref_tail + 8 + 16 * i, 16))
        e = {}
        for j, name in enumerate(("begin", "end", "handler", "target")):
            r = rel.get(fo + 4 * j)
            if r is None:  # absolute value, e.g. EXCEPTION_EXECUTE_HANDLER (1)
                e[name] = {"candidate": cand_vals[j], "reference": ref_vals[j],
                           "equal": cand_vals[j] == ref_vals[j]}
            elif r.symbol == symbol:
                c_off, r_off = cand_vals[j], ref_vals[j] - start
                e[name] = {"candidate_offset": hx(c_off), "reference_offset": hx(r_off),
                           "equal": c_off == r_off}
            else:
                want = funclet_rvas.get(r.symbol)
                e[name] = {"candidate_symbol": r.symbol, "reference_rva": hx(ref_vals[j]),
                           "resolves_to_manifest_rva": hx(want) if want is not None else None,
                           "equal": want is not None and want + cand_vals[j] == ref_vals[j]}
            ok = ok and e[name]["equal"]
        entries.append(e)
    out["scope_table"] = {"count_candidate": n, "count_reference": ref_n,
                          "identical": ok, "entries": entries}
    return out


def evaluate(entry: dict, img: PEImage, dimg, rfmap: dict, resolver: Resolver,
             funclet_rvas: dict) -> dict:
    res: dict = {}
    if not entry.get("object") or not entry.get("symbol"):
        res["match"] = "unimplemented"
        return res
    sources = [(entry["object"], entry["symbol"])] + [
        (s["object"], s["symbol"]) for s in entry.get("folded_sources", [])]
    start = int(entry["start_rva"], 16) if entry.get("start_rva") else None
    if start is None:
        obj = CoffObject(OBJ_ROOT / entry["object"])
        res["compiler"] = comp_id(obj)
        cand, _ = obj.function_bytes(entry["symbol"])
        res["candidate_sha256"] = hashlib.sha256(cand).hexdigest()
        res["match"] = "unknown"
        res["reference_state"] = "not-located"
        return res
    end = int(entry["end_rva"], 16)
    ref_file = img.read(start, end - start)
    res["original_sha256"] = hashlib.sha256(ref_file).hexdigest()
    rf = rfmap.get(start)
    worst = None
    order = ["exact", "relocation-equivalent", "partial", "unmatched", "unknown"]
    file_state = reference_state(img, rf, ref_file, b"")
    ref_dec = dimg.read(start, end - start) if dimg is not None and file_state != "plaintext" else None
    if ref_dec is not None:
        res["decrypted_sha256"] = hashlib.sha256(ref_dec).hexdigest()
    for objpath, symbol in sources:
        obj = CoffObject(OBJ_ROOT / objpath)
        cand_raw, relocs = obj.function_bytes(symbol)
        ref = ref_dec if ref_dec is not None else ref_file
        cand, unresolved, resolved = resolve_fields(cand_raw, relocs, start, img.image_base,
                                                    resolver, obj, objpath, ref)
        if ref_dec is not None:
            state = decrypted_state(dimg, rf, ref_file, ref_dec, cand)
        else:
            state = "plaintext" if ref_file == cand else file_state
        diff = byte_diff(ref, cand, unresolved, resolved)
        status = classify(state, diff)
        if (objpath, symbol) == sources[0]:
            res["compiler"] = comp_id(obj)
            res["candidate_sha256"] = hashlib.sha256(cand).hexdigest()
            res["reference_state"] = state
            res["byte_diff"] = diff if state not in ("encrypted", "unknown") else {
                "reference_size": len(ref), "candidate_size": len(cand),
                "note": "reference body is encrypted on disk and no decrypted image is available"}
            st = compare_structure(img, rf, obj, symbol, start, funclet_rvas)
            if st is not None:
                st["pdata_size_matches"] = len(cand) == end - start
                res["structure"] = st
        if worst is None or order.index(status) > order.index(worst):
            worst = status
    res["match"] = worst
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.build:
        import msvc
        r = msvc.build_solution(SOLUTION)
        print(r.stdout[-3000:])
        if r.returncode:
            return r.returncode
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    symbols = json.loads(SYMBOLS.read_text(encoding="utf-8")) if SYMBOLS.exists() else {"symbols": {}}
    manual = {k: int(v["rva"], 16) for k, v in symbols.get("symbols", {}).items()}
    img = PEImage()
    if img.sha256() != manifest["reference"]["sha256"]:
        print("reference SHA-256 differs from manifest", file=sys.stderr)
        return 2
    dimg = load_decrypted(img)
    resolver = Resolver(img, dimg, manual)
    rfs = img.runtime_functions()
    rfmap = {rf.begin: rf for rf in rfs}
    text = img.sections[0]
    primary = sum(1 for rf in rfs if text.contains_rva(rf.begin)
                  and not parse_unwind(img, rf.unwind).flags & UNW_FLAG_CHAININFO)
    funclet_rvas = {}
    for e in manifest["functions"]:
        if e.get("start_rva") and e.get("symbol"):
            funclet_rvas[e["symbol"]] = int(e["start_rva"], 16)
            for s in e.get("folded_sources", []):
                funclet_rvas[s["symbol"]] = int(e["start_rva"], 16)

    # Entries verified against the decrypted image can only be re-checked where it exists.
    skip = {i for i, e in enumerate(manifest["functions"])
            if dimg is None and e.get("reference_state") in DECRYPTED_STATES}
    if dimg is None:
        for i in skip:  # their recorded exact matches still resolve callers
            e = manifest["functions"][i]
            if e.get("match") == "exact":
                resolver.functions[e["symbol"]] = (int(e["start_rva"], 16),
                                                   f"recorded exact match of manifest entry {e['start_rva']}")

    # Evaluate to a fixpoint: an exact function's symbol may resolve its callers' relocations.
    for _ in range(32):
        results = {i: evaluate(e, img, dimg, rfmap, resolver, funclet_rvas)
                   for i, e in enumerate(manifest["functions"]) if i not in skip}
        added = False
        for i, res in results.items():
            e = manifest["functions"][i]
            if res.get("match") == "exact" and e.get("start_rva"):
                for sym in [e["symbol"]] + [s["symbol"] for s in e.get("folded_sources", [])]:
                    if sym not in resolver.functions:
                        resolver.functions[sym] = (int(e["start_rva"], 16),
                                                   f"exact match of manifest entry {e['start_rva']}")
                        added = True
        if not added:
            break

    stale = []
    for i, res in results.items():
        e = manifest["functions"][i]
        for k in COMPUTED:
            if e.get(k) != res.get(k):
                stale.append((e.get("start_rva") or e.get("name"), k))
            if k in res:
                e[k] = res[k]
            else:
                e.pop(k, None)
    denom = manifest["denominator"]
    if denom.get("count") != primary:
        stale.append(("denominator", "count"))
    denom["count"] = primary
    for e in manifest["functions"]:
        print(f"{e.get('start_rva') or '(unlocated)':>12}  {e.get('match', '?'):22} "
              f"{e.get('reference_state', '-'):21} {e['name']}")
    if skip:
        print(f"note: {len(skip)} entries verified against the decrypted image were not re-checked "
              "(local decrypted image not present)")
    if args.check:
        if stale:
            print("stale manifest fields:", stale, file=sys.stderr)
            return 1
        print("manifest up to date")
        return 0
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
