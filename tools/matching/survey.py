"""Survey which .pdata functions are plaintext on disk.

Writes ``analysis/plaintext-survey.json``: deterministic counts plus the list
of functions whose on-disk prologue agrees with their unwind record. The
survey publishes RVAs, sizes and hashes only, never original code bytes.

Usage:  python tools/matching/survey.py [--exe PATH] [--out PATH]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pe import DEFAULT_REFERENCE, REPO_ROOT, PEImage, entropy  # noqa: E402
from unwind import UNW_FLAG_CHAININFO, parse_unwind, verify_prologue  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=str(DEFAULT_REFERENCE))
    ap.add_argument("--out", default=str(REPO_ROOT / "analysis" / "plaintext-survey.json"))
    args = ap.parse_args()
    img = PEImage(args.exe)
    text = img.sections[0]
    assert text.name == ".text"
    rfs = img.runtime_functions()
    verdicts: Counter[str] = Counter()
    chained = 0
    plaintext = []
    for rf in rfs:
        if not text.contains_rva(rf.begin):
            verdicts["outside-main-text"] += 1
            continue
        ui = parse_unwind(img, rf.unwind & ~1 if rf.unwind & 1 else rf.unwind)
        if ui.flags & UNW_FLAG_CHAININFO:
            chained += 1
        verdict, detail = verify_prologue(img, rf.begin, ui)
        verdicts[verdict] += 1
        if verdict == "verified":
            body = img.read(rf.begin, rf.end - rf.begin)
            plaintext.append({
                "start_rva": f"{rf.begin:#010x}",
                "end_rva": f"{rf.end:#010x}",
                "size": rf.end - rf.begin,
                "unwind_rva": f"{rf.unwind:#010x}",
                "entropy": round(entropy(body), 3),
                "sha256": hashlib.sha256(body).hexdigest(),
                "evidence": detail,
            })
    out = {
        "schema_version": 1,
        "reference_sha256": img.sha256(),
        "method": ("Each .pdata RUNTIME_FUNCTION in the main .text is decoded; its "
                   "UNWIND_INFO prologue codes are compared with a linear capstone "
                   "decode of the on-disk bytes (push register, stack allocation "
                   "size, frame register, nonvolatile and XMM saves)."),
        "runtime_functions_total": len(rfs),
        "chained_unwind_entries_in_main_text": chained,
        "verdicts": dict(sorted(verdicts.items())),
        "prologue_verified_plaintext": plaintext,
    }
    Path(args.out).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "prologue_verified_plaintext"}, indent=2))
    print("plaintext functions:", len(plaintext))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
