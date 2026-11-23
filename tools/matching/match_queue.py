"""Verification queue: every compiled function in the denominator that is not exact, grouped by
the cause compare.py recorded, so byte-matching work can be scheduled apart from reconstruction.

Causes:
- an unresolved relocation, by symbol kind (string literal, StaticClass, StaticEnum, ...);
- differing bytes (partial / unmatched), by category.

Writes analysis/match-queue.json (stage counts, then groups by size with a few example RVAs) and
prints the largest groups. Deterministic: groups sort by count, then cause.

Usage:
  python tools/matching/match_queue.py              # write the queue and print the top groups
  python tools/matching/match_queue.py --list KEY   # print every RVA and name of the group KEY
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "matching"))
import manifest_io  # noqa: E402

QUEUE = ROOT / "analysis" / "match-queue.json"
PENDING = ("relocation-equivalent", "instruction-equivalent", "partial", "unmatched")

KINDS = [
    (re.compile(r"^\$SG\d+$"), "string literal ($SG, per-occurrence copy)"),
    (re.compile(r"^\?\?_C@"), "pooled string literal (??_C@)"),
    (re.compile(r"^\?StaticClass@"), "<Class>::StaticClass"),
    (re.compile(r"_StaticEnum@@YAPEAVUEnum@@XZ$"), "<Enum>_StaticEnum"),
    (re.compile(r"^\?StaticStruct@"), "<Struct>::StaticStruct"),
    (re.compile(r"^\?\?\$InternalConstructor@"), "InternalConstructor<Class>"),
    (re.compile(r"^\?\?\$InternalVTableHelperCtorCaller@"), "InternalVTableHelperCtorCaller<Class>"),
    (re.compile(r"^\?StaticRegisterNatives"), "StaticRegisterNatives<Class>"),
    (re.compile(r"^\?FuncParams@"), "FFunctionParams record"),
    (re.compile(r"^\?Return(Function|Struct|Enum|Package)@"), "creator singleton (.bss)"),
    (re.compile(r"^\?(OuterClass|Singleton)@"), "singleton (.bss)"),
    (re.compile(r"^\?Z_Construct_U"), "Z_Construct_* creator"),
    (re.compile(r"^\?\?[04]"), "constructor / assignment"),
    (re.compile(r"GlobalVectorConstants"), "GlobalVectorConstants"),
]


def kind(symbol: str) -> str:
    for rx, k in KINDS:
        if rx.search(symbol):
            return k
    return "other: " + symbol[:60]


def causes(e: dict) -> list[str]:
    d = e.get("byte_diff") or {}
    out = sorted({kind(u["symbol"]) for u in d.get("unresolved_relocations") or []})
    if d.get("differing_bytes"):
        out.append("differing bytes")
    return out or ["no recorded cause"]


def load_entries() -> list[dict]:
    out = []
    for p in [ROOT / "analysis" / "functions.json"] + sorted((ROOT / "analysis").glob("functions-*.json")):
        out += manifest_io.expand(json.loads(p.read_text(encoding="utf-8")))
    return out


def build(entries: list[dict]) -> dict:
    counted = [e for e in entries if e.get("start_rva") and e.get("in_denominator")]
    groups = defaultdict(list)
    for e in counted:
        if e.get("match") in PENDING:
            key = f"{e.get('category')} | {' + '.join(causes(e))}"
            groups[key].append((e["start_rva"], e["name"], e["match"]))
    rows = []
    for key, members in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        members.sort()
        states = defaultdict(int)
        for _, _, s in members:
            states[s] += 1
        rows.append({"key": key, "count": len(members), "states": dict(sorted(states.items())),
                     "examples": [f"{r} {n}" for r, n, _ in members[:5]]})
    return {
        "schema_version": 1,
        "generated_by": "tools/matching/match_queue.py",
        "pending_states": list(PENDING),
        "total": sum(r["count"] for r in rows),
        "groups": rows,
    }, groups


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", metavar="KEY", help="print the members of one group")
    args = ap.parse_args()
    doc, groups = build(load_entries())
    if args.list:
        for r, n, s in sorted(groups.get(args.list, [])):
            print(r, s, n)
        return 0 if args.list in groups else 1
    QUEUE.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    print(f"{doc['total']} functions to verify, {len(doc['groups'])} groups -> {QUEUE.relative_to(ROOT)}")
    for r in doc["groups"][:15]:
        print(f"  {r['count']:6d}  {r['key']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
