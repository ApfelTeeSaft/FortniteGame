"""Near misses of a module's compiled functions: where the systematic differences are.

For each function tools/engine/map.py could not place (no masked-identical .pdata function),
the most similar reference function of the same length is found (equal bytes outside the
relocation fields). Those at or above --min similarity are disassembled side by side, and the
first differing instruction is classified:

- displacement: same instruction, different memory displacement (a member offset: class layout);
- immediate: same instruction, different constant;
- branch: a jump or call whose target differs (code layout inside the function);
- register: same mnemonic, different registers (register allocation);
- mnemonic: different instructions.

With --survey, every module (or the one named) is scanned for near misses whose instructions
align and differ only in memory displacements, and the changes are counted by (ours ->
reference) displacement, virtual calls apart from member accesses: where a class layout
differs, and how many functions it costs.

Diagnostics only; nothing is written to the manifests. Usage:

    python tools/engine/nearmiss.py Core [--min 0.9] [--show 20]
    python tools/engine/nearmiss.py --survey [--min 0.85] [--show 25]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "matching"))
import capstone  # noqa: E402
import build as B  # noqa: E402
import map as M  # noqa: E402
import ue_target as T  # noqa: E402
from coff import CoffObject  # noqa: E402
from locate import masked  # noqa: E402

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)


def similarity(data: bytes, mask: bytearray, ref: bytes) -> float:
    a, b = bytearray(data), bytearray(ref)
    for i, m in enumerate(mask):
        if m:
            a[i] = b[i] = 0
    x = (int.from_bytes(a, "little") ^ int.from_bytes(b, "little")).to_bytes(len(a), "little")
    return x.count(0) / len(a)


def first_difference(data: bytes, mask: bytearray, ref: bytes) -> tuple[str, str, str]:
    """(class, candidate instruction, reference instruction) at the first unmasked difference."""
    first = next(i for i in range(len(data)) if not mask[i] and data[i] != ref[i])
    a = list(MD.disasm(data, 0))
    b = list(MD.disasm(ref, 0))
    ia = next((x for x in a if x.address <= first < x.address + x.size), None)
    ib = next((x for x in b if x.address <= first < x.address + x.size), None)
    if ia is None or ib is None:
        return "undecodable", "", ""
    sa, sb = f"{ia.mnemonic} {ia.op_str}", f"{ib.mnemonic} {ib.op_str}"
    if ia.mnemonic != ib.mnemonic:
        return "mnemonic", sa, sb
    if ia.mnemonic.startswith("j") or ia.mnemonic == "call":
        return "branch", sa, sb
    na, nb = re.sub(r"0x[0-9a-f]+", "#", ia.op_str), re.sub(r"0x[0-9a-f]+", "#", ib.op_str)
    if na == nb:
        return ("displacement" if "[" in ia.op_str and re.search(r"[+-] 0x", ia.op_str) else "immediate"), sa, sb
    return "register", sa, sb


MEMORY_OPERAND = re.compile(r"\[([a-z0-9]+)(?: \+ [a-z0-9]+\*\d)? ([+-]) (0x[0-9a-f]+)\]")


def displacements(code: bytes) -> list[tuple[int, str, str, int]]:
    """(offset, mnemonic, base register, displacement) of every non-RIP memory operand."""
    out = []
    for ins in MD.disasm(code, 0):
        for m in MEMORY_OPERAND.finditer(ins.op_str):
            if m.group(1) != "rip":
                out.append((ins.address, ins.mnemonic, m.group(1), int(m.group(3), 16) * (1 if m.group(2) == "+" else -1)))
    return out


def survey(modules: list[str], minimum: float, show: int) -> int:
    """Across modules: near misses whose instructions align and differ only in memory
    displacements, counted by (ours -> reference) displacement. A virtual call's change names
    a vtable slot that moved; a member access's, a member that moved."""
    from compare import load_decrypted
    from pe import PEImage
    img = PEImage()
    ix = M.load_index(img, load_decrypted(img))
    calls, members, seen = Counter(), Counter(), set()
    examples: dict[tuple, list[str]] = {}
    for module in modules:
        path = T.BUILD_DIR / f"{module}.build.json"
        if not path.exists():
            continue
        n = 0
        for u in json.loads(path.read_text(encoding="utf-8"))["units"]:
            if not u["ok"]:
                continue
            obj = CoffObject(B.OBJ_ROOT / u["object"])
            for sym, _ in obj.functions():
                if sym.name in seen:
                    continue
                seen.add(sym.name)
                data, mask = masked(obj, sym.name)
                if len(data) < 24 or ix.find(data, mask):
                    continue
                best, best_s = None, 0.0
                for start, ref in ix.by_len.get(len(data), []):
                    s = similarity(data, mask, ref)
                    if s > best_s:
                        best, best_s = ref, s
                if best is None or best_s < minimum:
                    continue
                ours, theirs = displacements(bytes(data)), displacements(best)
                if len(ours) != len(theirs):
                    continue
                diffs = [(x[1], x[3], y[3]) for x, y in zip(ours, theirs) if x[:3] == y[:3] and x[3] != y[3]]
                n += bool(diffs)
                for mnemonic, a_, b_ in diffs:
                    key = (a_, b_)
                    (calls if mnemonic in ("call", "jmp") else members)[key] += 1
                    examples.setdefault((mnemonic in ("call", "jmp"), key), []).append(sym.name)
        print(f"{module}: {n} functions differing in displacements only", flush=True)
    for title, counter, is_call in (("virtual calls", calls, True), ("member accesses", members, False)):
        print(f"\n{title} (ours -> reference):")
        for (a_, b_), c in counter.most_common(show):
            print(f"  {c:5d} {a_:#x} -> {b_:#x}  e.g. {examples[(is_call, (a_, b_))][0][:80]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("module", nargs="?")
    ap.add_argument("--min", type=float, default=0.9)
    ap.add_argument("--show", type=int, default=20)
    ap.add_argument("--survey", action="store_true",
                    help="all modules (or the one named): displacement-only near misses by displacement")
    a = ap.parse_args()
    if a.survey:
        mods = [a.module] if a.module else sorted(p.name[:-len(".build.json")] for p in T.BUILD_DIR.glob("*.build.json"))
        return survey(mods, a.min, a.show)
    if not a.module:
        ap.error("a module, or --survey")
    from compare import load_decrypted
    from pe import PEImage
    img = PEImage()
    dimg = load_decrypted(img)
    ix = M.load_index(img, dimg)
    rec = json.loads((T.BUILD_DIR / f"{a.module}.build.json").read_text(encoding="utf-8"))
    seen, near, classes, total = set(), [], Counter(), 0
    for u in rec["units"]:
        if not u["ok"]:
            continue
        obj = CoffObject(B.OBJ_ROOT / u["object"])
        for sym, _ in obj.functions():
            if sym.name in seen:
                continue
            seen.add(sym.name)
            data, mask = masked(obj, sym.name)
            if len(data) < 24 or ix.find(data, mask):
                continue
            total += 1
            best, best_s = None, 0.0
            for start, ref in ix.by_len.get(len(data), []):
                s = similarity(data, mask, ref)
                if s > best_s:
                    best, best_s = (start, ref), s
            if best and best_s >= a.min:
                cls, ca, rb = first_difference(data, mask, best[1])
                classes[cls] += 1
                near.append((best_s, sym.name, best[0], cls, ca, rb))
    print(f"{a.module}: {total} unplaced functions of 24+ bytes; {len(near)} have a same-length reference "
          f"function at >= {a.min:.0%} similarity")
    print(dict(classes))
    for s, name, start, cls, ca, rb in sorted(near, reverse=True)[:a.show]:
        print(f"  {s:.3f} 0x{start:08X} {cls:12s} {ca:40s} | {rb:40s} {name[:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
