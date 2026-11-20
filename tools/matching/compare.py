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
from collections import Counter
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import manifest_io  # noqa: E402
import symbols_auto  # noqa: E402
from coff import REL_FIELD_SIZE, CoffObject  # noqa: E402
from dump import DecryptedImage  # noqa: E402
from pe import REPO_ROOT, PEImage  # noqa: E402
from unwind import UNW_FLAG_CHAININFO, parse_unwind, verify_prologue  # noqa: E402

MANIFEST = REPO_ROOT / "analysis" / "functions.json"
# Bulk manifests produced by generators (e.g. tools/codegen/uht_creators.py) share the denominator.
EXTRA_MANIFESTS = "functions-*.json"
SYMBOLS = REPO_ROOT / "analysis" / "symbols.json"
# Generated symbol evidence: {symbol: {rva, evidence}} files written by analysis/codegen tools.
# Literal elimination needs every copy enumerated; content with this many copies is skipped.
ELIMINATION_LIMIT = 64
GENERATED_SYMBOLS = ("uht-creator-symbols.json", "uht-struct-symbols.json", "uht-enum-symbols.json")
SOLUTION = REPO_ROOT / "FortniteGameCode" / "FortniteGameCode.sln"
OBJ_ROOT = REPO_ROOT / "FortniteGameCode" / "Build" / "ClientShipping" / "obj"
DECRYPTED_REPORT = REPO_ROOT / "analysis" / "decrypted-reference.json"
DECRYPTED_IMAGE = REPO_ROOT / "local-output" / "reference-dump" / "FortniteClient-Win64-Shipping.decrypted.image"
DECRYPTED_PRESENT = DECRYPTED_IMAGE.with_suffix(".present")
COMPUTED = ("in_denominator", "reference_state", "match", "original_sha256", "decrypted_sha256",
            "candidate_sha256", "byte_diff", "structure", "compiler")
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

    def __init__(self, img: PEImage, dimg, manual: dict[str, tuple[int, str]]):
        self.known: dict[str, list[tuple[int, str]]] = {k: [v] for k, v in manual.items()}
        for k, lst in symbols_auto.build(img, dimg).items():
            self.known.setdefault(k, [(x["rva"], x["evidence"]) for x in lst])
        self.functions: dict[str, tuple[int, str]] = {}
        self.data_cache: dict[tuple[str, str], list[tuple[int, str]]] = {}
        self.data_notes: dict[tuple[str, str], str] = {}
        lo = symbols_auto._iat_rdata_extent(img)[1]
        exp_rva, exp_size = img.directory(0)
        self.hay_rva, self.hay = lo, img.read(lo, exp_rva + exp_size - lo)
        # Leave-one-out observations: symbol key -> {observed RVA: {manifest entry indices}},
        # and the same indexed by address: RVA -> {symbol key: {manifest entry indices}}.
        self.observations: dict = {}
        self.by_addr: dict = {}
        self.entry_names: dict[int, str] = {}

    @staticmethod
    def key(obj: CoffObject, objpath: str, symbol: str):
        """Internal-linkage symbols are only meaningful inside their own object file."""
        s = obj.symbol(symbol)
        return (objpath, symbol) if s is not None and s.storage == 3 else symbol

    def _observed(self, key, exclude: int | None) -> tuple[set[int], str]:
        vals, who, n = set(), [], 0
        for val, ents in self.observations.get(key, {}).items():
            others = ents - {exclude} if exclude in ents else ents
            if others:
                vals.add(val)
                n += len(others)
                if len(who) < 2:
                    who.extend(sorted(self.entry_names.get(i, str(i)) for i in list(others)[:2]))
        desc = ", ".join(who[:2]) + (f" and {n - len(who[:2])} more" if n > len(who[:2]) else "")
        return vals, desc

    def resolve(self, obj: CoffObject, objpath: str, symbol: str,
                exclude: int | None = None) -> list[tuple[int, str]]:
        """All independently evidenced reference addresses of `symbol` (usually one).

        `exclude` is the manifest entry under test. Observations made in that entry are
        never used to resolve its own fields.
        """
        if symbol in self.functions:
            return [self.functions[symbol]]
        if symbol in self.known:
            return self.known[symbol]
        dkey = (objpath, symbol)
        if dkey not in self.data_cache:
            rva, why = symbols_auto.resolve_data_symbol(obj, symbol, self.hay, self.hay_rva)
            self.data_cache[dkey] = [(rva, f"data symbol: {why}")] if rva is not None else []
            self.data_notes[dkey] = why
        if self.data_cache[dkey]:
            return self.data_cache[dkey]
        # Same symbol observed at one address by other relocation-equivalent-or-better functions.
        mykey = self.key(obj, objpath, symbol)
        vals, who = self._observed(mykey, exclude)
        if len(vals) == 1:
            return [(next(iter(vals)), "corroborated: same symbol at this address in " + who)]
        if len(vals) > 1:
            return []
        # Literal elimination (leave-one-out). Without /GF each use of a literal has its own
        # copy. If every copy but one is the observed target of a *different* symbol in other
        # relocation-equivalent-or-better functions, the remaining copy is this symbol's.
        lit = symbols_auto.literal_content(obj, symbol)
        if lit is not None:
            hits = symbols_auto.literal_hits(lit, self.hay, self.hay_rva, limit=ELIMINATION_LIMIT)
            if 1 < len(hits) < ELIMINATION_LIMIT:
                free, users = [], []
                for h in hits:
                    others = [k for k, ents in self.by_addr.get(h, {}).items()
                              if k != mykey and ents - {exclude}]
                    if others:
                        users.extend(self.entry_names.get(i, str(i)) for k in others
                                     for i in sorted(self.by_addr[h][k] - {exclude})[:1])
                    else:
                        free.append(h)
                if len(free) == 1:
                    return [(free[0], f"literal elimination: {len(hits)} copies, the others used by "
                                      + ", ".join(users[:2]) + (f" and {len(users) - 2} more" if len(users) > 2 else ""))]
        # Section-relative: neighbours in the object's data layout (same section name, sections
        # in object order), observed by other functions. The prediction supported by the most
        # neighbours is used if it strictly outnumbers every alternative; gaps in the layout
        # model (statics not reconstructed) then cost only the neighbours across the gap. The
        # byte comparison decides, and a failed prediction is reported as unresolved.
        sym = obj.symbol(symbol)
        if sym is None or sym.section <= 0:
            return []
        group = obj.data_layout().get(obj.sections[sym.section - 1].name)
        if not group:
            return []
        mine = next((off for name, off, _ in group if name == symbol), None)
        if mine is None:
            return []
        preds: dict[int, list[str]] = {}
        for name, off, _ in group:
            if name == symbol:
                continue
            ovals, owho = self._observed(self.key(obj, objpath, name), exclude)
            if len(ovals) == 1:
                preds.setdefault(next(iter(ovals)) + mine - off, []).append(f"{name} (seen in {owho})")
        ranked = sorted(preds.items(), key=lambda kv: -len(kv[1]))
        if ranked and (len(ranked) == 1 or len(ranked[0][1]) > len(ranked[1][1])):
            pred, basis = ranked[0]
            extra = f" and {len(basis) - 1} more neighbours" if len(basis) > 1 else ""
            dissent = sum(len(b) for _, b in ranked[1:])
            note = f" ({dissent} dissenting)" if dissent else ""
            return [(pred, "section-relative to " + basis[0] + extra + note)]
        return []

    def observe(self, idx: int, obj: CoffObject, objpath: str, relocs, cand_raw: bytes, ref: bytes,
                start: int, image_base: int) -> None:
        """Record where each relocation of entry `idx` points in the reference."""
        for r in relocs:
            size = REL_FIELD_SIZE.get(r.kind)
            if not size or r.offset + size > len(ref):
                continue
            # The compiled field holds the addend; the reference field holds the linked value.
            addend = int.from_bytes(cand_raw[r.offset:r.offset + size], "little", signed=size == 4)
            val = int.from_bytes(ref[r.offset:r.offset + size], "little", signed=size == 4)
            if r.kind == "ADDR64":
                target = val - image_base - addend
            elif r.kind == "ADDR32NB":
                target = val - addend
            elif r.kind.startswith("REL32"):
                extra = 0 if r.kind == "REL32" else int(r.kind[-1])
                target = val + start + r.offset + 4 + extra - addend
            else:
                continue
            key = self.key(obj, objpath, r.symbol)
            self.observations.setdefault(key, {}).setdefault(target, set()).add(idx)
            self.by_addr.setdefault(target, {}).setdefault(key, set()).add(idx)


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
                   obj: CoffObject, objpath: str, ref: bytes | None = None, exclude: int | None = None):
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
        targets = resolver.resolve(obj, objpath, r.symbol, exclude) if size else []
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
            if chosen[0] != ref[r.offset:r.offset + size] and chosen[2].startswith("section-relative"):
                # A layout prediction that does not reproduce the reference is missing evidence,
                # not a code difference: report the field as unresolved.
                unresolved.append((r.offset, size, r.symbol, r.kind))
                continue
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


