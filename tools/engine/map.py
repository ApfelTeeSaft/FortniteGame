"""Map compiled engine functions to the reference and write their manifests.

For every function of a module's objects (tools/engine/build.py), locate.PdataIndex lists the
reference's primary .pdata functions of the same length whose bytes are identical outside the
function's relocation fields. Each function is classified:

- unique: one such function. Proposed at its address.
- ambiguous: several. The relocations decide where they can: a hit stays a candidate only if
  every relocation whose target is independently known (an import slot, a literal or data
  block found by content, a function already in a manifest; compare.Resolver without
  observations) points there in the reference. Exactly one remaining candidate is proposed;
  otherwise the function stays ambiguous and is not proposed.
- none: no function of that length matches. Not proposed.

Addresses an existing manifest already holds are skipped, so the repository's reconstructions
and UHT code keep their entries; so are addresses claimed twice within a module (one name per
address, the first by name: /OPT:ICF folds identical bodies). A proposal is not a match:
compare.py resolves every relocation and decides exact, relocation-equivalent or not.

Writes analysis/functions-engine-<Module>.json (compact) and prints the classification.
Usage:

    python tools/engine/map.py Core [CoreUObject ...] | --all
"""
from __future__ import annotations

import argparse
import json
import pickle
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "matching"))
import build as B  # noqa: E402
import ue_target as T  # noqa: E402
from coff import REL_FIELD_SIZE, CoffObject  # noqa: E402
from locate import PdataIndex, masked  # noqa: E402
from manifest_io import dump_compact, expand  # noqa: E402

ANALYSIS = T.ROOT / "analysis"
INDEX_CACHE = T.BUILD_DIR / "pdata-index.pickle"
MIN_BYTES = 6   # shorter bodies (a ret, a jmp) say nothing about which function they are


def load_index(img, dimg) -> PdataIndex:
    if INDEX_CACHE.exists():
        return pickle.loads(INDEX_CACHE.read_bytes())
    ix = PdataIndex(img, dimg)
    INDEX_CACHE.write_bytes(pickle.dumps(ix))
    return ix


def claimed(exclude_module: str | None) -> dict[int, str]:
    """Start RVA -> manifest of every entry outside this module's own engine manifest."""
    out = {}
    own = f"functions-engine-{exclude_module}.json" if exclude_module else None
    for p in [ANALYSIS / "functions.json"] + sorted(ANALYSIS.glob("functions-*.json")):
        if p.name == own:
            continue
        m = json.loads(p.read_text(encoding="utf-8"))
        for e in (expand(m) if p.name != "functions.json" else m["functions"]):
            if e.get("start_rva"):
                out[int(e["start_rva"], 16)] = p.name
    return out


def known_functions() -> dict[str, int]:
    """Symbol -> RVA of every exact manifest entry (independent evidence for call targets)."""
    out = {}
    for p in [ANALYSIS / "functions.json"] + sorted(ANALYSIS.glob("functions-*.json")):
        m = json.loads(p.read_text(encoding="utf-8"))
        for e in (expand(m) if p.name != "functions.json" else m["functions"]):
            if e.get("match") == "exact" and e.get("symbol") and e.get("start_rva"):
                out[e["symbol"]] = int(e["start_rva"], 16)
    return out


def ref_target(kind: str, cand: bytes, ref: bytes, off: int, start: int, image_base: int) -> int | None:
    """Where a relocation field points in the reference (compare.Resolver.observe)."""
    size = REL_FIELD_SIZE.get(kind)
    if not size or off + size > len(ref):
        return None
    addend = int.from_bytes(cand[off:off + size], "little", signed=size == 4)
    val = int.from_bytes(ref[off:off + size], "little", signed=size == 4)
    if kind == "ADDR64":
        return val - image_base - addend
    if kind == "ADDR32NB":
        return val - addend
    if kind.startswith("REL32"):
        extra = 0 if kind == "REL32" else int(kind[-1])
        return val + start + off + 4 + extra - addend
    return None


_DATA_CACHE: dict = {}


def independent_targets(resolver, obj, objpath: str, symbol: str) -> set[int]:
    """Addresses of a symbol known without any observation: an import slot or other symbol
    compare.Resolver knows, or a literal or data block unique by content (symbols_auto)."""
    if symbol in resolver.known:
        return {rva for rva, _ in resolver.known[symbol]}
    key = (objpath, symbol)
    if key not in _DATA_CACHE:
        import symbols_auto
        rva, _ = symbols_auto.resolve_data_symbol(obj, symbol, resolver.hay, resolver.hay_rva,
                                                  resolver.data_hay, resolver.data_rva)
        _DATA_CACHE[key] = {rva} if rva is not None else set()
    return _DATA_CACHE[key]


