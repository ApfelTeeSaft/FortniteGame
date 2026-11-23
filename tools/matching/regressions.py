"""Match-state transitions between a Git revision's manifests and the working tree.

A regression is an address that had an exact function at the base revision and has none now.
Functions are compared by start RVA: when the linker folds identical bodies, the manifest keeps
one entry per address under one of the folded names, and that name may change between
revisions (a rename, reported separately, is not a regression). Exit status 1 if there is any
regression, so the check can gate a commit.

Usage:
  python tools/matching/regressions.py            # against HEAD
  python tools/matching/regressions.py --base REV # against another revision
  python tools/matching/regressions.py -v         # also list every transition and rename
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "matching"))
import manifest_io  # noqa: E402


def states(docs: list[dict]) -> dict[str, dict[str, str | None]]:
    """start RVA -> {name: match} over all manifests."""
    out: dict[str, dict[str, str | None]] = defaultdict(dict)
    for d in docs:
        for e in manifest_io.expand(d):
            if e.get("start_rva"):
                out[e["start_rva"]][e["name"]] = e.get("match")
    return out


def at_revision(rev: str, rel: str) -> dict | None:
    r = subprocess.run(["git", "show", f"{rev}:{rel}"], cwd=ROOT, capture_output=True)
    return json.loads(r.stdout) if r.returncode == 0 else None


def best(entry: dict[str, str | None] | None) -> str | None:
    order = ["exact", "relocation-equivalent", "instruction-equivalent", "partial", "unmatched", "unknown",
             "unimplemented"]
    vals = [v for v in (entry or {}).values() if v in order]
    return min(vals, key=order.index) if vals else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="HEAD")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    paths = [ROOT / "analysis" / "functions.json"] + sorted((ROOT / "analysis").glob("functions-*.json"))
    rels = [p.relative_to(ROOT).as_posix() for p in paths]
    old = states([d for d in (at_revision(args.base, r) for r in rels) if d])
    new = states([json.loads(p.read_text(encoding="utf-8")) for p in paths])
    moves, renamed, regressions = Counter(), [], []
    for rva in sorted(set(old) | set(new)):
        a, b = best(old.get(rva)), best(new.get(rva))
        names_a, names_b = sorted((old.get(rva) or {})), sorted((new.get(rva) or {}))
        if a == b:
            if a == "exact" and names_a != names_b:
                renamed.append((rva, names_a, names_b))
            continue
        moves[(a, b)] += 1
        if a == "exact":
            regressions.append((rva, names_a, b))
        if args.verbose:
            print(f"{rva} {', '.join(names_b or names_a)}: {a} -> {b}")
    for (a, b), n in sorted(moves.items(), key=lambda kv: (-kv[1], str(kv[0]))):
        print(f"{n:6d}  {a} -> {b}")
    if renamed:
        print(f"{len(renamed)} exact address(es) now under another folded name")
        if args.verbose:
            for rva, a, b in renamed:
                print(f"  {rva}: {', '.join(a)} -> {', '.join(b)}")
    if regressions:
        print(f"{len(regressions)} regression(s) against {args.base}:")
        for rva, names, b in regressions[:50]:
            print(f"  {rva} {', '.join(names)}: exact -> {b}")
        return 1
    print(f"no regressions against {args.base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
