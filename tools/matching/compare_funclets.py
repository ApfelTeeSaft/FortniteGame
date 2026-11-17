"""Compare generated COFF funclets with the complete recorded ranges in the PE."""

import argparse
import json
from pathlib import Path
from struct import Struct

from capstone import Cs, CS_ARCH_X86, CS_MODE_64

from tools.matching.coff import funclet_code
from tools.matching.compare import byte_comparison, validate_runtime_body
from tools.matching.pe import REFERENCE, code_at, digest, file_hash, file_range, open_image
from tools.matching.unwind import checked_runtime_range, runtime_entries


SCOPE_RECORD = Struct("<IIII")


def verify_scope_references(image, table, record):
    scopes = record["seh_scopes"]
    if not scopes:
        raise ValueError("Expected an independently referenced SEH funclet")
    for scope in scopes:
        unwind = scope["parent_unwind_rva"]
        parent = scope["parent_rva"]
        parents = [end for start, end, metadata in table if (start, metadata) == (parent, unwind)]
        if len(parents) != 1:
            raise ValueError(f"Missing unique parent runtime-function at RVA {parent:#x}")
        _, header = file_range(image, unwind, 4)
        if header[0] != 0x09:
            raise ValueError(f"Parent at RVA {parent:#x} has no supported exception handler")
        codes = header[2]
        count_rva = unwind + 8 + (codes + codes % 2) * 2
        _, count_bytes = file_range(image, count_rva, 4)
        count = int.from_bytes(count_bytes, "little")
        table_start = count_rva + 4
        delta = scope["scope_record_rva"] - table_start
        if delta < 0 or delta % SCOPE_RECORD.size or delta // SCOPE_RECORD.size >= count:
            raise ValueError(f"Invalid SEH scope index for parent at RVA {parent:#x}")
        _, raw = file_range(image, scope["scope_record_rva"], SCOPE_RECORD.size)
        begin, end, filter_rva, target = SCOPE_RECORD.unpack(raw)
        if not (parent <= begin < end <= parents[0] and parent <= target < parents[0]):
            raise ValueError(f"SEH scope lies outside parent at RVA {parent:#x}")
        if filter_rva != record["start_rva"]:
            raise ValueError(f"SEH scope points to a different filter at RVA {filter_rva:#x}")


def compare_funclets(reference, candidate, manifest):
    reference_hash = file_hash(reference)
    if reference_hash != manifest["reference_sha256"]:
        raise ValueError("Reference executable does not match the manifest SHA-256")
    candidate_hash = file_hash(candidate)
    decoder = Cs(CS_ARCH_X86, CS_MODE_64)
    decoder.detail = True
    results = []
    with open_image(reference) as original:
        table = runtime_entries(original)
        for record in manifest["functions"]:
            if record.get("boundary_method") != "amd64-coff-funclet":
                continue
            verify_scope_references(original, table, record)
            start = record["start_rva"]
            end, unwind = checked_runtime_range(original, table, start, decoder)
            if end != record["end_rva"]:
                raise ValueError(f"Original runtime-function does not end at recorded RVA {end:#x}")
            offset, expected = code_at(original, start, end - start)
            if digest(expected) != record["original_sha256"]:
                raise ValueError(f"Original range hash mismatch at RVA {start:#x}")
            symbol = record["candidate_symbol"]
            actual = funclet_code(candidate, symbol)
            validate_runtime_body(decoder, expected, start)
            validate_runtime_body(decoder, actual, 0)
            results.append({
                "start_rva": start,
                "end_rva": end,
                "file_offset": offset,
                "original_unwind_rva": unwind,
                "candidate_symbol": symbol,
                "reference_image_sha256": reference_hash,
                "candidate_object_sha256": candidate_hash,
                "method": "raw-pe-to-coff-funclet-bytes",
                **byte_comparison(decoder, expected, actual, start, 0),
            })
    return {"functions": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("object", type=Path)
    parser.add_argument("--reference", type=Path, default=REFERENCE)
    parser.add_argument("--manifest", type=Path, default=Path("analysis/functions.json"))
    parser.add_argument("--verify", action="store_true", help="Verify recorded statuses and byte hashes")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    report = compare_funclets(args.reference, args.object, manifest)
    print(json.dumps(report, indent=2))
    if args.verify:
        expected = {
            record["start_rva"]: record
            for record in manifest["functions"]
            if record.get("boundary_method") == "amd64-coff-funclet"
        }
        if not expected:
            parser.exit(1, "No recorded funclets to verify\n")
        for result in report["functions"]:
            record = expected[result["start_rva"]]
            verification = record["verification"]
            if result["status"] != record["status"] or any(
                result[field] != verification[field]
                for field in ("status", "original_sha256", "candidate_sha256", "candidate_size")
            ) or result.get("first_difference", {}).get("offset") != verification.get(
                "first_difference_offset"
            ):
                parser.exit(1, f"Verification changed at RVA {result['start_rva']:#x}\n")


if __name__ == "__main__":
    main()