def literal_agrees(obj, symbol: str, target: int, dimg) -> bool | None:
    """Does the reference hold the string literal's text where the relocation points? None if
    the symbol is not a string literal."""
    if not symbol.startswith(("$SG", "??_C@")):
        return None
    import symbols_auto
    lit = symbols_auto.literal_content(obj, symbol)
    if lit is None:
        return None
    return dimg.read(target, len(lit)) == lit


def absent_literal(resolver, obj, symbol: str) -> bool:
    """Is the symbol a string literal whose text the reference's data does not contain?"""
    if not symbol.startswith(("$SG", "??_C@")):
        return False
    import symbols_auto
    lit = symbols_auto.literal_content(obj, symbol)
    return lit is not None and not symbols_auto.literal_hits(lit, resolver.hay, resolver.hay_rva, limit=1)


def evidence(obj, objpath, name, rva, resolver, functions, proposed, observed, dimg, image_base,
             elsewhere=frozenset()) -> tuple[int, int]:
    """(-disagreeing, agreeing) relocation targets of a function placed at rva: against the
    independently known targets, else against what the module's uniquely placed functions
    see in the reference (observed: symbol -> targets). A symbol in elsewhere lost its
    proposed address to another: a target there disagrees."""
    raw, relocs = obj.function_bytes(name)
    ref = dimg.read(rva, len(raw))
    agree = disagree = 0
    for r in relocs:
        t = ref_target(r.kind, raw, ref, r.offset, rva, image_base)
        if t is None:
            continue
        if r.symbol in elsewhere:
            disagree += t == proposed[r.symbol]
            continue
        lit = literal_agrees(obj, r.symbol, t, dimg)
        if lit is not None:
            agree += lit
            disagree += not lit
            continue
        if r.symbol in functions:
            exp = {functions[r.symbol]}
        elif r.symbol in proposed and r.symbol != name:
            exp = {proposed[r.symbol]}
        else:
            exp = independent_targets(resolver, obj, objpath, r.symbol) or observed.get(r.symbol, set())
        if exp:
            agree += t in exp
            disagree += t not in exp
    return -disagree, agree


def disambiguate(obj, objpath, name, hits, resolver, functions, proposed, dimg, image_base):
    """The one hit every independently known relocation target agrees with, if exactly one."""
    raw, relocs = obj.function_bytes(name)
    keep = []
    for h in hits:
        ref = dimg.read(h, len(raw))
        ok, evidence = True, 0
        for r in relocs:
            t = ref_target(r.kind, raw, ref, r.offset, h, image_base)
            if t is None:
                continue
            if r.symbol in functions:
                exp = {functions[r.symbol]}
            elif r.symbol in proposed:
                exp = {proposed[r.symbol]}
            else:
                exp = independent_targets(resolver, obj, objpath, r.symbol)
            if not exp:
                continue
            if t in exp:
                evidence += 1
            else:
                ok = False
                break
        if ok and evidence:
            keep.append(h)
    return keep[0] if len(keep) == 1 else None


_UNDNAME = None


def demangle(symbols: list[str]) -> dict[str, str]:
    """Readable names through undname.exe (v140), in batches."""
    env = B.vc_environment()
    exe = B.cl_path(env).replace("cl.exe", "undname.exe")
    out, batch, size = {}, [], 0
    for s in symbols + [None]:
        if s is not None and size + len(s) < 24000:
            batch.append(s)
            size += len(s) + 3
            continue
        if batch:
            r = subprocess.run([exe] + batch, capture_output=True, text=True, errors="replace", env=env)
            names = re.findall(r'is :- "(.*)"', r.stdout)
            for b, n in zip(batch, names if len(names) == len(batch) else batch):
                out[b] = compact_name(n)
        batch, size = ([s], len(s) + 3) if s is not None else ([], 0)
    return out


