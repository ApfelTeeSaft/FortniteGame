"""Compare verified original function ranges against a compiled x64 PE."""

import argparse
from contextlib import ExitStack
import json
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone import CS_GRP_CALL, CS_GRP_INT, CS_GRP_IRET, CS_GRP_JUMP, CS_GRP_RET
from capstone import CS_GRP_BRANCH_RELATIVE
from capstone.x86_const import X86_OP_IMM

from tools.matching.pe import REFERENCE, code_at, digest, file_hash, open_image
from tools.matching.unwind import checked_runtime_range, runtime_entries


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


def validate_runtime_body(decoder, data, start):
    # MSVC can include an INT3 after a funclet return in the .pdata extent.
    # Exclude trailing traps from control-flow validation only. The matcher
    # still compares every byte in the original and candidate ranges.
    body = data.rstrip(b"\xcc")
    instructions = list(decoder.disasm(body, start))
    end = start + len(body)
    if (
        not instructions or instructions[-1].address + instructions[-1].size != end
        or instructions[-1].mnemonic != "ret" or instructions[-1].op_str
    ):
        raise ValueError(f"Runtime-function range at RVA {start:#x} has no complete decoded body")
    boundaries = {instruction.address for instruction in instructions}
    for instruction in instructions:
        if {CS_GRP_INT, CS_GRP_IRET}.intersection(instruction.groups) or instruction.mnemonic in {
            "hlt", "ud2", "syscall", "sysret", "retf", "retfq", "sti", "cli", "in", "out"
        }:
            raise ValueError(f"Unsupported instruction at RVA {instruction.address:#x}")
        if (
            CS_GRP_CALL not in instruction.groups
            and {CS_GRP_JUMP, CS_GRP_BRANCH_RELATIVE}.intersection(instruction.groups)
        ):
            operand = instruction.operands[0]
            if operand.type != X86_OP_IMM or operand.imm not in boundaries:
                raise ValueError(f"Branch escapes verified boundaries at RVA {instruction.address:#x}")


def compare_function(original, candidate, record, exports, decoder, unwind_tables):
    start, end = record["start_rva"], record["end_rva"]
    offset, expected = code_at(original, start, end - start)
    if digest(expected) != record["original_sha256"]:
        raise ValueError(f"Original range hash mismatch at RVA {start:#x}")
    symbol = record["candidate_export"]
    entry = exports.get(symbol)
    if entry is None or entry.forwarder:
        raise ValueError(f"Missing direct candidate export {symbol}")
    rva = entry.address
    boundary = record.get("boundary_method", "leaf")
    evidence = {}
    if boundary == "pe-runtime-function":
        original_entries, candidate_entries = unwind_tables
        verified_end, original_unwind = checked_runtime_range(
            original, original_entries, start, decoder
        )
        if verified_end != end:
            raise ValueError(f"Original runtime-function does not end at recorded RVA {end:#x}")
        candidate_end, candidate_unwind = checked_runtime_range(
            candidate, candidate_entries, rva, decoder
        )
        size = candidate_end - rva
        _, actual = code_at(candidate, rva, size)
        validate_runtime_body(decoder, expected, start)
        validate_runtime_body(decoder, actual, rva)
        method = "raw-pe-runtime-function-bytes"
        evidence = {"original_unwind_rva": original_unwind, "candidate_unwind_rva": candidate_unwind}
    elif boundary == "leaf":
        if leaf_size(original, start, decoder) != len(expected):
            raise ValueError(f"Original leaf does not end at recorded RVA {end:#x}")
        size = leaf_size(candidate, rva, decoder)
        _, actual = code_at(candidate, rva, size)
        method = "raw-pe-leaf-bytes"
    else:
        raise ValueError(f"Unrecognized boundary method {boundary!r}")
    result = {
        "start_rva": start,
        "end_rva": end,
        "file_offset": offset,
        "candidate_export": symbol,
        "candidate_rva": rva,
        "method": method,
        **evidence,
    }
    return {**result, **byte_comparison(decoder, expected, actual, start, rva)}


def byte_comparison(decoder, expected, actual, start, candidate_start):
    prefix = next(
        (i for i, pair in enumerate(zip(expected, actual)) if pair[0] != pair[1]),
        min(len(expected), len(actual)),
    )
    equal = expected == actual
    result = {
        "original_size": len(expected),
        "candidate_size": len(actual),
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
            "actual_instruction": instruction_at(decoder, actual, candidate_start, prefix),
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
        mapped = [record for record in manifest["functions"] if record.get("candidate_export")]
        unwind_tables = None
        if any(record.get("boundary_method") == "pe-runtime-function" for record in mapped):
            unwind_tables = runtime_entries(original), runtime_entries(build)
        results = [
            compare_function(original, build, record, exports, decoder, unwind_tables)
            for record in mapped
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
