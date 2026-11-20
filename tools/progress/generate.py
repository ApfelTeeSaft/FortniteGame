"""Generate docs/images/byte-match-progress.svg from verified manifest results.

Only entries whose match is ``exact`` count, and compare.py sets that state only
after a raw byte comparison. The function percentage never mixes in other states.

Usage:
  python tools/progress/generate.py            # write the SVG and print the summary
  python tools/progress/generate.py --verify   # exit 1 if the SVG is stale or the manifest is inconsistent
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "analysis" / "functions.json"
SVG = ROOT / "docs" / "images" / "byte-match-progress.svg"
STATES = ["exact", "relocation-equivalent", "instruction-equivalent", "partial",
          "unmatched", "unknown", "unimplemented"]


def validate(m: dict) -> list[str]:
    errors = []
    seen = set()
    for e in m["functions"]:
        rva = e.get("start_rva")
        if rva:
            if rva in seen:
                errors.append(f"duplicate start_rva {rva}")
            seen.add(rva)
        if e.get("match") not in STATES:
            errors.append(f"{rva or e['name']}: invalid match state {e.get('match')!r}")
        if e.get("start_rva") and "in_denominator" not in e:
            errors.append(f"{rva}: in_denominator missing; run tools/matching/compare.py")
        if e.get("match") == "exact":
            d = e.get("byte_diff") or {}
            if not rva or e.get("reference_state") not in ("plaintext", "decrypted"):
                errors.append(f"{rva}: exact requires a located plaintext or validated decrypted reference range")
            if d.get("differing_bytes") != 0 or d.get("unresolved_relocations"):
                errors.append(f"{rva}: exact requires zero differing bytes and no unresolved relocations")
            if d.get("reference_size") != d.get("candidate_size"):
                errors.append(f"{rva}: exact requires equal sizes")
    if not m["denominator"].get("count"):
        errors.append("denominator count missing; run tools/matching/compare.py")
    return errors


def summarize(m: dict) -> dict:
    located = [e for e in m["functions"] if e.get("start_rva")]
    counted = [e for e in located if e.get("in_denominator")]
    states = Counter(e["match"] for e in counted)
    exact = [e for e in counted if e["match"] == "exact"]
    outside = [e for e in located if not e.get("in_denominator")]
    structural = [e for e in located if e["match"] == "unknown" and e.get("structure")
                  and e["structure"].get("pdata_size_matches")
                  and e["structure"].get("unwind_codes_identical")
                  and e["structure"].get("scope_table", {}).get("identical", True)]
    return {
        "denominator": m["denominator"]["count"],
        "exact": len(exact),
        "exact_bytes": sum(int(e["end_rva"], 16) - int(e["start_rva"], 16) for e in exact),
        "states": {s: states.get(s, 0) for s in STATES},
        "exact_by_category": dict(sorted(Counter(e["category"] for e in exact).items())),
        "exact_vs_disk": sum(1 for e in exact if e["reference_state"] == "plaintext"),
        "exact_vs_decrypted": sum(1 for e in exact if e["reference_state"] == "decrypted"),
        "structure_only": len(structural),
        "unlocated": sum(1 for e in m["functions"] if not e.get("start_rva")
                         and e.get("reference_presence") != "not present in reference"),
        "not_present": sum(1 for e in m["functions"]
                           if e.get("reference_presence") == "not present in reference"),
        "outside_denominator": len(outside),
        "outside_denominator_exact": sum(1 for e in outside if e["match"] == "exact"),
        "manifest_digest": hashlib.sha256(
            json.dumps(m, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:12],
        "reference": m["reference"]["sha256"][:12],
    }


def pct(n: int, d: int) -> str:
    p = 100.0 * n / d if d else 0.0
    if p == 0:
        return "0%"
    if p < 0.01:
        return f"{p:.4f}%"
    return f"{p:.2f}%"


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def wrap(prefix: str, items: list[str], width: int) -> list[str]:
    """Greedy line packing of comma-separated items; continuation lines are indented."""
    out, cur = [], prefix
    for i, item in enumerate(items):
        piece = item + ("," if i < len(items) - 1 else "")
        if cur.strip() and len(cur) + 1 + len(piece) > width:
            out.append(cur)
            cur = "    " + piece
        else:
            cur = f"{cur} {piece}" if cur else piece
    out.append(cur)
    return out


def render(s: dict) -> str:
    labels = {"seh-filter-funclet": "SEH filters", "source-function": "hand-written",
              "uht-ufunction-creator": "UFunction creators", "uht-class-constructor": "UClass constructors",
              "uht-static-register-natives": "native registrars", "uht-struct-constructor": "UStruct constructors",
              "uht-staticstruct": "StaticStruct"}
    items = [f"{labels.get(k, k.replace('-', ' '))} {v:,}" for k, v in s["exact_by_category"].items()] or ["none"]
    cat_lines = wrap("exact by category:", items, 96)
    W = 760
    extra = 18 * (len(cat_lines) - 1)
    H = 252 + extra
    bar_x, bar_y, bar_w, bar_h = 32, 104, W - 64, 14
    fill = bar_w * s["exact"] / s["denominator"] if s["denominator"] else 0
    st = s["states"]
    font = "font-family=\"Segoe UI, -apple-system, Helvetica, Arial, sans-serif\""
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">',
        f'<title id="t">Fortnite 2.5 — Exact Function Matches</title>',
        f'<desc id="d">{s["exact"]} of {s["denominator"]:,} identified functions match the reference bytes exactly ({pct(s["exact"], s["denominator"])}).</desc>',
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="10" fill="#0f141a" stroke="#2a323c"/>',
        f'<text x="32" y="40" {font} font-size="19" font-weight="600" fill="#e6edf3">Fortnite 2.5 — Exact Function Matches</text>',
        f'<text x="32" y="82" {font} font-size="28" font-weight="700" fill="#e6edf3">{s["exact"]:,}<tspan font-size="18" font-weight="400" fill="#8b949e"> / {s["denominator"]:,} functions</tspan></text>',
        f'<text x="{W - 32}" y="82" text-anchor="end" {font} font-size="28" font-weight="700" fill="#3fb950">{pct(s["exact"], s["denominator"])}</text>',
        f'<rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="7" fill="#21262d"/>',
    ]
    if fill > 0:
        lines.append(f'<rect x="{bar_x}" y="{bar_y}" width="{fill:.3f}" height="{bar_h}" rx="{min(7, fill / 2):.3f}" fill="#3fb950"/>')
    lines.append(f'<text x="32" y="146" {font} font-size="13" fill="#c9d1d9">exact {st["exact"]} · relocation-equivalent {st["relocation-equivalent"]} · partial {st["partial"]} · unmatched {st["unmatched"]} · unknown {st["unknown"]} · not located {s["unlocated"]} · absent from image {s["not_present"]}</text>')
    for i, text in enumerate(cat_lines):
        lines.append(f'<text x="32" y="{166 + 18 * i}" {font} font-size="13" fill="#c9d1d9" xml:space="preserve">{esc(text)}</text>')
    lines += [
        f'<text x="32" y="{184 + extra}" {font} font-size="13" fill="#c9d1d9">{s["exact_bytes"]:,} bytes · compared with on-disk bytes {s["exact_vs_disk"]:,} · with the validated decrypted image {s["exact_vs_decrypted"]:,}</text>',
        f'<text x="32" y="{212 + extra}" {font} font-size="11.5" fill="#8b949e">Denominator: primary .pdata functions in the main .text ({s["outside_denominator"]} recovered functions without .pdata outside it, {s["outside_denominator_exact"]} exact).</text>',
        f'<text x="32" y="{227 + extra}" {font} font-size="11.5" fill="#8b949e">Encrypted bodies are compared with a validated decrypted image. Exact = identical bytes; relocations from independent evidence.</text>',
        f'<text x="{W - 32}" y="40" text-anchor="end" {font} font-size="11" fill="#6e7681">manifest {s["manifest_digest"]} · ref {s["reference"]}</text>',
        "</svg>",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    sys.path.insert(0, str(ROOT / "tools" / "matching"))
    import manifest_io
    for extra in sorted((ROOT / "analysis").glob("functions-*.json")):
        m["functions"] += manifest_io.expand(json.loads(extra.read_text(encoding="utf-8")))
    errors = validate(m)
    if errors:
        print("manifest inconsistent:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 1
    s = summarize(m)
    svg = render(s)
    if args.verify:
        current = SVG.read_text(encoding="utf-8") if SVG.exists() else ""
        if current != svg:
            print(f"{SVG.relative_to(ROOT)} is stale; run python tools/progress/generate.py", file=sys.stderr)
            return 1
        print("progress image up to date:", json.dumps(s))
        return 0
    SVG.parent.mkdir(parents=True, exist_ok=True)
    SVG.write_text(svg, encoding="utf-8", newline="\n")
    print(json.dumps(s, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
