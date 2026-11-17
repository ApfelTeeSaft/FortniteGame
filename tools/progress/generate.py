"""Render the checked-in exact-function progress badge from verified metadata."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "analysis/functions.json"
SVG = ROOT / "docs/images/byte-match-progress.svg"
STATUSES = (
    "exact", "relocation-equivalent", "instruction-equivalent", "partial",
    "unmatched", "unimplemented", "unknown",
)
SHA256 = re.compile(r"[0-9a-f]{64}")
RAW_METHODS = {
    "leaf": "raw-pe-leaf-bytes",
    "pe-runtime-function": "raw-pe-runtime-function-bytes",
    "amd64-coff-funclet": "raw-pe-to-coff-funclet-bytes",
}


def counts(manifest):
    reference = manifest["reference_sha256"]
    if manifest["schema_version"] != 1 or not SHA256.fullmatch(reference):
        raise ValueError("Invalid manifest schema or reference hash")
    totals = Counter(dict.fromkeys(STATUSES, 0))
    previous_end = 0
    for record in sorted(manifest["functions"], key=lambda entry: entry["start_rva"]):
        start, end = record["start_rva"], record["end_rva"]
        if not 0 < start < end or start < previous_end:
            raise ValueError(f"Invalid or overlapping function range at {start:#x}")
        previous_end = end
        status = record["status"]
        if status not in STATUSES:
            raise ValueError(f"Unsupported function status {status}")
        if type(record["eligible"]) is not bool:
            raise ValueError(f"Missing eligibility decision at {start:#x}")
        if status == "exact":
            verification = record["verification"]
            original = record["original_sha256"]
            boundary = record.get("boundary_method", "leaf")
            candidate_key, artifact_hash = (
                ("candidate_symbol", "candidate_object_sha256")
                if boundary == "amd64-coff-funclet"
                else ("candidate_export", "candidate_image_sha256")
            )
            required = {
                "start_rva": start,
                "end_rva": end,
                "original_size": end - start,
                "candidate_size": end - start,
                candidate_key: record[candidate_key],
                "original_sha256": original,
                "candidate_sha256": original,
                "reference_image_sha256": reference,
                "method": RAW_METHODS[boundary],
                "status": "exact",
            }
            if (
                not SHA256.fullmatch(original)
                or not SHA256.fullmatch(verification.get(artifact_hash, ""))
                or not record.get("source")
                or any(verification.get(key) != value for key, value in required.items())
            ):
                raise ValueError(f"Missing raw byte verification at {start:#x}")
        if record["eligible"]:
            totals[status] += 1
    return totals


def render(totals, reference):
    exact, total = totals["exact"], sum(totals.values())
    percentage = f"{exact / total:.2%}" if total else "N/A"
    coverage = f"{520 * exact / total:.3f}" if total else "0"
    scope = "Identified eligible functions" if total else "No eligible ranges confirmed yet"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 576 160" role="img" aria-labelledby="title summary">
  <title id="title">Fortnite 2.5 — Exact Function Matches</title>
  <desc id="summary">{exact} of {total} identified eligible functions. Exact byte matches: {percentage}.</desc>
  <rect width="576" height="160" rx="14" fill="#111b2c"/>
  <text x="28" y="36" fill="#f4f8ff" font-family="system-ui,sans-serif" font-size="19" font-weight="700">Fortnite 2.5 — Exact Function Matches</text>
  <text x="28" y="74" fill="#f4f8ff" font-family="ui-monospace,monospace" font-size="25" font-weight="700">{exact:,} / {total:,}</text>
  <text x="548" y="74" fill="#77e4cb" font-family="ui-monospace,monospace" font-size="21" text-anchor="end">{percentage}</text>
  <rect x="28" y="92" width="520" height="12" rx="6" fill="#35445b"/>
  <rect x="28" y="92" width="{coverage}" height="12" rx="6" fill="#50dac0"/>
  <text x="28" y="133" fill="#b9c6da" font-family="system-ui,sans-serif" font-size="13">{scope}</text>
  <text x="548" y="133" fill="#b9c6da" font-family="ui-monospace,monospace" font-size="12" text-anchor="end">PE {reference[:12]}</text>
</svg>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    totals = counts(manifest)
    expected = render(totals, manifest["reference_sha256"])
    if args.verify:
        if not SVG.exists() or SVG.read_text(encoding="utf-8") != expected:
            parser.exit(1, "Progress SVG is missing or stale\n")
    else:
        SVG.parent.mkdir(parents=True, exist_ok=True)
        SVG.write_text(expected, encoding="utf-8", newline="\n")
    print(json.dumps({
        "eligible": sum(totals.values()),
        "excluded": len(manifest["functions"]) - sum(totals.values()),
        **totals,
    }, indent=2))


if __name__ == "__main__":
    main()