def compact_name(undecorated: str) -> str:
    """'public: int __cdecl FString::Find(...)const __ptr64' -> 'FString::Find'."""
    s = undecorated.replace(" __ptr64", "")
    m = re.match(r"^void __cdecl `dynamic initializer for '(.*)''\(void\)$", s)
    if m:
        return f"dynamic initializer for {m.group(1)}"
    m = re.match(r"^void __cdecl `dynamic atexit destructor for '(.*)''\(void\)$", s)
    if m:
        return f"dynamic atexit destructor for {m.group(1)}"
    depth, cut = 0, len(s)
    for i, ch in enumerate(s):
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        elif ch == "(" and depth == 0:
            cut = i
            break
    head = s[:cut]
    depth, start = 0, 0
    for i, ch in enumerate(head):
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        elif ch == " " and depth == 0:
            start = i + 1
    name = head[start:]
    return name or undecorated


def source_of(name: str, demangled: str, sources: list[str], texts: dict) -> str:
    """The included .cpp that defines the function, by its qualified name, else the first."""
    qual = demangled.split("(")[0].split(" ")[-1] if "(" in demangled else demangled
    qual = re.sub(r"<.*>", "", qual)
    parts = qual.split("::")
    needle = "::".join(parts[-2:]) if len(parts) >= 2 else parts[-1]
    for s in sources:
        t = texts.get(s)
        if t is None:
            p = T.ROOT / s
            t = texts[s] = (p.read_text(encoding="utf-8", errors="replace") if p.exists() else "").replace(" (", "(")
        if needle and needle + "(" in t:
            return s
    return sources[0] if sources else ""


def choose_names(cands, proposed, resolver, functions, dimg, image_base, previous=None) -> dict[int, str]:
    """Address -> the one symbol it is proposed for. Where several are (/OPT:ICF folds equal
    bodies, and masked bytes cannot tell functions apart that differ only in their targets):
    the symbol the module's manifest already has there as an exact match, if it is one of
    them (previous: address -> symbol); else the one whose relocation targets the evidence
    supports best (evidence()), then the first by name. Choices are revised until they agree
    with one another: a function calling a symbol that lost its address to another counts
    that call as a disagreement (a lambda's outer and inner functions stay one lambda's)."""
    previous = previous or {}
    by_rva = {}
    for c in sorted(cands, key=lambda c: c[0]):
        rva = proposed.get(c[0])
        if rva is not None:
            by_rva.setdefault(rva, []).append(c)
    contested = {rva: cs for rva, cs in by_rva.items() if len(cs) > 1}
    wanted = {r.symbol for cs in contested.values() for c in cs for r in c[1].function_bytes(c[0])[1]}
    observed: dict[str, set[int]] = {}
    for name, obj, objpath, srcs, hits, n in cands:
        rva = proposed.get(name)
        if rva is None or len(hits) != 1 or rva in contested:
            continue
        raw, relocs = obj.function_bytes(name)
        ref = dimg.read(rva, len(raw))
        for r in relocs:
            if r.symbol in wanted:
                t = ref_target(r.kind, raw, ref, r.offset, rva, image_base)
                if t is not None:
                    observed.setdefault(r.symbol, set()).add(t)
    out = {rva: cs[0][0] for rva, cs in by_rva.items()}
    fixed = {rva for rva, cs in contested.items() if previous.get(rva) in {c[0] for c in cs}}
    for rva in fixed:
        out[rva] = previous[rva]
    # Callers: a placed function whose relocation to a contested symbol lands on that symbol's
    # address in the reference supports it there (ICF leaves one copy of equal bodies; the
    # name it gets should be the one its callers use).
    contenders = {c[0]: rva for rva, cs in contested.items() for c in cs}
    callers: dict[str, set[str]] = {}
    for name, obj, objpath, srcs, hits, n in cands:
        rva = proposed.get(name)
        if rva is None or rva in contested:
            continue
        raw, relocs = obj.function_bytes(name)
        ref = None
        for r in relocs:
            if r.symbol in contenders and r.symbol != name:
                ref = ref if ref is not None else dimg.read(rva, len(raw))
                if ref_target(r.kind, raw, ref, r.offset, rva, image_base) == contenders[r.symbol]:
                    callers.setdefault(r.symbol, set()).add(name)
    for _ in range(4):
        elsewhere = frozenset(c[0] for rva, cs in contested.items() for c in cs if out[rva] != c[0])
        changed = False
        for rva, cs in contested.items():
            if rva in fixed:
                continue
            scores = []
            for c in cs:
                neg, agree = evidence(c[1], c[2], c[0], rva, resolver, functions, proposed, observed, dimg,
                                      image_base, elsewhere - {c[0]})
                scores.append((neg, agree + len(callers.get(c[0], ()))))
            best = max(scores)
            pick = next(c[0] for c, s in zip(cs, scores) if s == best)
            changed |= pick != out[rva]
            out[rva] = pick
        if not changed:
            break
    return out


