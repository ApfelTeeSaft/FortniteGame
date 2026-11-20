"""Load, normalize and validate a user-supplied decrypted image of the reference build.

The shipping EXE stores function bodies encrypted (docs/REVERSE_ENGINEERING.md).
A memory image of the same build, taken after decryption, supplies the plaintext
bodies. This module:

1. extracts the module image from a full-memory minidump (.dmp), a raw dump of
   the module region, or a PE-file dump;
2. detects the load-base delta from DIR64 base relocations that target sections
   which are plaintext in the original file, then subtracts it at every DIR64
   site so absolute addresses read as they would at the preferred base 0x140000000;
3. validates that the image is this build (plaintext sections must agree with the
   original file) and measures how much of .text decrypted (prologue vs. unwind).

The dump and the normalized image are proprietary: they stay under local-output/
and are never committed. Only hashes and statistics are published.
"""
from __future__ import annotations

import hashlib
import struct
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from pe import PEImage, RuntimeFunction

MODULE_NAME = "FortniteClient-Win64-Shipping.exe"
IMAGE_REL_BASED_DIR64 = 10


# --------------------------------------------------------------------------- sources
@dataclass
class ModuleImage:
    """RVA-indexed module image with a byte-granular presence map."""
    base: int | None
    data: bytearray
    present: bytearray            # 1 where the source supplied the byte
    source_format: str
    notes: list[str] = field(default_factory=list)


def _read_minidump(path: Path, size_of_image: int, name: str = MODULE_NAME) -> ModuleImage:
    with open(path, "rb") as f:
        hdr = f.read(32)
        sig, _, nstreams, dir_rva = struct.unpack_from("<4sIII", hdr)
        if sig != b"MDMP":
            raise ValueError("not a minidump")
        f.seek(dir_rva)
        streams = {}
        for _ in range(nstreams):
            stype, dsize, rva = struct.unpack("<III", f.read(12))
            streams.setdefault(stype, (dsize, rva))
        if 4 not in streams:
            raise ValueError("minidump has no ModuleListStream")
        _, mrva = streams[4]
        f.seek(mrva)
        nmod = struct.unpack("<I", f.read(4))[0]
        base = msize = None
        for _ in range(nmod):
            rec = f.read(108)
            b, sz, _, _, name_rva = struct.unpack_from("<QIIII", rec)
            here = f.tell()
            f.seek(name_rva)
            ln = struct.unpack("<I", f.read(4))[0]
            mname = f.read(ln).decode("utf-16le", "replace")
            f.seek(here)
            if mname.lower().endswith(name.lower()):
                base, msize = b, sz
                break
        if base is None:
            raise ValueError(f"module {name} not found in minidump")
        img = ModuleImage(base, bytearray(size_of_image), bytearray(size_of_image), "minidump")
        if msize != size_of_image:
            img.notes.append(f"module list SizeOfImage {msize:#x} differs from reference {size_of_image:#x}")
        end = base + size_of_image
        ranges = []
        if 9 in streams:                       # Memory64ListStream (full-memory dumps)
            f.seek(streams[9][1])
            n, data_rva = struct.unpack("<QQ", f.read(16))
            off = data_rva
            for _ in range(n):
                start, dsz = struct.unpack("<QQ", f.read(16))
                ranges.append((start, dsz, off))
                off += dsz
        if 5 in streams:                       # MemoryListStream
            f.seek(streams[5][1])
            n = struct.unpack("<I", f.read(4))[0]
            for _ in range(n):
                start, dsz, rva = struct.unpack("<QII", f.read(16))
                ranges.append((start, dsz, rva))
        for start, dsz, off in ranges:
            lo, hi = max(start, base), min(start + dsz, end)
            if lo >= hi:
                continue
            f.seek(off + (lo - start))
            chunk = f.read(hi - lo)
            img.data[lo - base:lo - base + len(chunk)] = chunk
            img.present[lo - base:lo - base + len(chunk)] = b"\1" * len(chunk)
        return img


