"""Match-state transitions between a Git revision's manifests and the working tree.

A regression is a function that was exact at the base revision and is not exact now (or is gone).
Exit status 1 if there is any, so the check can gate a commit.

Usage:
  python tools/matching/regressions.py            # against HEAD
  python tools/matching/regressions.py --base REV # against another revision
  python tools/matching/regressions.py -v         # also list every transition
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "matching"))
import manifest_io  # noqa: E402


def states(docs: list[dict]) -> dict[tuple[str, str], str]:
    out = {}
    for d in docs:
        for e in manifest_io.expand(d):
            if e.get("start_rva"):
                out[(e["start_rva"], e["name"])] = e.get("match")
    return out


def at_revision(rev: str, rel: str) -> dict | None:
    r = subprocess.run(["git", "show", f"{rev}:{rel}"], cwd=ROOT, capture_output=True)
    return json.loads(r.stdout) if r.returncode == 0 else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="HEAD")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    paths = [ROOT / "analysis" / "functions.json"] + sorted((ROOT / "analysis").glob("functions-*.json"))
    rels = [p.relative_to(ROOT).as_posix() for p in paths]
    old = states([d for d in (at_revision(args.base, r) for r in rels) if d])
    new = states([json.loads(p.read_text(encoding="utf-8")) for p in paths])
    moves = Counter()
    regressions = []
    for k in sorted(set(old) | set(new)):
        a, b = old.get(k), new.get(k)
        if a == b:
            continue
        moves[(a, b)] += 1
        if a == "exact":
            regressions.append((k, b))
        if args.verbose:
            print(f"{k[0]} {k[1]}: {a} -> {b}")
    for (a, b), n in sorted(moves.items(), key=lambda kv: (-kv[1], str(kv[0]))):
        print(f"{n:6d}  {a} -> {b}")
    if regressions:
        print(f"{len(regressions)} regression(s) against {args.base}:")
        for (rva, name), b in regressions[:50]:
            print(f"  {rva} {name}: exact -> {b}")
        return 1
    print(f"no regressions against {args.base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