def map_module(module: str, ix: PdataIndex, img, dimg, resolver, functions) -> Counter:
    rec = json.loads((T.BUILD_DIR / f"{module}.build.json").read_text(encoding="utf-8"))
    taken = claimed(module)
    stats = Counter()
    cands = []   # (name, obj, objpath, sources, hits)
    seen = set()
    for u in rec["units"]:
        if not u["ok"]:
            continue
        obj = CoffObject(B.OBJ_ROOT / u["object"])
        for sym, _ in obj.functions():
            if sym.name in seen:
                continue
            seen.add(sym.name)
            data, mask = masked(obj, sym.name)
            if len(data) < MIN_BYTES:
                continue
            hits = ix.find(data, mask)
            cands.append((sym.name, obj, u["object"], u["sources"], hits, len(data)))
    proposed: dict[str, int] = {}
    for name, obj, objpath, srcs, hits, n in cands:
        if len(hits) == 1:
            proposed[name] = hits[0]
    for name, obj, objpath, srcs, hits, n in cands:
        if len(hits) > 1:
            h = disambiguate(obj, objpath, name, hits, resolver, functions, proposed, dimg, img.image_base)
            if h is not None:
                proposed[name] = h
                stats["ambiguous, decided by relocations"] += 1
            else:
                stats["ambiguous"] += 1
        elif len(hits) == 1:
            stats["unique"] += 1
        else:
            stats["none"] += 1
    entries = []
    own = ANALYSIS / f"functions-engine-{module}.json"
    previous = ({int(e["start_rva"], 16): e["symbol"] for e in expand(json.loads(own.read_text(encoding="utf-8")))
                 if e.get("match") == "exact"} if own.exists() else {})
    winner = choose_names(cands, proposed, resolver, functions, dimg, img.image_base, previous)
    names = demangle(sorted(proposed))
    texts: dict = {}
    for name, obj, objpath, srcs, hits, n in sorted(cands, key=lambda c: c[0]):
        rva = proposed.get(name)
        if rva is None:
            continue
        if rva in taken:
            stats[f"already in {taken[rva]}"] += 1
            continue
        if winner[rva] != name:
            stats["same address as another symbol (folded)"] += 1
            continue
        e = {"start_rva": f"0x{rva:08X}", "end_rva": f"0x{ix.extent[rva]:08X}",
             "name": names.get(name, name), "source": source_of(name, names.get(name, name), srcs, texts),
             "object": objpath, "symbol": name}
        if len(hits) > 1:
            e["evidence"] = (f"masked bytes identical to {len(hits)} .pdata functions of {n} bytes; the "
                             "independently known relocation targets agree with this one only")
        entries.append(e)
    entries.sort(key=lambda e: e["start_rva"])
    stats["proposed"] = len(entries)
    out = ANALYSIS / f"functions-engine-{module}.json"
    dump_compact(out, {
        "schema_version": 1, "generated_by": "tools/engine/map.py",
        "evidence": ("Functions of the local UE4.20 engine tree, compiled by tools/engine/build.py from "
                     "UnrealBuildTool's own compile actions for UE4Game Win64 Shipping, and located in the "
                     "reference by tools/engine/map.py. compare.py decides each match."),
        "entry_defaults": {"category": "engine-source", "module": module,
                           "name_confidence": "high-confidence inferred", "reference_state": "decrypted",
                           "evidence": (f"UE4.20 {module} compiled with v140 from UBT's compile action: masked "
                                        "bytes identical to exactly one .pdata function of the same length"),
                           "compact": True},
        "functions": entries})
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("modules", nargs="*")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    from compare import Resolver, load_decrypted, load_manual_symbols
    from pe import PEImage
    img = PEImage()
    dimg = load_decrypted(img)
    if dimg is None:
        print("needs the validated decrypted image", file=sys.stderr)
        return 1
    ix = load_index(img, dimg)
    resolver = Resolver(img, dimg, load_manual_symbols())
    functions = known_functions()
    names = [n for n in T.compiled_modules() if (T.BUILD_DIR / f"{n}.build.json").exists()] if a.all else a.modules
    total = Counter()
    for n in names:
        s = map_module(n, ix, img, dimg, resolver, functions)
        total.update(s)
        print(n, dict(s), flush=True)
    if len(names) > 1:
        print("total", dict(total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