_OBJ_CACHE: dict[str, CoffObject] = {}


def load_obj(objpath: str) -> CoffObject:
    obj = _OBJ_CACHE.get(objpath)
    if obj is None:
        obj = _OBJ_CACHE[objpath] = CoffObject(OBJ_ROOT / objpath)
    return obj


def compact_diff(diff: dict) -> dict:
    kinds = Counter(r["evidence"].split(":")[0].split(" (")[0].split(" to ")[0]
                    for r in diff.get("resolved_relocations", []))
    if diff["differing_bytes"] == 0 and not diff.get("unresolved_relocations") \
            and diff["reference_size"] == diff["candidate_size"]:
        return {"differing_bytes": 0, "resolved_by": dict(sorted(kinds.items()))}
    return {
        "reference_size": diff["reference_size"], "candidate_size": diff["candidate_size"],
        "differing_bytes": diff["differing_bytes"], "first_difference": diff.get("first_difference"),
        "resolved_relocations": len(diff.get("resolved_relocations", [])),
        "resolved_by": dict(sorted(kinds.items())),
        "unresolved_relocations": [{"offset": u["offset"], "symbol": u["symbol"]}
                                   for u in diff.get("unresolved_relocations", [])],
    }


def evaluate(idx: int, entry: dict, img: PEImage, dimg, rfmap: dict, resolver: Resolver,
             funclet_rvas: dict) -> dict:
    res: dict = {}
    compact = bool(entry.get("compact"))
    if not entry.get("object") or not entry.get("symbol"):
        res["match"] = "unimplemented"
        return res
    sources = [(entry["object"], entry["symbol"])] + [
        (s["object"], s["symbol"]) for s in entry.get("folded_sources", [])]
    start = int(entry["start_rva"], 16) if entry.get("start_rva") else None
    if start is None:
        obj = load_obj(entry["object"])
        res["compiler"] = comp_id(obj)
        cand, _ = obj.function_bytes(entry["symbol"])
        res["candidate_sha256"] = hashlib.sha256(cand).hexdigest()
        res["match"] = "unknown"
        res["reference_state"] = "not-located"
        return res
    end = int(entry["end_rva"], 16)
    ref_file = img.read(start, end - start)
    if not compact:
        res["original_sha256"] = hashlib.sha256(ref_file).hexdigest()
    rf = rfmap.get(start)
    worst = None
    order = ["exact", "relocation-equivalent", "partial", "unmatched", "unknown"]
    file_state = reference_state(img, rf, ref_file, b"")
    ref_dec = dimg.read(start, end - start) if dimg is not None and file_state != "plaintext" else None
    if ref_dec is not None and not compact:
        res["decrypted_sha256"] = hashlib.sha256(ref_dec).hexdigest()
    for objpath, symbol in sources:
        obj = load_obj(objpath)
        cand_raw, relocs = obj.function_bytes(symbol)
        ref = ref_dec if ref_dec is not None else ref_file
        cand, unresolved, resolved = resolve_fields(cand_raw, relocs, start, img.image_base,
                                                    resolver, obj, objpath, ref, idx)
        if ref_dec is not None:
            state = decrypted_state(dimg, rf, ref_file, ref_dec, cand)
        else:
            state = "plaintext" if ref_file == cand else file_state
        diff = byte_diff(ref, cand, unresolved, resolved)
        status = classify(state, diff)
        if status in ("exact", "relocation-equivalent"):
            res.setdefault("_observe", []).append((obj, objpath, relocs, cand_raw, ref, start))
        if (objpath, symbol) == sources[0]:
            if not compact:
                res["compiler"] = comp_id(obj)
            digest = hashlib.sha256(cand).hexdigest()
            res["candidate_sha256"] = digest[:16] if compact else digest
            res["reference_state"] = state
            if state in ("encrypted", "unknown"):
                res["byte_diff"] = {"reference_size": len(ref), "candidate_size": len(cand),
                                    "note": "reference body is encrypted on disk and no decrypted image is available"}
            else:
                res["byte_diff"] = compact_diff(diff) if compact else diff
            if not compact:
                st = compare_structure(img, rf, obj, symbol, start, funclet_rvas)
                if st is not None:
                    st["pdata_size_matches"] = len(cand) == end - start
                    res["structure"] = st
        if worst is None or order.index(status) > order.index(worst):
            worst = status
    res["match"] = worst
    return res


