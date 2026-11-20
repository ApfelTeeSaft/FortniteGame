"""Derive reference RVAs for object-file symbols from evidence other than the code under test.

Sources, each recorded with its evidence:

* ``__imp_<name>`` for delay-loaded imports: slots listed by the plaintext delay-import
  descriptors and their name tables.
* ``__imp_<name>`` for static imports, two independently named slots:
  - the protector's import table in .idata, named by its plaintext descriptors. In the
    decrypted image 25,348 ``call [rip+X]`` sites and every import thunk reference this
    table, i.e. the protector rewrote those displacements;
  - the original linker IAT at the start of .rdata, which has no readable names on disk.
    In the decrypted image each of its slots holds the same address as exactly one
    protector slot, which names it. 62 call sites still reference this table.
  A relocation field may match either slot of the same import name; compare.py records
  which table it used.
* ``<name>`` for import thunks: a ``jmp qword ptr [rip+disp]`` (FF 25) in the decrypted main
  .text, outside every .pdata range, whose target is a named IAT slot, and which is the
  only such thunk for that name.
* data symbols: unique occurrence of the object's data bytes (see resolve_data_symbol).

Matched function symbols are added by compare.py once those functions are exact.
"""
from __future__ import annotations

import bisect
import struct

from coff import CoffObject
from pe import PEImage


def _cstr(img: PEImage, rva: int) -> str:
    return img.read(rva, 512).split(b"\0")[0].decode("latin-1")


def _import_name(img: PEImage, entry: int) -> str | None:
    if entry >> 63:
        return None  # by ordinal: no symbol name to map
    return _cstr(img, (entry & 0x7FFFFFFF) + 2)


def _iat_rdata_extent(img: PEImage) -> tuple[int, int]:
    """Original MSVC IAT at the start of .rdata: qwords holding 0, an ordinal, or a hint/name RVA."""
    rd = next(s for s in img.sections if s.name == ".rdata")
    rva = rd.rva
    while True:
        v = int.from_bytes(img.read(rva, 8), "little")
        if not (v == 0 or v >> 63 or (v < img.size_of_image and img.section_of(v) is not None)):
            return rd.rva, rva
        rva += 8


def build(original: PEImage, decrypted=None) -> dict[str, list[dict]]:
    """Symbol -> list of {rva, evidence}. Several entries are equally evidenced addresses."""
    out: dict[str, list[dict]] = {}

    def put(sym: str, rva: int, evidence: str) -> None:
        lst = out.setdefault(sym, [])
        if all(x["rva"] != rva for x in lst):
            lst.append({"rva": rva, "evidence": evidence})

    # Delay-load imports (descriptors and name tables are plaintext on disk).
    drva, dsize = original.directory(13)
    for i in range(0, dsize, 32):
        _, name, _, iat, intab = struct.unpack("<5I", original.read(drva + i, 20))
        if name == 0:
            break
        dll = _cstr(original, name)
        k = 0
        while True:
            ent = int.from_bytes(original.read(intab + 8 * k, 8), "little")
            if ent == 0:
                break
            nm = _import_name(original, ent)
            if nm:
                put("__imp_" + nm, iat + 8 * k, f"delay-import slot of {dll}!{nm}")
            k += 1

    # Static imports in the protector's table (plaintext descriptors in .idata).
    irva, isize = original.directory(1)
    prot: list[tuple[int, str, str]] = []
    for i in range(0, isize, 20):
        oft, _, _, name, ft = struct.unpack("<5I", original.read(irva + i, 20))
        if name == 0:
            break
        dll = _cstr(original, name)
        k = 0
        while True:
            ent = int.from_bytes(original.read(oft + 8 * k, 8), "little")
            if ent == 0:
                break
            nm = _import_name(original, ent)
            if nm:
                prot.append((ft + 8 * k, dll, nm))
            k += 1
    dlls_per_name: dict[str, set[str]] = {}
    for _, dll, nm in prot:
        dlls_per_name.setdefault(nm, set()).add(dll)
    slot_name: dict[int, str] = {}
    for slot, dll, nm in prot:
        if len(dlls_per_name[nm]) == 1:  # one name exported by two DLLs would be ambiguous
            slot_name[slot] = nm
            put("__imp_" + nm, slot, f"protector import table slot of {dll}!{nm}")

    if decrypted is None:
        return out

    # Original linker IAT (.rdata start), named through runtime values shared with the protector table.
    value_names: dict[int, set[str]] = {}
    for slot, _, nm in prot:
        val = int.from_bytes(decrypted.read(slot, 8), "little")
        if val:
            value_names.setdefault(val, set()).add(nm)
    lo, hi = _iat_rdata_extent(original)
    for slot in range(lo, hi, 8):
        val = int.from_bytes(decrypted.read(slot, 8), "little")
        names = value_names.get(val)
        if val and names and len(names) == 1:
            nm = next(iter(names))
            if len(dlls_per_name.get(nm, ())) == 1:
                slot_name[slot] = nm
                put("__imp_" + nm, slot, f"original IAT slot; runtime value equals protector entry for {nm}")

    # Import thunks: FF 25 rel32 -> named slot, outside .pdata ranges, unique per name.
    text = original.sections[0]
    rfs = sorted((rf.begin, rf.end) for rf in original.runtime_functions())
    begins = [b for b, _ in rfs]
    code = decrypted.read(text.rva, text.rawsize)
    thunks: dict[str, list[tuple[int, int]]] = {}
    pos = code.find(b"\xff\x25")
    while pos >= 0:
        if pos + 6 <= len(code):
            rva = text.rva + pos
            tgt = rva + 6 + struct.unpack_from("<i", code, pos + 2)[0]
            nm = slot_name.get(tgt)
            if nm is not None:
                j = bisect.bisect_right(begins, rva) - 1
                if not (j >= 0 and rfs[j][0] <= rva < rfs[j][1]):
                    thunks.setdefault(nm, []).append((rva, tgt))
        pos = code.find(b"\xff\x25", pos + 1)
    for nm, sites in thunks.items():
        if len(sites) == 1:
            rva, tgt = sites[0]
            put(nm, rva, f"import thunk jmp [0x{tgt:08X}] ({nm})")
    return out


