"""Recover the reference's __LINE__ numbering of the engine .cpp files.

Fortnite's engine files have lines added or removed relative to the public UE4.20.0 tree, so
the line numbers that shipping logging and fatal errors pass (`mov r8d, 775` where the
reference has 769) differ, and a function that differs only there is never placed.

measure: every compile action is compiled once more with each of its engine .cpp files
renumbered through an overlay (tools/engine/overlay.py): file i of the unit starts at line
(i + 1) * 50,000 + 1. A 4-byte field whose value in the regular object is below 50,000 and
in this one is (i + 1) * 50,000 + L is a __LINE__ of file i, line L of the public file.
Any other difference between the two objects is reported (the overlays must change nothing
else). Each function with such fields is then found in the reference with them masked as well
as its relocation fields: at its manifest address if it is already exact there (an anchor),
else at the .pdata functions of its length with equal masked bytes that the relocation targets
confirm (confirmed(): every independently known target agrees, at least one does, and no string
literal is text the reference lacks), if exactly one does or all that do hold the same values
there. The reference's value at each field is the original number of that line.

derive: per file, one original number per line (the value with two thirds of the weight;
anchors weigh 1000), else none. The numbers need not increase: Fortnite's files also have
functions moved (GenericPlatformProcess.cpp's stubs), and #line can set any number. Writes
analysis/engine-lines.json, which build.py turns into #line directives (tools/engine/overlay.py).

    python tools/engine/lines.py measure Core [...] | --all [--jobs N]
    python tools/engine/lines.py derive
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "matching"))
import build as B  # noqa: E402
import overlay as O  # noqa: E402
import ue_target as T  # noqa: E402

OFFSET = 50_000          # #line accepts at most 16,777,215: 334 files of up to 50,000 lines a unit
LINE_LIMIT = 16_777_215
MEASURE = T.BUILD_DIR / "lines"
MEASURE_OBJ = MEASURE / "obj"
ANCHOR = 1000


def offset_numbering(index: int, src: Path):
    """Each file renumbered from (index + 1) * OFFSET, under the reference's __FILE__ (its
    literals then resolve by content in confirmed())."""
    if (index + 2) * OFFSET > LINE_LIMIT:
        return None     # beyond the limit: not measured
    return (index + 1) * OFFSET + 1, [], O.reference_file(src)


def line_fields(a: bytes, b: bytes, files: int) -> tuple[list[tuple[int, int, int]], bool]:
    """([(offset, file index, line)], explained) for two compilations of one function."""
    out, covered, n = [], -1, len(a)
    for p in range(n):
        if p <= covered or a[p] == b[p]:
            continue
        for s in range(max(0, p - 3), p + 1):
            if s + 4 > n:
                break
            va = int.from_bytes(a[s:s + 4], "little")
            vb = int.from_bytes(b[s:s + 4], "little")
            i, line = divmod(vb, OFFSET)
            if va < OFFSET and 1 <= i <= files and line:
                out.append((s, i - 1, line))
                covered = s + 3
                break
        else:
            return out, False
    return out, True


GENERATED_NAME = re.compile(r"<lambda_[0-9a-f]{32}>|\?A0x[0-9a-f]{8}")


def renamed_functions(oa, ob) -> dict[str, str]:
    """Functions of oa missing from ob by name -> their ob name. Lambdas and anonymous
    namespaces are named from the file name and position, which the overlay changes; a name
    maps when exactly one function of each object has its generated parts and size."""
    def groups(o, skip):
        g = defaultdict(list)
        for s, _ in o.functions():
            if s.name not in skip and GENERATED_NAME.search(s.name):
                g[(GENERATED_NAME.sub("?", s.name), len(o.function_bytes(s.name)[0]))].append(s.name)
        return g
    names_a = {s.name for s, _ in oa.functions()}
    names_b = {s.name for s, _ in ob.functions()}
    ga, gb = groups(oa, names_b), groups(ob, names_a)
    return {v[0]: gb[k][0] for k, v in ga.items() if len(v) == 1 and len(gb.get(k, ())) == 1}


def engine_sources(unit: Path) -> list[Path]:
    if not unit.name.startswith("Module."):
        return [unit] if O.is_engine_source(unit) else []
    return [Path(p) for p in B.included_sources(unit) if O.is_engine_source(Path(p))]


def manifest_rvas(module: str) -> tuple[dict[str, int], set[str]]:
    """Symbol -> RVA of the module's engine manifest entries that compare.py placed, and the
    exact ones among them."""
    from manifest_io import expand
    p = T.ROOT / "analysis" / f"functions-engine-{module}.json"
    if not p.exists():
        return {}, set()
    out, exact = {}, set()
    for e in expand(json.loads(p.read_text(encoding="utf-8"))):
        if e.get("match") in ("exact", "relocation-equivalent"):
            out[e["symbol"]] = int(e["start_rva"], 16)
            if e["match"] == "exact":
                exact.add(e["symbol"])
    return out, exact


def confirmed(obj, objpath: str, name: str, rva: int, ctx, placed: dict) -> bool:
    """Is the reference function at rva this one? Every relocation target known independently
    (a matched or placed function, an import, data unique by content) must agree, at least one
    must, and every string literal's text must be what the reference holds where the function
    points (or, when it is not read there, somewhere): functions that differ only in their
    message and line (the "not implemented on this platform" stubs) otherwise match one
    another."""
    import map as M
    ix, img, dimg, resolver, functions = ctx
    raw, relocs = obj.function_bytes(name)
    ref = dimg.read(rva, len(raw))
    agree = 0
    for r in relocs:
        t = M.ref_target(r.kind, raw, ref, r.offset, rva, img.image_base)
        if t is None:
            continue
        lit = M.literal_agrees(obj, r.symbol, t, dimg)
        if lit is False:
            return False
        if lit:
            agree += 1
            continue
        if r.symbol in functions:
            exp = {functions[r.symbol]}
        elif r.symbol in placed:
            exp = {placed[r.symbol]}
        else:
            exp = M.independent_targets(resolver, obj, objpath, r.symbol)
        if not exp:
            if M.absent_literal(resolver, obj, r.symbol):
                return False
            continue
        if t not in exp:
            return False
        agree += 1
    return agree > 0


def measure_module(module: str, jobs: int, ctx) -> dict:
    import map as M
    from coff import CoffObject
    from locate import masked
    ix, img, dimg, resolver, functions = ctx
    env = B.vc_environment()
    acts = T.actions(module)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        recs = list(ex.map(lambda a: B.compile_action(a, dict(T.PROJECT_DEFINITIONS), env, obj_root=MEASURE_OBJ,
                                                        tag="lines", numbering=offset_numbering,
                                                        overlay_root=MEASURE / "overlay"), acts))
    seconds = round(time.time() - t0, 1)
    placed, exact = manifest_rvas(module)
    stats, cons, odd = Counter(), [], []
    for act, rec in zip(acts, recs):
        unit_name = act.name[:-len(".cpp.obj.response")]
        a_path = B.ENGINE_OBJ / module / f"{unit_name}.obj"
        if not rec["ok"] or not a_path.exists():
            stats["units failed"] += 1
            continue
        srcs = engine_sources(B.action_source(act))
        b_path = MEASURE_OBJ / module / f"{unit_name}.obj"
        oa, ob = CoffObject(a_path), CoffObject(b_path)
        index_b = ob.function_index()
        renamed = renamed_functions(oa, ob)
        for sym, _ in oa.functions():
            name_b = sym.name if sym.name in index_b else renamed.get(sym.name)
            if name_b is None:
                stats["absent from the renumbered object"] += 1
                continue
            a, ra = oa.function_bytes(sym.name)
            b, rb = ob.function_bytes(name_b)
            if len(a) != len(b) or [(r.offset, r.kind) for r in ra] != [(r.offset, r.kind) for r in rb]:
                stats["different size or relocations"] += 1
                odd.append(sym.name)
                continue
            if a == b:
                continue
            fields, ok = line_fields(a, b, len(srcs))
            if not ok:
                stats["other differences"] += 1
                odd.append(sym.name)
                continue
            stats["functions with line fields"] += 1
            data, mask = masked(oa, sym.name)
            fields = [f for f in fields if f[0] + 4 <= len(data)]
            for s, _, _ in fields:
                for j in range(s, s + 4):
                    mask[j] = 1
            # Only an exact entry's address is taken as given: a relocation-equivalent one may sit
            # where it does because of line numbers an earlier measurement recovered.
            rva, how = (placed.get(sym.name) if sym.name in exact else None), "manifest"
            if rva is not None:
                ref = dimg.read(rva, len(data))
                if any(not mask[j] and data[j] != ref[j] for j in range(len(data))):
                    rva = None
            if rva is None:
                # A candidate counts only if the relocation targets known independently (in the
                # renumbered object __FILE__ is the reference's string) agree with it.
                hits = ix.find(data, mask)
                good = [h for h in hits if confirmed(ob, str(b_path), name_b, h, ctx, placed)]
                if not good:
                    stats["not located" if not hits else "not confirmed by relocation targets"] += 1
                    continue
                if len({tuple(dimg.read(h + s, 4) for s, _, _ in fields) for h in good}) != 1:
                    stats["confirmed candidates disagree"] += 1
                    continue
                rva = good[0]
                how = "confirmed by relocation targets" if len(good) == 1 else "several confirmed, equal values"
            stats[f"located: {how}"] += 1
            weight = ANCHOR if sym.name in exact else 1
            ref = dimg.read(rva, len(data))
            for s, i, line in fields:
                orig = int.from_bytes(ref[s:s + 4], "little")
                if not 0 < orig < OFFSET:
                    stats["implausible reference value"] += 1
                    continue
                cons.append([srcs[i].relative_to(T.ROOT).as_posix(), line, orig, weight, sym.name])
    out = {"module": module, "seconds": seconds, "stats": dict(sorted(stats.items())),
           "unexplained": sorted(odd)[:50], "constraints": cons}
    (MEASURE / f"{module}.lines.json").write_text(json.dumps(out, indent=0), encoding="utf-8")
    print(module, seconds, "s", dict(stats), f"{len(cons)} constraints", flush=True)
    return out


def derive() -> dict:
    per = defaultdict(lambda: defaultdict(Counter))
    modules = []
    for p in sorted(MEASURE.glob("*.lines.json")):
        m = json.loads(p.read_text(encoding="utf-8"))
        modules.append(m["module"])
        for f, L, R, w, _ in m["constraints"]:
            per[f][L][R] += w
    stats, files = Counter(), {}
    for f in sorted(per):
        pts = []
        for L, rs in per[f].items():
            R, w = rs.most_common(1)[0]
            if w * 3 < sum(rs.values()) * 2:
                stats["lines with conflicting values"] += 1
                continue
            pts.append((L, R, w))
        chain = sorted(pts)
        if chain:
            files[f] = [[L, R, min(w, ANCHOR)] for L, R, w in chain]
            stats["files"] += 1
            stats["lines"] += len(chain)
            if any(R != L for L, R, _ in chain):
                stats["files renumbered"] += 1
    doc = {
        "schema_version": 1, "generated_by": "tools/engine/lines.py",
        "build_root": O.BUILD_ROOT,
        "evidence": ("Original line numbers of public UE4.20.0 engine .cpp lines, read from the __LINE__ "
                     "fields of the reference's functions (tools/engine/lines.py measure): [our line, original "
                     "line, weight]; weight 1000 is a function already exact, else the number of functions."),
        "modules": modules, "stats": dict(sorted(stats.items())), "files": files}
    text = json.dumps({k: v for k, v in doc.items() if k != "files"}, indent=1)[:-2]
    body = ",\n".join(f"  {json.dumps(f)}: {json.dumps(c, separators=(',', ':'))}" for f, c in files.items())
    O.LINES_JSON.write_text(text + ',\n "files": {\n' + body + "\n }\n}\n", encoding="utf-8")
    print(dict(stats))
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["measure", "derive"])
    ap.add_argument("modules", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 8)
    a = ap.parse_args()
    if a.command == "derive":
        derive()
        return 0
    import map as M
    from compare import Resolver, load_decrypted, load_manual_symbols
    from pe import PEImage
    img = PEImage()
    dimg = load_decrypted(img)
    if dimg is None:
        print("needs the validated decrypted image", file=sys.stderr)
        return 1
    ctx = (M.load_index(img, dimg), img, dimg, Resolver(img, dimg, load_manual_symbols()), M.known_functions())
    MEASURE.mkdir(parents=True, exist_ok=True)
    names = T.compiled_modules() if a.all else a.modules
    for n in names:
        measure_module(n, a.jobs, ctx)
    return 0


if __name__ == "__main__":
    sys.exit(main())
