"""Find file-backed runtime-function prologues corroborated by unwind metadata."""

import argparse
from collections import Counter
import json
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_64

from tools.matching.compare import validate_runtime_body
from tools.matching.pe import REFERENCE, code_at, file_hash, open_image
from tools.matching.unwind import checked_runtime_range, runtime_entries, small_stack_prologue


def ida_ranges(path, reference_hash):
    if path is None:
        return {}
    with path.open(encoding="utf-8") as stream:
        header = json.loads(next(stream))
        if header["reference_sha256"] != reference_hash or header["scope"] != "all":
            raise ValueError("Expected a full IDA export for the same reference SHA-256")
        return {row["start_rva"]: row["chunks"] for row in map(json.loads, stream)}


def audit(reference, ida_inventory=None):
    reference_hash = file_hash(reference)
    ranges = ida_ranges(ida_inventory, reference_hash)
    decoder = Cs(CS_ARCH_X86, CS_MODE_64)
    decoder.detail = True
    counters = Counter(dict.fromkeys(
        ("supported_unwind", "file_backed_prologue", "matching_prologue", "accepted_body"), 0
    ))
    matches = []
    with open_image(reference) as image:
        entries = runtime_entries(image)
        for entry in entries:
            prologue = small_stack_prologue(image, entry)
            if prologue is None:
                continue
            counters["supported_unwind"] += 1
            start, end, unwind = entry
            try:
                _, prefix = code_at(image, start, len(prologue))
            except ValueError:
                continue
            counters["file_backed_prologue"] += 1
            if prefix != prologue:
                continue
            counters["matching_prologue"] += 1
            row = {"start_rva": start, "end_rva": end, "unwind_rva": unwind}
            if ida_inventory is not None:
                row["ida_chunks"] = ranges.get(start)
            try:
                checked_runtime_range(image, entries, start)
                _, body = code_at(image, start, end - start)
                validate_runtime_body(decoder, body, start)
            except ValueError as error:
                row["rejection"] = str(error)
            else:
                counters["accepted_body"] += 1
            matches.append(row)
    return {
        "schema_version": 1,
        "reference_sha256": reference_hash,
        "method": "version-1 single UWOP_ALLOC_SMALL",
        "runtime_slots": len(entries),
        **counters,
        "matching_ranges": matches,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=REFERENCE)
    parser.add_argument("--ida-inventory", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.reference, args.ida_inventory), indent=2))


if __name__ == "__main__":
    main()
