"""Generate a reference fingerprint with no PDB paths or general string dumps."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from tools.matching.pe import REFERENCE, file_hash, open_image


def fingerprint(path):
    with open_image(path) as image:
        image.parse_data_directories(directories=[0, 1, 6, 13])
        header = image.OPTIONAL_HEADER
        data = image.__data__
        rich = (image.parse_rich_header() or {}).get("values", [])
        markers = set()
        for term in (
            "4.20.0-3889387", "++Fortnite+Release-2.5", "++Fortnite+Release-2.5-CL-3889387"
        ):
            if data.find(term.encode("utf-16le")) != -1:
                markers.add(term)
        modules = Counter(
            match.group().decode("utf-16le")
            for match in re.finditer(
                rb"/\x00S\x00c\x00r\x00i\x00p\x00t\x00/\x00(?:[A-Za-z0-9_]\x00)+(?=\x00\x00)",
                data,
            )
        )
        exports = getattr(image, "DIRECTORY_ENTRY_EXPORT", None)
        return {
            "schema_version": 1,
            "reference_name": path.name,
            "reference_sha256": file_hash(path),
            "size": len(data),
            "coff_timestamp_utc": datetime.fromtimestamp(
                image.FILE_HEADER.TimeDateStamp, timezone.utc
            ).isoformat(),
            "machine": f"{image.FILE_HEADER.Machine:#06x}",
            "image_base": header.ImageBase,
            "entry_rva": header.AddressOfEntryPoint,
            "subsystem": header.Subsystem,
            "linker_version": [header.MajorLinkerVersion, header.MinorLinkerVersion],
            "rich_records": [
                {"product_id": tag >> 16, "build": tag & 0xffff, "count": count}
                for tag, count in zip(rich[::2], rich[1::2])
            ],
            "sections": [
                {
                    "name": section.Name.rstrip(b"\0").decode("ascii"),
                    "rva": section.VirtualAddress,
                    "virtual_size": section.Misc_VirtualSize,
                    "file_offset": section.PointerToRawData,
                    "file_size": section.SizeOfRawData,
                    "characteristics": f"{section.Characteristics:#010x}",
                    "entropy": round(section.get_entropy(), 3),
                }
                for section in image.sections
            ],
            "directories": {
                entry.name.removeprefix("IMAGE_DIRECTORY_ENTRY_"): {
                    "file_offset" if index == 4 else "rva": entry.VirtualAddress,
                    "size": entry.Size,
                }
                for index, entry in enumerate(header.DATA_DIRECTORY)
                if entry.Size
            },
            "runtime_function_slots": header.DATA_DIRECTORY[3].Size // 12,
            "imports": modules_for(image, "DIRECTORY_ENTRY_IMPORT"),
            "delay_imports": modules_for(image, "DIRECTORY_ENTRY_DELAY_IMPORT"),
            "export_count": len(exports.symbols) if exports else 0,
            "debug_directory_types": [
                entry.struct.Type for entry in getattr(image, "DIRECTORY_ENTRY_DEBUG", [])
            ],
            "rtti_type_marker_counts": {
                marker.decode("ascii"): sum(1 for _ in re.finditer(re.escape(marker), data))
                for marker in (b".?AV", b".?AU")
            },
            "engine_build_strings": sorted(markers),
            "reflected_script_packages": dict(sorted(modules.items())),
        }


def modules_for(image, attribute):
    return sorted(
        {entry.dll.decode("ascii") for entry in getattr(image, attribute, [])},
        key=str.casefold,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=REFERENCE)
    args = parser.parse_args()
    print(json.dumps(fingerprint(args.reference), indent=2))


if __name__ == "__main__":
    main()