def _read_flat(path: Path, original: PEImage) -> ModuleImage:
    raw = path.read_bytes()
    size = original.size_of_image
    candidates = []
    # (a) image layout: file offset == RVA
    img_layout = bytearray(raw[:size].ljust(size, b"\0"))
    pres = bytearray(b"\1" * min(len(raw), size)).ljust(size, b"\0")
    candidates.append(("raw-image-layout", img_layout, pres))
    # (b) PE-file dump: map through the dump's own section table
    if raw[:2] == b"MZ":
        try:
            e = struct.unpack_from("<I", raw, 0x3C)[0]
            nsec, optsz = struct.unpack_from("<H", raw, e + 6)[0], struct.unpack_from("<H", raw, e + 20)[0]
            st = e + 24 + optsz
            buf, pr = bytearray(size), bytearray(size)
            hdr_len = min(original.size_of_headers, len(raw))
            buf[:hdr_len], pr[:hdr_len] = raw[:hdr_len], b"\1" * hdr_len
            for i in range(nsec):
                vsize, rva, rsize, rptr = struct.unpack_from("<IIII", raw, st + 40 * i + 8)
                n = max(0, min(rsize, vsize or rsize, size - rva, len(raw) - rptr))
                buf[rva:rva + n], pr[rva:rva + n] = raw[rptr:rptr + n], b"\1" * n
            candidates.append(("pe-file-dump", buf, pr))
        except (struct.error, ValueError):
            pass
    # Pick the layout whose .rdata agrees best with the original file.
    rd = next(s for s in original.sections if s.name == ".rdata")
    probe = original.read(rd.rva, min(rd.rawsize, 0x100000))

    def score(buf: bytes) -> int:
        seg = buf[rd.rva:rd.rva + len(probe)]
        return sum(1 for i in range(0, len(probe), 64) if seg[i:i + 64] == probe[i:i + 64])

    fmt, buf, pr = max(candidates, key=lambda c: score(c[1]))
    return ModuleImage(None, buf, pr, fmt)


def load_dump(path: Path | str, original: PEImage) -> ModuleImage:
    path = Path(path)
    with open(path, "rb") as f:
        magic = f.read(4)
    if magic == b"MDMP":
        return _read_minidump(path, original.size_of_image)
    return _read_flat(path, original)


# --------------------------------------------------------------------------- relocations
def dir64_sites(original: PEImage) -> list[int]:
    rva, size = original.directory(5)
    raw = original.read(rva, size)
    sites, o = [], 0
    while o + 8 <= len(raw):
        page, bs = struct.unpack_from("<II", raw, o)
        if bs < 8:
            break
        for i in range(o + 8, o + bs, 2):
            e = struct.unpack_from("<H", raw, i)[0]
            if e >> 12 == IMAGE_REL_BASED_DIR64:
                sites.append(page + (e & 0xFFF))
        o += bs
    return sites


def detect_delta(original: PEImage, img: ModuleImage, sites: list[int]) -> tuple[int, int, int]:
    """Return (delta, votes, sampled) using DIR64 sites in sections that are plaintext on disk."""
    plain = {".rdata", ".pdata", ".rsrc", "_RDATA", ".gfids"}
    votes: Counter[int] = Counter()
    sampled = 0
    for rva in sites:
        s = original.section_of(rva)
        if s is None or s.name not in plain or not img.present[rva] or not img.present[rva + 7]:
            continue
        off = original.rva_to_off(rva)
        if off is None:
            continue
        file_val = struct.unpack_from("<Q", original.data, off)[0]
        dump_val = struct.unpack_from("<Q", img.data, rva)[0]
        votes[(dump_val - file_val) & 0xFFFFFFFFFFFFFFFF] += 1
        sampled += 1
        if sampled >= 200000:
            break
    if not votes:
        return 0, 0, 0
    delta, n = votes.most_common(1)[0]
    return delta, n, sampled


def normalize(img: ModuleImage, sites: list[int], delta: int) -> int:
    """Subtract `delta` at every DIR64 site the dump supplied. Returns sites adjusted."""
    if delta == 0:
        return 0
    done = 0
    for rva in sites:
        if rva + 8 <= len(img.data) and img.present[rva] and img.present[rva + 7]:
            v = struct.unpack_from("<Q", img.data, rva)[0]
            struct.pack_into("<Q", img.data, rva, (v - delta) & 0xFFFFFFFFFFFFFFFF)
            done += 1
    return done


# --------------------------------------------------------------------------- image view
class DecryptedImage:
    """PEImage-compatible view that serves bytes from a normalized module image."""

    def __init__(self, original: PEImage, data: bytes, present: bytes | None = None):
        self.original = original
        self.data_rva = data
        self.present = present
        self.sections = original.sections
        self.image_base = original.image_base

    def read(self, rva: int, n: int) -> bytes:
        if rva < 0 or rva + n > len(self.data_rva):
            raise ValueError("outside image")
        if self.present is not None and b"\0" in self.present[rva:rva + n]:
            raise ValueError(f"RVA range {rva:#x}+{n:#x} not present in dump")
        return bytes(self.data_rva[rva:rva + n])

    def u32(self, rva: int) -> int:
        return struct.unpack("<I", self.read(rva, 4))[0]

    def runtime_functions(self) -> list[RuntimeFunction]:
        return self.original.runtime_functions()

    def section_of(self, rva: int):
        return self.original.section_of(rva)


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()
