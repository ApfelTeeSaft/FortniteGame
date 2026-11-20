"""Minimal, dependency-light PE32+ reader used by the matching tools.

Only reads the reference image; never writes to it. All coordinates are
RVAs unless a name says otherwise (``va`` = ImageBase + RVA, ``off`` = raw
file offset).
"""
from __future__ import annotations

import hashlib
import math
import struct
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
# Path relative to the repository root (E:\FortniteGame). CLAUDE.md names it
# relative to the workspace root as FortniteGame\2.5\2.5\FortniteGame\...
DEFAULT_REFERENCE = (
    REPO_ROOT / "2.5" / "2.5" / "FortniteGame" / "Binaries" / "Win64"
    / "FortniteClient-Win64-Shipping.exe"
)
REFERENCE_SHA256 = "9731a6b5e1fab894c089849713c371182e357dcbefa7d8d4e71dc19eeb449102"


@dataclass(frozen=True)
class Section:
    index: int
    name: str
    rva: int
    vsize: int
    raw: int
    rawsize: int
    chars: int

    def contains_rva(self, rva: int) -> bool:
        return self.rva <= rva < self.rva + max(self.vsize, self.rawsize)


@dataclass(frozen=True)
class RuntimeFunction:
    begin: int
    end: int
    unwind: int


def entropy(buf: bytes) -> float:
    if not buf:
        return 0.0
    n = len(buf)
    return -sum(c / n * math.log2(c / n) for c in Counter(buf).values())


class PEImage:
    def __init__(self, path: Path | str = DEFAULT_REFERENCE):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        d = self.data
        if d[:2] != b"MZ":
            raise ValueError("not an MZ image")
        self.e_lfanew = struct.unpack_from("<I", d, 0x3C)[0]
        if d[self.e_lfanew:self.e_lfanew + 4] != b"PE\0\0":
            raise ValueError("missing PE signature")
        fh = self.e_lfanew + 4
        (self.machine, self.nsections, self.timestamp, _, _,
         self.opt_size, self.characteristics) = struct.unpack_from("<HHIIIHH", d, fh)
        oh = fh + 20
        magic = struct.unpack_from("<H", d, oh)[0]
        if magic != 0x20B:
            raise ValueError("not PE32+")
        self.linker_major, self.linker_minor = d[oh + 2], d[oh + 3]
        self.entry = struct.unpack_from("<I", d, oh + 16)[0]
        self.image_base = struct.unpack_from("<Q", d, oh + 24)[0]
        self.section_alignment, self.file_alignment = struct.unpack_from("<II", d, oh + 32)
        (self.os_major, self.os_minor, self.img_major, self.img_minor,
         self.subsys_major, self.subsys_minor) = struct.unpack_from("<6H", d, oh + 40)
        self.size_of_image, self.size_of_headers, self.checksum = struct.unpack_from("<III", d, oh + 56)
        self.subsystem, self.dll_characteristics = struct.unpack_from("<HH", d, oh + 68)
        ndirs = struct.unpack_from("<I", d, oh + 108)[0]
        self.directories = [struct.unpack_from("<II", d, oh + 112 + 8 * i) for i in range(ndirs)]
        st = oh + self.opt_size
        self.sections: list[Section] = []
        for i in range(self.nsections):
            o = st + 40 * i
            name = d[o:o + 8].rstrip(b"\0").decode("ascii", "replace")
            vsize, rva, rawsize, raw = struct.unpack_from("<IIII", d, o + 8)
            chars = struct.unpack_from("<I", d, o + 36)[0]
            self.sections.append(Section(i, name, rva, vsize, raw, rawsize, chars))

    # -- coordinates -------------------------------------------------
    def section_of(self, rva: int) -> Section | None:
        for s in self.sections:
            if s.rva <= rva < s.rva + s.vsize:
                return s
        return None

    def rva_to_off(self, rva: int) -> int | None:
        s = self.section_of(rva)
        if s is None or rva - s.rva >= s.rawsize:
            return None
        return s.raw + (rva - s.rva)

    def read(self, rva: int, n: int) -> bytes:
        off = self.rva_to_off(rva)
        if off is None or self.rva_to_off(rva + n - 1) is None:
            raise ValueError(f"RVA range {rva:#x}+{n:#x} is not file-backed")
        return self.data[off:off + n]

    def u32(self, rva: int) -> int:
        return struct.unpack("<I", self.read(rva, 4))[0]

    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()

    # -- directories ---------------------------------------------------
    def directory(self, index: int) -> tuple[int, int]:
        return self.directories[index] if index < len(self.directories) else (0, 0)

    def runtime_functions(self) -> list[RuntimeFunction]:
        rva, size = self.directory(3)
        raw = self.read(rva, size)
        return [RuntimeFunction(*struct.unpack_from("<III", raw, i))
                for i in range(0, size - size % 12, 12)]

    def rich_header(self) -> list[tuple[int, int, int]]:
        """Return (prodid, build, count) tuples from the Rich header."""
        d = self.data[:self.e_lfanew]
        end = d.find(b"Rich")
        if end < 0:
            return []
        key = d[end + 4:end + 8]
        dec = bytes(b ^ key[i % 4] for i, b in enumerate(d[:end]))
        start = dec.rfind(b"DanS")
        if start < 0:
            return []
        out = []
        for o in range(start + 16, end, 8):
            comp, cnt = struct.unpack_from("<II", dec, o)
            out.append((comp >> 16, comp & 0xFFFF, cnt))
        return out
