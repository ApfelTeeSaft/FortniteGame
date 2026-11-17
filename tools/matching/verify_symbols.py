"""Verify native registration pairs and PE range metadata for the recorded RVAs."""

import argparse
import json
from pathlib import Path
from struct import unpack

from tools.matching.pe import REFERENCE, code_at, digest, file_hash, open_image


def verify(reference, inventory):
    if file_hash(reference) != inventory["reference_sha256"]:
        raise ValueError("Reference executable does not match the symbol inventory SHA-256")

    with open_image(reference) as image:
        base = image.OPTIONAL_HEADER.ImageBase
        exception = image.OPTIONAL_HEADER.DATA_DIRECTORY[3]
        for row in inventory["symbols"]:
            name_va, entry_va = unpack("<QQ", image.get_data(row["registration_pair_rva"], 16))
            name = image.get_string_at_rva(name_va - base).decode("ascii")
            begin, end, unwind = unpack("<III", image.get_data(row["runtime_function_rva"], 12))
            if (
                name != row["reflected_name"]
                or name_va - base != row["name_rva"]
                or entry_va - base != begin
                or (begin, end, unwind) != (row["start_rva"], row["end_rva"], row["unwind_rva"])
                or not exception.VirtualAddress <= row["runtime_function_rva"]
                <= exception.VirtualAddress + exception.Size - 12
                or (row["runtime_function_rva"] - exception.VirtualAddress) % 12
            ):
                raise ValueError(f"Registration or runtime function record changed for {name}")
            offset, code = code_at(image, begin, end - begin)
            if offset != row["file_offset"] or digest(code) != row["on_disk_sha256"]:
                raise ValueError(f"File-backed range changed for {name}")
    return len(inventory["symbols"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=REFERENCE)
    parser.add_argument("--inventory", type=Path, default=Path("analysis/symbols.json"))
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    print(f"Verified {verify(args.reference, inventory)} registration pairs and PE ranges.")


if __name__ == "__main__":
    main()
