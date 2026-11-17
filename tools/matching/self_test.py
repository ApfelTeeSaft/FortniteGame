"""Verify positive and negative comparisons with the compiled synthetic probe."""

import argparse
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_64

from tools.matching.compare import compare, leaf_size
from tools.matching.pe import code_at, digest, file_hash, open_image
from tools.matching.unwind import checked_runtime_range, runtime_entries
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
            end, _ = checked_runtime_range(image, runtime_entries(image), start, decoder)
            size = end - start
        else:
            size = leaf_size(image, start, decoder)
        _, data = code_at(image, start, size)

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("probe", type=Path)
    parser.add_argument("--alternate-toolchain", type=Path)
    args = parser.parse_args()
    test_probe(args.probe, args.alternate_toolchain, "ProbeScale", "leaf")
    test_probe(args.probe, args.alternate_toolchain, "ProbeBranch", "pe-runtime-function")
    test_probe(args.probe, args.alternate_toolchain, "ProbeFrame", "pe-runtime-function")


if __name__ == "__main__":
    main()
