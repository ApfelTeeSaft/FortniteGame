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

Diagnostics only; nothing is written to the manifests. Usage:

    python tools/engine/nearmiss.py Core [--min 0.9] [--show 20]
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("module")
    ap.add_argument("--min", type=float, default=0.9)
    ap.add_argument("--show", type=int, default=20)
    a = ap.parse_args()
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
