"""Compare recovered functions with the reference image and record verified results.

For every analysis/functions.json entry that names an object file and symbol:

* raw bytes of the compiled function are compared with the reference bytes over the
  manifest range [start_rva, end_rva). Relocation fields are resolved only through
  analysis/symbols.json; unresolved fields are never treated as equal, so a function
  that matches apart from them is ``relocation-equivalent``, not ``exact``;
* the reference range is classified as plaintext or encrypted on disk (prologue vs.
  unwind record, see survey.py). Encrypted bodies cannot be compared, so their match
  state is ``unknown`` however good the structural evidence;
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
from coff import REL_FIELD_SIZE, CoffObject  # noqa: E402
from pe import REPO_ROOT, PEImage  # noqa: E402
from unwind import UNW_FLAG_CHAININFO, parse_unwind, verify_prologue  # noqa: E402

MANIFEST = REPO_ROOT / "analysis" / "functions.json"
SYMBOLS = REPO_ROOT / "analysis" / "symbols.json"
SOLUTION = REPO_ROOT / "FortniteGameCode" / "FortniteGameCode.sln"
OBJ_ROOT = REPO_ROOT / "FortniteGameCode" / "Build" / "ClientShipping" / "obj"
COMPUTED = ("reference_state", "match", "original_sha256", "candidate_sha256",
            "byte_diff", "structure", "compiler")


def hx(v: int) -> str:
    return f"0x{v:08X}"


def comp_id(obj: CoffObject) -> str | None:
    for s in obj.symbols:
        if s is not None and s.name == "@comp.id":
            return f"prodid {s.value >> 16} build {s.value & 0xFFFF}"
    return None


def reference_state(img: PEImage, rf, ref: bytes, cand: bytes) -> str:
    if ref == cand:
        return "plaintext"
    if rf is None:
        return "unknown"
    verdict, _ = verify_prologue(img, rf.begin, parse_unwind(img, rf.unwind))
    return {"verified": "plaintext", "mismatch": "encrypted",
            "undecodable": "encrypted"}.get(verdict, "unknown")


def resolve_fields(cand: bytes, relocs, start: int, image_base: int, symmap: dict[str, int]):
    """Apply resolvable relocations as the linker would at the original placement."""
    buf = bytearray(cand)
    unresolved = []
    for r in relocs:
        size = REL_FIELD_SIZE.get(r.kind)
        if size is None:
            unresolved.append((r.offset, 4, r.symbol, r.kind))
            continue
        target = symmap.get(r.symbol)
        if target is None:
            unresolved.append((r.offset, size, r.symbol, r.kind))
            continue
        field = int.from_bytes(buf[r.offset:r.offset + size], "little", signed=size == 4)
        if r.kind == "ADDR64":
            val = image_base + target + field
        elif r.kind in ("ADDR32NB",):
            val = target + field
        elif r.kind.startswith("REL32"):
            extra = 0 if r.kind == "REL32" else int(r.kind[-1])
            val = target + field - (start + r.offset + 4 + extra)
        else:
            unresolved.append((r.offset, size, r.symbol, r.kind))
            continue
        buf[r.offset:r.offset + size] = (val & ((1 << (8 * size)) - 1)).to_bytes(size, "little")
    return bytes(buf), unresolved


def byte_diff(ref: bytes, cand: bytes, unresolved) -> dict:
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
        "unresolved_relocations": [
            {"offset": hx(o), "size": s, "symbol": sym, "kind": k} for o, s, sym, k in unresolved],
        "bytes_differing_only_in_unresolved_fields": len(masked_diff),
    }


def classify(state: str, diff: dict) -> str:
    if state == "encrypted":
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


def evaluate(entry: dict, img: PEImage, rfmap: dict, symmap: dict, funclet_rvas: dict) -> dict:
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
    ref = img.read(start, end - start)
    res["original_sha256"] = hashlib.sha256(ref).hexdigest()
    rf = rfmap.get(start)
    worst = None
    order = ["exact", "relocation-equivalent", "partial", "unmatched", "unknown"]
    for objpath, symbol in sources:
        obj = CoffObject(OBJ_ROOT / objpath)
        cand_raw, relocs = obj.function_bytes(symbol)
        cand, unresolved = resolve_fields(cand_raw, relocs, start, img.image_base, symmap)
        state = reference_state(img, rf, ref, cand)
        diff = byte_diff(ref, cand, unresolved)
        status = classify(state, diff)
        if (objpath, symbol) == sources[0]:
            res["compiler"] = comp_id(obj)
            res["candidate_sha256"] = hashlib.sha256(cand).hexdigest()
            res["reference_state"] = state
            res["byte_diff"] = diff if state != "encrypted" else {
                "reference_size": len(ref), "candidate_size": len(cand),
                "note": "reference body is encrypted on disk; bytes not comparable"}
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
    symmap = {k: int(v["rva"], 16) for k, v in symbols.get("symbols", {}).items()}
    img = PEImage()
    if img.sha256() != manifest["reference"]["sha256"]:
        print("reference SHA-256 differs from manifest", file=sys.stderr)
        return 2
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
    stale = []
    for e in manifest["functions"]:
        res = evaluate(e, img, rfmap, symmap, funclet_rvas)
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
              f"{e.get('reference_state', '-'):11} {e['name']}")
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
