"""Read and write function manifests.

analysis/functions.json is hand-curated and pretty-printed. Generated bulk manifests
(analysis/functions-*.json) are written compactly, one entry per line. Fields shared by every
entry live once in "entry_defaults", whose string values may contain {class} and {name}
placeholders. Defaults are expanded on load and stripped again on save.
"""
from __future__ import annotations

import json
from pathlib import Path


def expand(manifest: dict) -> list[dict]:
    defaults = manifest.get("entry_defaults", {})
    out = []
    for e in manifest["functions"]:
        for k, v in defaults.items():
            if k not in e:
                e[k] = v.format(**e) if isinstance(v, str) else v
        out.append(e)
    return out


def strip(manifest: dict) -> None:
    defaults = manifest.get("entry_defaults", {})
    for e in manifest["functions"]:
        for k, v in defaults.items():
            if k in e and e[k] == (v.format(**e) if isinstance(v, str) else v):
                del e[k]


def dump_compact(path: Path, manifest: dict) -> None:
    """Header fields pretty-printed, then the functions list with one entry per line."""
    head = {k: v for k, v in manifest.items() if k != "functions"}
    text = json.dumps(head, indent=1)[:-2]  # drop the closing "\n}"
    lines = [json.dumps(e, separators=(",", ":")) for e in manifest["functions"]]
    text += ',\n "functions": [\n' + ",\n".join(lines) + "\n ]\n}\n"
    path.write_text(text, encoding="utf-8")
