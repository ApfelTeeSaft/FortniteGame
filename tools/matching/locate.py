"""Locate compiled functions in the decrypted reference by their bytes.

A locating aid for naming and annotation, not a matcher: it masks every relocation field of the
candidate and reports the 16-byte-aligned addresses in a range of .text where all other bytes are
identical. compare.py still resolves the relocations and decides the match state.

    python tools/matching/locate.py OBJ LO HI [NAME-SUBSTRING ...]

OBJ is a compiled object (for example FortniteGameCode/Build/ClientShipping/obj/...), LO and HI
are RVAs (hex). With substrings, only the function symbols containing one are tried. Several hits
mean the masked body is not unique: bodies that differ only in relocated operands (two wrappers
passing different string literals, say) need other evidence, such as the alphabetical COMDAT
order, to tell apart. Without a hit the best .pdata start by identical-prefix length is printed.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from coff import REL_FIELD_SIZE, CoffObject  # noqa: E402
from compare import load_decrypted  # noqa: E402
from pe import PEImage  # noqa: E402


def masked(obj: CoffObject, name: str) -> tuple[bytes, bytearray]:
    data, relocs = obj.function_bytes(name)
    mask = bytearray(len(data))
    for r in relocs:
        for i in range(r.offset, min(len(data), r.offset + REL_FIELD_SIZE.get(r.kind, 4))):
            mask[i] = 1
    n = len(data)
    while n > 1 and data[n - 1] == 0xCC and not mask[n - 1]:   # the COMDAT's int3 padding
        n -= 1
    return data[:n], mask[:n]


class PdataIndex:
    """The reference's primary .pdata functions by length, for locating whole objects at once.

    A function's extent is its primary entry plus the contiguous chained entries that unwind to
    it (only int3 padding between them), as compare.py reads it. find() returns the starts
    whose bytes equal the candidate's outside its relocation fields. It proposes; compare.py
    resolves the relocations and decides the match state.
    """

    def __init__(self, img: PEImage, dimg):
        from unwind import UNW_FLAG_CHAININFO, parse_unwind
        text = img.sections[0]
        rfs = sorted((r for r in img.runtime_functions() if text.contains_rva(r.begin)), key=lambda r: r.begin)
        by_begin = {r.begin: r for r in rfs}

        def root(r):
            for _ in range(32):
                ui = parse_unwind(img, r.unwind)
                if not (ui.flags & UNW_FLAG_CHAININFO) or not ui.chained:
                    return r.begin
                nxt = by_begin.get(ui.chained[0])
                if nxt is None:
                    return ui.chained[0]
                r = nxt
            return r.begin

        roots = [root(r) for r in rfs]
        self.extent: dict[int, int] = {}
        i = 0
        while i < len(rfs):
            if roots[i] != rfs[i].begin:
                i += 1
                continue
            start, end, j = rfs[i].begin, rfs[i].end, i + 1
            while j < len(rfs) and roots[j] == start and 0 <= rfs[j].begin - end <= 16:
                gap = dimg.read(end, rfs[j].begin - end)
                if gap.strip(b"\xcc"):
                    break
                end, j = rfs[j].end, j + 1
            self.extent[start] = end
            i += 1
        self.by_len: dict[int, list[tuple[int, bytes]]] = {}
        for start, end in self.extent.items():
            try:
                self.by_len.setdefault(end - start, []).append((start, dimg.read(start, end - start)))
            except ValueError:
                pass

    def find(self, data: bytes, mask: bytearray) -> list[int]:
        bucket = self.by_len.get(len(data))
        if not bucket:
            return []
        runs, k, n = [], 0, len(data)
        while k < n:
            if mask[k]:
                k += 1
                continue
            j = k
            while j < n and not mask[j]:
                j += 1
            runs.append((k, j, data[k:j]))
            k = j
        runs.sort(key=lambda r: r[0] - r[1])   # longest run first: it rejects most quickly
        return [s for s, ref in bucket if all(ref[a:b] == piece for a, b, piece in runs)]


def locate(region: bytes, lo: int, data: bytes, mask: bytearray, step: int = 16) -> list[int]:
    hits = []
    for off in range(0, len(region) - len(data) + 1, step):
        if all(mask[i] or region[off + i] == data[i] for i in range(len(data))):
            hits.append(lo + off)
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("obj")
    ap.add_argument("lo")
    ap.add_argument("hi")
    ap.add_argument("names", nargs="*")
    a = ap.parse_args()
    img = PEImage()
    dimg = load_decrypted(img)
    if dimg is None:
        print("no validated decrypted image (see docs/BUILDING.md)", file=sys.stderr)
        return 1
    lo, hi = int(a.lo, 16), int(a.hi, 16)
    region = dimg.read(lo, hi - lo + 0x2000)
    starts = sorted(r.begin for r in img.runtime_functions() if lo <= r.begin < hi)
    obj = CoffObject(a.obj)
    for sym, _ in obj.functions():
        if a.names and not any(s in sym.name for s in a.names):
            continue
        data, mask = masked(obj, sym.name)
        if len(data) < 4:
            continue
        hits = [h for h in locate(region, lo, data, mask) if h < hi]
        if hits:
            more = " ..." if len(hits) > 6 else ""
            print(f"HIT  {sym.name}  {len(data)} bytes  at " + ", ".join(f"0x{h:08X}" for h in hits[:6]) + more)
            continue
        best, best_len = None, -1
        for s in starts:
            off, k = s - lo, 0
            while k < len(data) and (mask[k] or region[off + k] == data[k]):
                k += 1
            if k > best_len:
                best, best_len = s, k
        print(f"miss {sym.name}  {len(data)} bytes" + (f"  best 0x{best:08X} (prefix {best_len})" if best else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