def load_manual_symbols() -> dict[str, tuple[int, str]]:
    manual: dict[str, tuple[int, str]] = {}
    if SYMBOLS.exists():
        for k, v in json.loads(SYMBOLS.read_text(encoding="utf-8")).get("symbols", {}).items():
            manual[k] = (int(v["rva"], 16), v.get("evidence", "analysis/symbols.json"))
    for name in GENERATED_SYMBOLS:
        path = REPO_ROOT / "analysis" / name
        if path.exists():
            doc = json.loads(path.read_text(encoding="utf-8"))
            codes = doc.get("evidence_codes", {})
            for k, v in doc.get("symbols", {}).items():
                rva, ev = (v["rva"], v["evidence"]) if isinstance(v, dict) else (v[0], codes.get(v[1], v[1]))
                manual.setdefault(k, (int(rva, 16), f"{name}: {ev}"))
    return manual


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="print a summary instead of every entry")
    args = ap.parse_args()
    if args.build:
        import msvc
        r = msvc.build_solution(SOLUTION)
        print(r.stdout[-3000:])
        if r.returncode:
            return r.returncode
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    extra = [(p, json.loads(p.read_text(encoding="utf-8")))
             for p in sorted((REPO_ROOT / "analysis").glob(EXTRA_MANIFESTS))]
    entries = list(manifest["functions"])
    owner = [MANIFEST] * len(entries)
    for p, m in extra:
        entries += manifest_io.expand(m)
        owner += [p] * len(m["functions"])
    img = PEImage()
    if img.sha256() != manifest["reference"]["sha256"]:
        print("reference SHA-256 differs from manifest", file=sys.stderr)
        return 2
    dimg = load_decrypted(img)
    resolver = Resolver(img, dimg, load_manual_symbols())
    rfs = img.runtime_functions()
    rfmap = {rf.begin: rf for rf in rfs}
    text = img.sections[0]
    primary_set = {rf.begin for rf in rfs if text.contains_rva(rf.begin)
                   and not parse_unwind(img, rf.unwind).flags & UNW_FLAG_CHAININFO}
    primary = len(primary_set)
    funclet_rvas = {}
    for e in entries:
        if e.get("start_rva") and e.get("symbol"):
            funclet_rvas[e["symbol"]] = int(e["start_rva"], 16)
            for s in e.get("folded_sources", []):
                funclet_rvas[s["symbol"]] = int(e["start_rva"], 16)

    # Entries verified against the decrypted image can only be re-checked where it exists.
    skip = {i for i, e in enumerate(entries)
            if dimg is None and e.get("reference_state") in DECRYPTED_STATES}
    if dimg is None:
        for i in skip:  # their recorded exact matches still resolve callers
            e = entries[i]
            if e.get("match") == "exact":
                resolver.functions[e["symbol"]] = (int(e["start_rva"], 16),
                                                   f"recorded exact match of manifest entry {e['start_rva']}")

    # Evaluate to a fixpoint. An exact function's symbol may resolve its callers' relocations,
    # and relocation-equivalent-or-better functions contribute observations that resolve
    # *other* entries' fields (leave-one-out). Observations are gathered between passes only.
    for i, e in enumerate(entries):
        resolver.entry_names[i] = e["name"]

    def snapshot() -> int:
        return hash(frozenset((repr(k), v, frozenset(ents))
                              for k, d in resolver.observations.items() for v, ents in d.items()))

    results: dict = {}
    for _ in range(32):
        results = {i: evaluate(i, e, img, dimg, rfmap, resolver, funclet_rvas)
                   for i, e in enumerate(entries) if i not in skip}
        for i, res in results.items():
            e = entries[i]
            res["in_denominator"] = bool(e.get("start_rva")) and int(e["start_rva"], 16) in primary_set
        before = snapshot()
        resolver.observations = {}
        resolver.by_addr = {}
        for i, res in results.items():
            for obj, objpath, relocs, cand_raw, ref, start in res.pop("_observe", []):
                resolver.observe(i, obj, objpath, relocs, cand_raw, ref, start, img.image_base)
        added = before != snapshot()
        for i, res in results.items():
            e = entries[i]
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
        e = entries[i]
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
    if args.quiet:
        for path in [MANIFEST] + [p for p, _ in extra]:
            st = Counter(e.get("match") for e, o in zip(entries, owner) if o == path)
            print(f"{path.name}: {dict(sorted(st.items()))}")
    else:
        for e in entries:
            print(f"{e.get('start_rva') or '(unlocated)':>12}  {e.get('match', '?'):22} "
                  f"{e.get('reference_state', '-'):21} {e['name']}")
    if skip:
        print(f"note: {len(skip)} entries verified against the decrypted image were not re-checked "
              "(local decrypted image not present)")
    if args.check:
        if stale:
            print(f"stale manifest fields ({len(stale)}):", stale[:20], file=sys.stderr)
            return 1
        print("manifest up to date")
        return 0
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for p, m in extra:
        manifest_io.strip(m)
        manifest_io.dump_compact(p, m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
