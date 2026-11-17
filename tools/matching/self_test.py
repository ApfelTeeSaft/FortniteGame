"""Verify positive and negative comparisons with the compiled synthetic probe."""

import argparse
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_64

from tools.matching.compare import compare, leaf_size
from tools.matching.pe import code_at, digest, file_hash, open_image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("probe", type=Path)
    parser.add_argument("--alternate-toolchain", type=Path)
    args = parser.parse_args()

    with open_image(args.probe) as image:
        image.parse_data_directories(directories=[0])
        start = next(
            entry.address for entry in image.DIRECTORY_ENTRY_EXPORT.symbols
            if entry.name == b"ProbeScale"
        )
        decoder = Cs(CS_ARCH_X86, CS_MODE_64)
        decoder.detail = True
        size = leaf_size(image, start, decoder)
        _, data = code_at(image, start, size)

    record = {
        "start_rva": start,
        "end_rva": start + size,
        "original_sha256": digest(data),
        "candidate_export": "ProbeScale",
    }
    manifest = {"reference_sha256": file_hash(args.probe), "functions": [record]}
    report = compare(args.probe, args.probe, manifest)
    if not report["whole_file_exact"] or report["functions"][0]["status"] != "exact":
        raise RuntimeError("Probe must match itself")

    if args.alternate_toolchain:
        alternate = compare(args.probe, args.alternate_toolchain, manifest)
        print(f"Alternate toolchain: {alternate['functions'][0]['status']}")

    record["candidate_export"] = "ProbeScaleVariant"
    mismatch = compare(args.probe, args.probe, manifest)["functions"][0]
    if mismatch["status"] not in {"partial", "unmatched"} or not mismatch.get("first_difference"):
        raise RuntimeError("Different probe implementations must produce a mismatch")

    record["end_rva"] -= 1
    record["original_sha256"] = digest(data[:-1])
    try:
        compare(args.probe, args.probe, manifest)
    except ValueError as error:
        if "does not end at recorded RVA" not in str(error):
            raise
    else:
        raise RuntimeError("A truncated reference function must be rejected")
    print("Synthetic self-test passed: exact match, mismatch, and truncated range rejection.")


if __name__ == "__main__":
    main()
