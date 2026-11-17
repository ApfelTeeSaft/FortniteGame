"""Compare verified original function ranges against a compiled x64 PE."""

import argparse
from contextlib import ExitStack
import json
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone import CS_GRP_CALL, CS_GRP_INT, CS_GRP_IRET, CS_GRP_JUMP, CS_GRP_RET

from tools.matching.pe import REFERENCE, code_at, digest, file_hash, open_image


def leaf_size(image, rva, decoder):
    # Decode from the export, independently of the original function's length.
    # Branching functions need independent candidate boundaries from other evidence.
    for section in image.sections:
        size = min(256, section.VirtualAddress + min(
            section.SizeOfRawData, section.Misc_VirtualSize
        ) - rva)
        if section.VirtualAddress <= rva and size > 0:
            try:
                _, machine_code = code_at(image, rva, size)
            except ValueError:
                continue
            break
    else:
        raise ValueError(f"No file-backed candidate code at RVA {rva:#x}")

    forbidden = {CS_GRP_CALL, CS_GRP_JUMP, CS_GRP_INT, CS_GRP_IRET}
    for instruction in decoder.disasm(machine_code, rva):
        if forbidden.intersection(instruction.groups) or instruction.mnemonic in {
            "hlt", "ud2", "int3", "syscall", "sysret"
        }:
            break
        if CS_GRP_RET in instruction.groups:
            if instruction.mnemonic == "ret" and not instruction.op_str:
                return instruction.address + instruction.size - rva
            break
    raise ValueError(f"Unable to establish a straight-line leaf at RVA {rva:#x}")


def instruction_at(decoder, data, rva, offset):
    for instruction in decoder.disasm(data, rva):
        if instruction.address <= rva + offset < instruction.address + instruction.size:
            return f"{instruction.mnemonic} {instruction.op_str}".strip()
    return None


def compare_function(original, candidate, record, exports, decoder):
    start, end = record["start_rva"], record["end_rva"]
    offset, expected = code_at(original, start, end - start)
    if digest(expected) != record["original_sha256"]:
        raise ValueError(f"Original range hash mismatch at RVA {start:#x}")
    symbol = record["candidate_export"]
    entry = exports.get(symbol)
    if entry is None or entry.forwarder:
        raise ValueError(f"Missing direct candidate export {symbol}")
    rva = entry.address
    if leaf_size(original, start, decoder) != len(expected):
        raise ValueError(f"Original leaf does not end at recorded RVA {end:#x}")
    size = leaf_size(candidate, rva, decoder)
    _, actual = code_at(candidate, rva, size)
    prefix = next(
        (i for i, pair in enumerate(zip(expected, actual)) if pair[0] != pair[1]),
        min(len(expected), len(actual)),
    )
    equal = expected == actual
    result = {
        "start_rva": start,
        "end_rva": end,
        "file_offset": offset,
        "candidate_export": symbol,
        "candidate_rva": rva,
        "original_size": len(expected),
        "candidate_size": size,
        "method": "raw-pe-leaf-bytes",
        "original_sha256": digest(expected),
        "candidate_sha256": digest(actual),
        "status": "exact" if equal else "partial" if prefix else "unmatched",
    }
    if not equal:
        result["first_difference"] = {
            "offset": prefix,
            "expected_bytes": expected[prefix:prefix + 12].hex(),
            "actual_bytes": actual[prefix:prefix + 12].hex(),
            "expected_instruction": instruction_at(decoder, expected, start, prefix),
            "actual_instruction": instruction_at(decoder, actual, rva, prefix),
        }
    return result


def compare(reference, candidate, manifest):
    original_hash = file_hash(reference)
    if original_hash != manifest["reference_sha256"]:
        raise ValueError("Reference executable does not match the manifest SHA-256")
    candidate_hash = file_hash(candidate)
    decoder = Cs(CS_ARCH_X86, CS_MODE_64)
    decoder.detail = True
    with ExitStack() as stack:
        original = stack.enter_context(open_image(reference))
        build = stack.enter_context(open_image(candidate))
        build.parse_data_directories(directories=[0])
        directory = getattr(build, "DIRECTORY_ENTRY_EXPORT", None)
        exports = {
            entry.name.decode("ascii"): entry
            for entry in (directory.symbols if directory else [])
            if entry.name
        }
        results = [
            compare_function(original, build, record, exports, decoder)
            for record in manifest["functions"]
            if record.get("candidate_export")
        ]
    for result in results:
        result["reference_image_sha256"] = original_hash
        result["candidate_image_sha256"] = candidate_hash
    return {
        "reference_sha256": original_hash,
        "candidate_sha256": candidate_hash,
        "whole_file_exact": original_hash == candidate_hash,
        "functions": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--reference", type=Path, default=REFERENCE)
    parser.add_argument("--manifest", type=Path, default=Path("analysis/functions.json"))
    parser.add_argument("--require-exact", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = compare(args.reference, args.candidate, manifest)
    print(json.dumps(result, indent=2))
    results = result["functions"]
    if args.require_exact and (not results or any(r["status"] != "exact" for r in results)):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
