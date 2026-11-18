"""Trace bounded direct control-flow edges in file-backed executable bytes.

This is static discovery. Decodable instructions and branch edges do not establish
original function boundaries, runtime reachability, or valid transformed code.
"""

import argparse
from collections import Counter, deque
import json
from pathlib import Path

from capstone import (
    Cs, CS_ARCH_X86, CS_MODE_64, CS_GRP_BRANCH_RELATIVE, CS_GRP_CALL,
    CS_GRP_INT, CS_GRP_IRET, CS_GRP_JUMP, CS_GRP_RET,
)
from capstone.x86_const import X86_OP_IMM

from tools.matching.pe import REFERENCE, code_at, digest, file_hash, open_image


UNSUPPORTED = {"hlt", "ud2", "syscall", "sysret", "retf", "retfq", "sti", "cli", "in", "out"}


def section_index(image, rva):
    for index, section in enumerate(image.sections):
        if section.VirtualAddress <= rva < section.VirtualAddress + min(
            section.SizeOfRawData, section.Misc_VirtualSize
        ):
            return index
    return None


def block(image, decoder, start, instruction_limit):
    index = section_index(image, start)
    if index is None:
        return {"start_rva": start, "error": "Unbacked address", "edges": []}
    section = image.sections[index]
    size = min(
        instruction_limit * 15,
        section.VirtualAddress + min(section.SizeOfRawData, section.Misc_VirtualSize) - start,
    )
    try:
        offset, data = code_at(image, start, size)
    except ValueError:
        return {"start_rva": start, "error": "Non-executable address", "edges": []}

    edges = []
    counts = Counter()
    instruction_count = 0
    end = start
    stop = "instruction limit"
    for instruction in decoder.disasm(data, start):
        end = instruction.address + instruction.size
        if instruction.mnemonic in UNSUPPORTED or {
            CS_GRP_INT, CS_GRP_IRET
        }.intersection(instruction.groups):
            stop = "unsupported instruction"
            break
        counts[instruction.mnemonic] += 1
        instruction_count += 1
        if CS_GRP_RET in instruction.groups:
            stop = "return"
            break
        if {CS_GRP_CALL, CS_GRP_JUMP, CS_GRP_BRANCH_RELATIVE}.intersection(instruction.groups):
            if instruction.operands[0].type == X86_OP_IMM:
                edges.append({
                    "instruction_rva": instruction.address,
                    "kind": "call" if CS_GRP_CALL in instruction.groups else "branch",
                    "target_rva": instruction.operands[0].imm,
                })
                stop = "direct transfer"
            else:
                stop = "indirect transfer"
            if instruction.mnemonic != "jmp":
                edges.append({
                    "instruction_rva": instruction.address, "kind": "fallthrough",
                    "target_rva": end,
                })
            break
        if instruction_count >= instruction_limit:
            break
    else:
        stop = "undecodable or section end"

    return {
        "start_rva": start, "end_rva": end, "section_index": index,
        "file_offset": offset, "sha256": digest(data[:end - start]),
        "instruction_counts": dict(sorted(counts.items())),
        "stop": stop, "edges": edges,
    }


def trace(reference, start=None, *, block_limit=64, instruction_limit=64):
    if not 1 <= block_limit <= 4096 or not 1 <= instruction_limit <= 1024:
        raise ValueError("Trace limits exceed supported bounds")
    decoder = Cs(CS_ARCH_X86, CS_MODE_64)
    decoder.detail = True
    with open_image(reference) as image:
        root = image.OPTIONAL_HEADER.AddressOfEntryPoint if start is None else start
        pending = deque([root])
        discovered = {root}
        blocks = []
        while pending and len(blocks) < block_limit:
            current = pending.popleft()
            row = block(image, decoder, current, instruction_limit)
            for edge in row["edges"]:
                target = edge["target_rva"]
                edge["target_section_index"] = section_index(image, target)
                if target not in discovered:
                    discovered.add(target)
                    pending.append(target)
            blocks.append(row)
    return {
        "schema_version": 1,
        "reference_sha256": file_hash(reference),
        "scope": "Static direct-edge discovery with bounded decoding",
        "start_rva": root,
        "block_limit": block_limit,
        "instruction_limit": instruction_limit,
        "limit_reached": bool(pending),
        "pending_rvas": sorted(pending),
        "blocks": sorted(blocks, key=lambda row: row["start_rva"]),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=REFERENCE)
    parser.add_argument("--start", type=lambda value: int(value, 0))
    parser.add_argument("--blocks", type=int, default=64)
    args = parser.parse_args()
    print(json.dumps(trace(args.reference, args.start, block_limit=args.blocks), indent=2))


if __name__ == "__main__":
    main()
