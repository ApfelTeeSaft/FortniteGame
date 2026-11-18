"""Verify positive and negative comparisons with the compiled synthetic probe."""

import argparse
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from capstone import Cs, CS_ARCH_X86, CS_MODE_64

from tools.matching.coff import HEADER, SECTION, funclet_bytes
from tools.matching.compare import compare, leaf_size, validate_runtime_body
from tools.matching.pe import code_at, digest, file_hash, open_image
from tools.matching.trace_flow import trace
from tools.matching.unwind import checked_runtime_range, prologue_matches, read_prologue, runtime_entries
from tools.progress.generate import counts


def test_probe(probe, alternate_toolchain, symbol, boundary):
    decoder = Cs(CS_ARCH_X86, CS_MODE_64)
    decoder.detail = True
    with open_image(probe) as image:
        image.parse_data_directories(directories=[0])
        start = next(
            entry.address for entry in image.DIRECTORY_ENTRY_EXPORT.symbols
            if entry.name == symbol.encode("ascii")
        )
        if boundary == "pe-runtime-function":
            end, unwind = checked_runtime_range(image, runtime_entries(image), start, decoder)
            size = end - start
        else:
            size = leaf_size(image, start, decoder)
        _, data = code_at(image, start, size)
        if symbol == "ProbeSimd":
            prologue = read_prologue(image, (start, start + size, unwind))
            if prologue is None or not any(
                op[0] == "save" and op[1].startswith("xmm")
                for group in prologue.operations.values() for op in group
            ):
                raise RuntimeError("SIMD probe must save a nonvolatile XMM register")
            for instruction in decoder.disasm(data[:prologue.size], 0):
                if instruction.mnemonic in {"movaps", "movups", "movdqa", "movdqu", "movapd", "movupd"}:
                    # Change only the SIMD store's source register.
                    mutated = bytearray(data)
                    modrm = instruction.address + instruction.modrm_offset
                    mutated[modrm] ^= 0x08
                    if prologue_matches(decoder, mutated, prologue):
                        raise RuntimeError("Changed SIMD save must fail unwind validation")
                    break
            else:
                raise RuntimeError("SIMD store not found in probe")

    record = {
        "start_rva": start,
        "end_rva": start + size,
        "original_sha256": digest(data),
        "candidate_export": symbol,
        "boundary_method": boundary,
    }
    manifest = {
        "schema_version": 1,
        "reference_sha256": file_hash(probe),
        "functions": [record],
    }
    report = compare(probe, probe, manifest)
    if not report["whole_file_exact"] or report["functions"][0]["status"] != "exact":
        raise RuntimeError(f"{symbol} must match itself")
    record.update({
        "eligible": True,
        "status": "exact",
        "source": "FortniteGameCode/Probe.cpp",
        "verification": report["functions"][0],
    })
    if counts(manifest)["exact"] != 1:
        raise RuntimeError(f"{symbol} must pass progress verification")

    if alternate_toolchain:
        alternate = compare(probe, alternate_toolchain, manifest)
        print(f"{symbol} alternate toolchain: {alternate['functions'][0]['status']}")

    record["candidate_export"] = symbol + "Variant"
    mismatch = compare(probe, probe, manifest)["functions"][0]
    if mismatch["status"] not in {"partial", "unmatched"} or not mismatch.get("first_difference"):
        raise RuntimeError("Different probe implementations must produce a mismatch")

    record["end_rva"] -= 1
    record["original_sha256"] = digest(data[:-1])
    try:
        compare(probe, probe, manifest)
    except ValueError as error:
        if "does not end at recorded RVA" not in str(error):
            raise
    else:
        raise RuntimeError("A truncated reference function must be rejected")
    print(f"{symbol} passed exact, mismatch, and truncated-range checks.")