def _string_literal(window: bytes) -> bytes | None:
    """The NUL-terminated literal at the start of `window` (wide or narrow), if it is one."""
    if len(window) >= 4 and window[0] != 0 and window[1] == 0:
        end = 0
        while end + 1 < len(window) and window[end:end + 2] != b"\0\0":
            if window[end + 1] != 0:
                return None
            end += 2
        if window[end:end + 2] == b"\0\0":
            return window[:end + 2]
        return None
    end = window.find(b"\0")
    if end > 0 and all(0x09 <= c < 0x7F for c in window[:end]):
        return window[:end + 1]
    return None


def resolve_data_symbol(obj: CoffObject, symname: str, haystack: bytes,
                        hay_rva: int) -> tuple[int | None, str]:
    """Find a data symbol's bytes in `haystack` (plaintext reference data starting at hay_rva).

    String literals ($SG..., ??_C@...) are searched as their exact NUL-terminated content. A
    match must start on a string boundary, i.e. be preceded by a NUL of the same width, so
    that a suffix of a longer string cannot count. Other data symbols are searched as their
    bytes up to the next symbol in their section, at the section alignment. In every case the
    occurrence must be unique, and data containing relocations is not searched.
    """
    sym = next((s for s in obj.symbols if s is not None and s.name == symname and s.section > 0), None)
    if sym is None:
        return None, "symbol not defined in object"
    sec = obj.sections[sym.section - 1]
    if sec.chars & 0x20 or not sec.chars & 0x40:
        return None, "not an initialized-data symbol"
    offs = sorted({s.value for s in obj.symbols
                   if s is not None and s.section == sym.section and s.storage in (2, 3)} | {len(sec.data)})
    hi = offs[offs.index(sym.value) + 1]
    window = sec.data[sym.value:hi]
    if any(sym.value <= r.offset < hi for r in sec.relocs):
        return None, "data contains relocations"
    hits: list[int] = []
    if symname.startswith(("$SG", "??_C@")):
        lit = _string_literal(window)
        if lit is None:
            return None, "string literal not recognised"
        width = 2 if lit[1:2] == b"\0" else 1
        p = haystack.find(lit)
        while p >= 0 and len(hits) < 3:
            if (hay_rva + p) % width == 0 and p >= width and haystack[p - width:p] == b"\0" * width:
                hits.append(hay_rva + p)
            p = haystack.find(lit, p + 1)
        what = f"{len(lit)}-byte string literal"
    else:
        if len(window) < 8:
            return None, "data too short to identify"
        align_bits = (sec.chars >> 20) & 0xF
        align = 1 << (align_bits - 1) if align_bits else 16
        if sym.value:  # a symbol inside a section is only known to be as aligned as its offset
            align = min(align, sym.value & -sym.value)
        p = haystack.find(window)
        while p >= 0 and len(hits) < 3:
            if (hay_rva + p) % align == 0:
                hits.append(hay_rva + p)
            p = haystack.find(window, p + 1)
        what = f"{len(window)}-byte data block"
    if len(hits) == 1:
        return hits[0], f"unique {what}"
    if not hits:
        return None, f"{what} not found in reference"
    return None, f"{what} ambiguous ({len(hits)}+ occurrences)"
