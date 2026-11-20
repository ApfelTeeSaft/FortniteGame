"""Minimal AMD64 COFF object reader (sections, symbols, relocations)."""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

IMAGE_REL_AMD64 = {
    0x0: "ABSOLUTE", 0x1: "ADDR64", 0x2: "ADDR32", 0x3: "ADDR32NB", 0x4: "REL32",
    0x5: "REL32_1", 0x6: "REL32_2", 0x7: "REL32_3", 0x8: "REL32_4", 0x9: "REL32_5",
    0xA: "SECTION", 0xB: "SECREL", 0xC: "SECREL7", 0xD: "TOKEN", 0xE: "SREL32",
}
REL_FIELD_SIZE = {"ADDR64": 8, "ADDR32": 4, "ADDR32NB": 4, "REL32": 4, "REL32_1": 4,
                  "REL32_2": 4, "REL32_3": 4, "REL32_4": 4, "REL32_5": 4,
                  "SECTION": 2, "SECREL": 4}


@dataclass
class Reloc:
    offset: int
    symbol: str
    kind: str


@dataclass
class CoffSection:
    index: int          # 1-based, as used by symbols
    name: str
    data: bytes
    chars: int
    relocs: list[Reloc] = field(default_factory=list)


@dataclass
class CoffSymbol:
    name: str
    value: int
    section: int
    type: int
    storage: int


class CoffObject:
    def __init__(self, path: Path | str):
        d = Path(path).read_bytes()
        sig1, sig2 = struct.unpack_from("<HH", d, 0)
        if sig1 == 0 and sig2 == 0xFFFF:  # /bigobj: ANON_OBJECT_HEADER_BIGOBJ
            machine = struct.unpack_from("<H", d, 6)[0]
            nsec, symptr, nsym = struct.unpack_from("<III", d, 44)
            hdr, symsz, secfmt = 56, 20, "<IiHBB"
        else:
            machine, nsec, _, symptr, nsym, optsz, _ = struct.unpack_from("<HHIIIHH", d, 0)
            hdr, symsz, secfmt = 20 + optsz, 18, "<IhHBB"
        if machine != 0x8664:
            raise ValueError(f"unexpected machine {machine:#x}")
        strtab = symptr + symsz * nsym

        def name_at(raw: bytes) -> str:
            if raw[:4] == b"\0\0\0\0":
                o = strtab + struct.unpack_from("<I", raw, 4)[0]
                return d[o:d.index(b"\0", o)].decode("latin-1")
            return raw.rstrip(b"\0").decode("latin-1")

        self.symbols: list[CoffSymbol | None] = []
        i = 0
        while i < nsym:
            o = symptr + symsz * i
            raw = d[o:o + 8]
            value, sec, typ, storage, naux = struct.unpack_from(secfmt, d, o + 8)
            self.symbols.append(CoffSymbol(name_at(raw), value, sec, typ, storage))
            self.symbols.extend([None] * naux)
            i += 1 + naux
        self.sections: list[CoffSection] = []
        for s in range(nsec):
            o = hdr + 40 * s
            rawname = d[o:o + 8]
            if rawname[:1] == b"/":
                so = strtab + int(rawname[1:].rstrip(b"\0"))
                name = d[so:d.index(b"\0", so)].decode("latin-1")
            else:
                name = rawname.rstrip(b"\0").decode("latin-1")
            size, ptr, relptr, _, nrel, _, chars = struct.unpack_from("<IIIIHHI", d, o + 16)
            data = d[ptr:ptr + size] if ptr else bytes(size)
            relocs = []
            for r in range(nrel):
                roff, symidx, rtype = struct.unpack_from("<IIH", d, relptr + 10 * r)
                sym = self.symbols[symidx]
                relocs.append(Reloc(roff, sym.name if sym else f"#{symidx}",
                                    IMAGE_REL_AMD64.get(rtype, hex(rtype))))
            self.sections.append(CoffSection(s + 1, name, data, chars, relocs))

    def symbol(self, name: str) -> CoffSymbol | None:
        """The defining record of `name` if there is one, else its first (undefined) record."""
        idx = self.__dict__.get("_sym_index")
        if idx is None:
            idx = {}
            for s in self.symbols:
                if s is None:
                    continue
                cur = idx.get(s.name)
                if cur is None or (cur.section <= 0 < s.section):
                    idx[s.name] = s
            self._sym_index = idx
        return idx.get(name)

    def data_layout(self) -> dict[str, list[tuple[str, int, int]]]:
        """Per section name: [(symbol, offset, storage)] for defined data symbols.

        Sections that share a name (e.g. one COMDAT .bss per static local) are laid out in
        section-table order with their alignment, as the linker places one object's
        contributions. Offsets are relative to the start of that group.
        """
        cached = self.__dict__.get("_layout")
        if cached is not None:
            return cached
        base: dict[int, int] = {}
        cursor: dict[str, int] = {}
        for sec in self.sections:
            if sec.chars & 0x20:  # code
                continue
            bits = (sec.chars >> 20) & 0xF
            align = 1 << (bits - 1) if bits else 16
            cur = cursor.get(sec.name, 0)
            cur = (cur + align - 1) & ~(align - 1)
            base[sec.index] = cur
            cursor[sec.name] = cur + len(sec.data)
        groups: dict[str, list[tuple[str, int, int]]] = {}
        for s in self.symbols:
            if s is None or s.section <= 0 or s.section not in base or s.storage not in (2, 3):
                continue
            if s.name.startswith((".", "$unwind", "$pdata", "$chain")):
                continue
            sec = self.sections[s.section - 1]
            groups.setdefault(sec.name, []).append((s.name, base[s.section] + s.value, s.storage))
        self._layout = groups
        return groups

    def function_index(self) -> dict[str, tuple[int, int, CoffSection]]:
        cached = self.__dict__.get("_fn_index")
        if cached is not None:
            return cached
        per_sec: dict[int, list[CoffSymbol]] = {}
        for sym, sec in self.functions():
            per_sec.setdefault(sec.index, []).append(sym)
        idx = {}
        for secidx, syms in per_sec.items():
            sec = self.sections[secidx - 1]
            syms.sort(key=lambda s: s.value)
            for i, s in enumerate(syms):
                end = next((t.value for t in syms[i + 1:] if t.value > s.value), len(sec.data))
                idx.setdefault(s.name, (s.value, end, sec))
        self._fn_index = idx
        return idx

    def functions(self):
        """Yield (symbol, section) for every function symbol defined in a code section."""
        for sym in self.symbols:
            if sym is None or sym.section <= 0:
                continue
            sec = self.sections[sym.section - 1]
            if sec.chars & 0x20 and (sym.type & 0x20 or sym.value == 0) and sym.storage in (2, 3):
                if sym.name.startswith((".", "$")):
                    continue
                yield sym, sec

    def function_bytes(self, symname: str) -> tuple[bytes, list[Reloc]]:
        """Bytes of a function from its symbol to the next symbol in the same section."""
        hit = self.function_index().get(symname)
        if hit is None:
            raise KeyError(symname)
        start, end, sec = hit
        rel = [Reloc(r.offset - start, r.symbol, r.kind) for r in sec.relocs if start <= r.offset < end]
        return sec.data[start:end], rel
