"""Fingerprint the reference PE and the local toolchain.

Writes analysis/build-fingerprint.json with publishable metadata only: hashes,
headers, section table, directory summary, Rich header, debug directory, build
strings, and the per-section plaintext/encryption survey. It writes no code bytes.

Usage: python tools/matching/fingerprint.py
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pe import REPO_ROOT, PEImage, entropy  # noqa: E402

# Rich header product ids (VS2015 family) used by the reference.
PRODID = {
    0: "Unmarked objects (imports)", 1: "Import0 (imported functions)",
    123: "VS2005 Linker/Utc (8.00.50727)", 131: "VS2008 Masm (9.00.30729)",
    132: "VS2008 Utc C (9.00.30729)", 147: "VS2008 Implib/Utc (9.00.30729)",
    156: "VS2010 Utc/Implib (10.00)", 173: "VS2010 (10.00.30319)",
    199: "VS2012 tool (11.00)", 203: "VS2013 Utc C++ (12.00)", 206: "VS2013 Utc C (12.00)",
    207: "VS2013 Implib (12.00)", 208: "VS2013 Masm (12.00)",
    224: "VS2013 tool (12.00.31101)", 225: "VS2013 tool (12.00.31101)", 239: "VS2013 tool",
    255: "Cvtres 14.00", 256: "Export 14.00", 257: "Implib 14.00", 258: "Linker 14.00",
    259: "Masm 14.00", 260: "Utc1900_C (C compiler 19.00)", 261: "Utc1900_CPP (C++ compiler 19.00)",
}
DIRS = ["EXPORT", "IMPORT", "RESOURCE", "EXCEPTION", "SECURITY", "BASERELOC", "DEBUG",
        "ARCHITECTURE", "GLOBALPTR", "TLS", "LOAD_CONFIG", "BOUND_IMPORT", "IAT",
        "DELAY_IMPORT", "COM_DESCRIPTOR", "RESERVED"]


def section_survey(img: PEImage, sec, page: int = 0x1000) -> dict:
    raw = img.data[sec.raw:sec.raw + sec.rawsize]
    low = [i for i in range(0, len(raw), page) if entropy(raw[i:i + page]) < 7.0]
    return {"pages": (len(raw) + page - 1) // page, "pages_entropy_below_7": len(low)}


def main() -> int:
    img = PEImage()
    d = img.data
    sections = []
    for s in img.sections:
        body = d[s.raw:s.raw + s.rawsize]
        sections.append({
            "index": s.index, "name": s.name, "rva": f"0x{s.rva:08X}", "virtual_size": f"0x{s.vsize:08X}",
            "raw_offset": f"0x{s.raw:08X}", "raw_size": f"0x{s.rawsize:08X}",
            "characteristics": f"0x{s.chars:08X}", "entropy": round(entropy(body), 3),
            "sha256": hashlib.sha256(body).hexdigest()})
    dirs = {DIRS[i]: {"rva": f"0x{a:08X}", "size": f"0x{n:X}"}
            for i, (a, n) in enumerate(img.directories) if a}
    rich = [{"prodid": p, "build": b, "count": c, "tool": PRODID.get(p, "unknown")}
            for p, b, c in img.rich_header()]
    # Debug directory: CodeView PDB name and age (GUID kept; it identifies the build, not a secret).
    dbg = []
    drva, dsize = img.directory(6)
    for i in range(0, dsize, 28):
        _, ts, _, _, typ, size, rva, ptr = struct.unpack_from("<IIHHIIII", img.read(drva + i, 28))
        e = {"type": typ, "size": size}
        if typ == 2 and d[ptr:ptr + 4] == b"RSDS":
            guid = d[ptr + 4:ptr + 20]
            age = struct.unpack_from("<I", d, ptr + 20)[0]
            e.update(format="RSDS", guid=guid.hex(), age=age,
                     pdb=d[ptr + 24:d.index(b"\0", ptr + 24)].decode("latin-1"))
        dbg.append(e)
    u16 = lambda pat: sorted({m.group(0).decode("utf-16le") for m in re.finditer(pat, d)})
    strings = {
        "branch": u16(rb"\+\x00\+\x00F\x00o\x00r\x00t\x00n\x00i\x00t\x00e\x00\+\x00(?:[\x20-\x7e]\x00){1,60}"),
        "version_resource": u16(rb"4\x00\.\x002\x000\x00\.\x00(?:[\x20-\x7e]\x00){1,60}"),
    }
    sec_rva, sec_size = img.directory(4)  # file offset for SECURITY
    out = {
        "schema_version": 1,
        "generated_by": "tools/matching/fingerprint.py",
        "reference": {
            "path": "FortniteGame/2.5/2.5/FortniteGame/Binaries/Win64/FortniteClient-Win64-Shipping.exe",
            "sha256": img.sha256(), "size": len(d),
            "machine": f"0x{img.machine:04X}",
            "timestamp": img.timestamp,
            "timestamp_utc": datetime.fromtimestamp(img.timestamp, timezone.utc).isoformat(),
            "characteristics": f"0x{img.characteristics:04X}",
            "linker_version": f"{img.linker_major}.{img.linker_minor:02d}",
            "os_version": f"{img.os_major}.{img.os_minor}", "subsystem": img.subsystem,
            "dll_characteristics": f"0x{img.dll_characteristics:04X}",
            "image_base": f"0x{img.image_base:016X}", "entry_rva": f"0x{img.entry:08X}",
            "size_of_image": f"0x{img.size_of_image:08X}", "checksum": f"0x{img.checksum:08X}",
            "section_alignment": f"0x{img.section_alignment:X}", "file_alignment": f"0x{img.file_alignment:X}",
        },
        "sections": sections,
        "directories": dirs,
        "authenticode": {"present": bool(sec_size), "file_offset": f"0x{sec_rva:08X}", "size": f"0x{sec_size:X}",
                         "note": "WIN_CERTIFICATE appended after the last section. A rebuilt image cannot reproduce Epic's signature."},
        "rich_header": rich,
        "debug_directory": dbg,
        "build_strings": strings,
        "code_protection": {
            "main_text": section_survey(img, img.sections[0]),
            "summary": ("Function bodies in the main .text are individually encrypted on disk. The 0xCC padding "
                        "between them stays plaintext, and pdata/xdata/rdata are plaintext. See "
                        "analysis/plaintext-survey.json and docs/REVERSE_ENGINEERING.md."),
            "entry_point": "mainCRTStartup-shaped stub: its first call targets the second, non-standard .text section (no .pdata).",
        },
        "toolchain": {
            "reference_compiler": "MSVC 19.00.24215.1 (VS2015 Update 3): Rich prodid 261/260 build 24215, linker 258 build 24215",
            "local_matching_compiler": "C:/Program Files (x86)/Microsoft Visual Studio 14.0/VC/bin/amd64/cl.exe 19.00.24215.1",
            "solution_ide": "Visual Studio 2019 16.11 (D:/VS2019), platform toolset v140",
            "ltcg": "not used: no Utc1900 LTCG/CVTCIL product ids in the Rich header",
            "windows_sdk_for_matching": "10.0.10586.0 (pinned; original SDK version not yet established)",
        },
        "engine": {
            "reference_version_resource": "4.20.0-3889387+++Fortnite+Release-2.5",
            "local_engine_tree": "Engine/Build/Build.version: 4.20.0, BranchName ++UE4+Release-4.20, Changelist 0",
            "note": "The reference is an internal 4.20 development fork at CL 3889387 (linked 2018-02-14). Known code differences from public 4.20.0 are listed in docs/ENGINE_DIFFERENCES.md.",
        },
    }
    path = REPO_ROOT / "analysis" / "build-fingerprint.json"
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