def test_funclet_object(path):
    raw = path.read_bytes()
    symbol = "DelayLoadFilterProbe$filt$0"
    code = funclet_bytes(raw, symbol)
    decoder = Cs(CS_ARCH_X86, CS_MODE_64)
    decoder.detail = True
    validate_runtime_body(decoder, code, 0)
    for sample in (b"", raw[:HEADER.size - 1], raw[:-1]):
        try:
            funclet_bytes(sample, symbol)
        except ValueError:
            pass
        else:
            raise RuntimeError("Truncated COFF object must be rejected")

    # A relocation in the code section invalidates a raw object-code match.
    machine, count, _, _, _, _, _ = HEADER.unpack_from(raw)
    if machine != 0x8664:
        raise RuntimeError("Expected AMD64 fixture")
    for index in range(count):
        offset = HEADER.size + index * SECTION.size
        fields = list(SECTION.unpack_from(raw, offset))
        if not fields[-1] & 0x20000000 or fields[3] != len(code):
            continue
        if raw[fields[4]:fields[4] + fields[3]] != code:
            continue
        mutated = bytearray(raw)
        fields[5] = fields[4]
        fields[7] = 1
        SECTION.pack_into(mutated, offset, *fields)
        try:
            funclet_bytes(mutated, symbol)
        except ValueError as error:
            if "no relocations" not in str(error):
                raise
        else:
            raise RuntimeError("Relocatable code must be rejected")
        break
    else:
        raise RuntimeError("Expected code fixture section not found")
    print("COFF checks passed for truncation and relocatable code.")


def test_trace(probe):
    with open_image(probe) as image:
        image.parse_data_directories(directories=[0])
        start = next(
            entry.address for entry in image.DIRECTORY_ENTRY_EXPORT.symbols
            if entry.name == b"ProbeBranch"
        )
    report = trace(probe, start, block_limit=32)
    blocks = report["blocks"]
    if report["limit_reached"] or any(row.get("error") for row in blocks):
        raise RuntimeError("The synthetic branch trace must complete within its limits")
    if not any(edge["kind"] == "call" for row in blocks for edge in row["edges"]):
        raise RuntimeError("The trace must discover the synthetic direct call")
    if not any(row.get("stop") == "return" for row in blocks):
        raise RuntimeError("The trace must reach a synthetic return")
    limited = trace(probe, start, block_limit=1)
    if not limited["limit_reached"] or not limited["pending_rvas"]:
        raise RuntimeError("A limited trace must report pending addresses")
    print("Static trace checks passed for direct calls, returns, and traversal limits.")


def test_relative_loop():
    # LOOP belongs to Capstone's branch-relative group but not its jump group.
    # A nearby return cannot establish a straight-line leaf for this input.
    code = bytes.fromhex("e2 fe c3")
    image = SimpleNamespace(sections=[
        SimpleNamespace(VirtualAddress=0x1000, SizeOfRawData=3, Misc_VirtualSize=3),
    ])
    decoder = Cs(CS_ARCH_X86, CS_MODE_64)
    decoder.detail = True
    with patch("tools.matching.compare.code_at", return_value=(0, code)):
        try:
            leaf_size(image, 0x1000, decoder)
        except ValueError:
            pass
        else:
            raise RuntimeError("A relative LOOP must be rejected by the leaf matcher")
    print("Relative LOOP rejected by the straight-line leaf matcher.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("probe", type=Path)
    parser.add_argument("--alternate-toolchain", type=Path)
    parser.add_argument("--funclet-object", type=Path)
    args = parser.parse_args()
    test_probe(args.probe, args.alternate_toolchain, "ProbeScale", "leaf")
    test_probe(args.probe, args.alternate_toolchain, "ProbeBranch", "pe-runtime-function")
    test_probe(args.probe, args.alternate_toolchain, "ProbeFrame", "pe-runtime-function")
    test_probe(args.probe, args.alternate_toolchain, "ProbeSimd", "pe-runtime-function")
    test_trace(args.probe)
    test_relative_loop()
    if args.funclet_object:
        test_funclet_object(args.funclet_object)


if __name__ == "__main__":
    main()
