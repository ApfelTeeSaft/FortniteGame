"""Ingest a decrypted image of the reference build and validate it.

Usage:
  python tools/matching/ingest_dump.py --dump <path to .dmp / raw / PE dump>

Writes (local only, ignored by Git):
  local-output/reference-dump/FortniteClient-Win64-Shipping.decrypted.image
      RVA-indexed module image normalized to the preferred base 0x140000000
  local-output/reference-dump/FortniteClient-Win64-Shipping.decrypted.present
      byte presence map (written only when the dump has gaps)
Writes (publishable):
  analysis/decrypted-reference.json   hashes, validation and coverage statistics

The image is accepted only if it agrees byte for byte with the original over the
linker-produced extents of the plaintext data (validation_extents): .rdata from the
end of the import address table to the end of the export directory, the exception
directory, and the resource directory. Every differing byte outside those extents is
reported with the region it falls in (runtime-bound IAT, protector-owned section
slack). Coverage counts primary .pdata functions whose prologue agrees with their
unwind record in the decrypted image.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dump import DecryptedImage, detect_delta, dir64_sites, load_dump, normalize, sha256  # noqa: E402
from pe import DEFAULT_REFERENCE, REPO_ROOT, PEImage  # noqa: E402
from unwind import UNW_FLAG_CHAININFO, parse_unwind, verify_prologue  # noqa: E402

LOCAL_DIR = REPO_ROOT / "local-output" / "reference-dump"
IMAGE_PATH = LOCAL_DIR / "FortniteClient-Win64-Shipping.decrypted.image"
PRESENT_PATH = LOCAL_DIR / "FortniteClient-Win64-Shipping.decrypted.present"
REPORT = REPO_ROOT / "analysis" / "decrypted-reference.json"
# Sections that are plaintext and read-only in the original file.
PLAINTEXT_SECTIONS = (".rdata", ".pdata", "_RDATA", ".rsrc", ".gfids")


def iat_extent(original: PEImage) -> tuple[int, int]:
    """Original MSVC IAT at the start of .rdata: qwords holding 0, an ordinal, or a hint/name RVA."""
    rd = next(s for s in original.sections if s.name == ".rdata")
    rva = rd.rva
    while True:
        v = int.from_bytes(original.read(rva, 8), "little")
        if not (v == 0 or v >> 63 or (v < original.size_of_image and original.section_of(v) is not None)):
            break
        rva += 8
    return rd.rva, rva


def validation_extents(original: PEImage) -> dict[str, tuple[int, int]]:
    rd = next(s for s in original.sections if s.name == ".rdata")
    exp_rva, exp_size = original.directory(0)
    exc_rva, exc_size = original.directory(3)
    res_rva, res_size = original.directory(2)
    iat_lo, iat_hi = iat_extent(original)
    assert iat_lo == rd.rva and rd.rva <= exp_rva < rd.rva + rd.vsize
    return {
        ".rdata (IAT end .. export directory end)": (iat_hi, exp_rva + exp_size),
        ".pdata (exception directory)": (exc_rva, exc_rva + exc_size),
        ".rsrc (resource directory)": (res_rva, res_rva + res_size),
    }


def diff_count(original: PEImage, img, lo: int, hi: int) -> tuple[int, int]:
    """(differing bytes, missing bytes) between file and normalized dump over [lo, hi)."""
    fb = original.read(lo, hi - lo)
    db = bytes(img.data[lo:hi])
    pb = img.present[lo:hi]
    diff = missing = 0
    for o in range(0, hi - lo, 0x1000):
        a, b, p = fb[o:o + 0x1000], db[o:o + 0x1000], pb[o:o + 0x1000]
        if a == b and p.count(1) == len(p):
            continue
        missing += p.count(0)
        diff += sum(1 for x, y, z in zip(a, b, p) if z and x != y)
    return diff, missing


def account_differences(original: PEImage, img, extents: dict) -> dict:
    """Locate every differing byte in the plaintext sections and name the region it is in."""
    iat_lo, iat_hi = iat_extent(original)
    out = {}
    for s in original.sections:
        if s.name not in PLAINTEXT_SECTIONS:
            continue
        n = min(s.rawsize, s.vsize or s.rawsize)
        diff, missing = diff_count(original, img, s.rva, s.rva + n)
        regions = {"runtime-bound IAT": 0, "inside validation extent": 0, "outside extents (section slack)": 0}
        if diff:
            fb = original.read(s.rva, n)
            db = bytes(img.data[s.rva:s.rva + n])
            for o in range(n):
                if fb[o] != db[o]:
                    r = s.rva + o
                    if iat_lo <= r < iat_hi:
                        regions["runtime-bound IAT"] += 1
                    elif any(lo <= r < hi for lo, hi in extents.values()):
                        regions["inside validation extent"] += 1
                    else:
                        regions["outside extents (section slack)"] += 1
        out[s.name] = {"bytes": n, "differing": diff, "missing": missing, "differing_by_region": regions}
    return out


def coverage(original: PEImage, dimg: DecryptedImage) -> dict:
    text = original.sections[0]
    file_v, dump_v = Counter(), Counter()
    transitions = Counter()
    for rf in original.runtime_functions():
        if not text.contains_rva(rf.begin):
            continue
        ui = parse_unwind(original, rf.unwind)
        if ui.flags & UNW_FLAG_CHAININFO:
            continue
        fv, _ = verify_prologue(original, rf.begin, ui)
        try:
            dv, _ = verify_prologue(dimg, rf.begin, ui)
        except ValueError:
            dv = "not-present"
        file_v[fv] += 1
        dump_v[dv] += 1
        transitions[f"{fv}->{dv}"] += 1
    with_codes = sum(v for k, v in dump_v.items() if k != "no-codes")
    return {
        "primary_functions": sum(file_v.values()),
        "file_verdicts": dict(sorted(file_v.items())),
        "decrypted_verdicts": dict(sorted(dump_v.items())),
        "decrypted_prologue_verified_ratio": round(dump_v["verified"] / with_codes, 6) if with_codes else None,
        "transitions": dict(sorted(transitions.items())),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", required=True)
    args = ap.parse_args()
    dump_path = Path(args.dump).resolve()
    original = PEImage(DEFAULT_REFERENCE)
    img = load_dump(dump_path, original)
    sites = dir64_sites(original)
    delta, votes, sampled = detect_delta(original, img, sites)
    if sampled == 0 or votes / sampled < 0.99:
        print(f"cannot establish a single load delta ({votes}/{sampled} votes)", file=sys.stderr)
        return 1
    adjusted = normalize(img, sites, delta)
    extents = validation_extents(original)
    checked = {}
    for name, (lo, hi) in extents.items():
        diff, missing = diff_count(original, img, lo, hi)
        checked[name] = {"start_rva": f"0x{lo:08X}", "end_rva": f"0x{hi:08X}", "bytes": hi - lo,
                         "differing": diff, "missing": missing}
    ok = all(v["differing"] == 0 and v["missing"] == 0 for v in checked.values())
    accounting = account_differences(original, img, extents)
    dimg = DecryptedImage(original, bytes(img.data), None if img.present.count(0) == 0 else bytes(img.present))
    text = original.sections[0]
    funclets_ok = all(dimg.read(r, 0x2A) == original.read(r, 0x2A) for r in (0x02DAE750, 0x02DAE780))
    cov = coverage(original, dimg)
    report = {
        "schema_version": 1,
        "generated_by": "tools/matching/ingest_dump.py",
        "reference_sha256": original.sha256(),
        "dump": {"file_name": dump_path.name, "sha256": sha256(dump_path.read_bytes()),
                 "size": dump_path.stat().st_size, "format": img.source_format, "notes": img.notes},
        "normalization": {
            "preferred_base": f"0x{original.image_base:016X}",
            "load_delta": f"0x{delta:016X}",
            "delta_votes": votes, "delta_sampled_sites": sampled,
            "dir64_sites_total": len(sites), "dir64_sites_adjusted": adjusted,
        },
        "normalized_image": {
            "size": len(img.data), "sha256": sha256(bytes(img.data)),
            "main_text_sha256": sha256(bytes(img.data[text.rva:text.rva + text.rawsize])),
            "bytes_missing": img.present.count(0),
        },
        "validation": {
            "rule": "byte identity over linker-produced plaintext extents after un-rebasing DIR64 sites",
            "extents": checked,
            "difference_accounting": accounting,
            "plaintext_funclets_identical": funclets_ok,
            "accepted": ok and funclets_ok,
        },
        "coverage": cov,
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not report["validation"]["accepted"]:
        print("REJECTED: dump does not agree with the reference's plaintext sections", file=sys.stderr)
        return 1
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_PATH.write_bytes(bytes(img.data))
    if img.present.count(0):
        PRESENT_PATH.write_bytes(bytes(img.present))
    elif PRESENT_PATH.exists():
        PRESENT_PATH.unlink()
    print(f"accepted; normalized image written to {IMAGE_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
