"""Write generated sources without touching unchanged files, so MSBuild rebuilds only what changed."""
from __future__ import annotations

from pathlib import Path


def sync_tree(root: Path, files: dict[Path, str], pattern: str = "*.gen.cpp",
              recursive: bool = True) -> tuple[int, int]:
    """Make `root` hold exactly `files` (path -> text) among files matching `pattern`
    (in subdirectories too unless `recursive` is false).

    Returns (written, removed). Files whose text is unchanged keep their timestamps.
    """
    written = 0
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        data = text.encode("utf-8")
        if not path.exists() or path.read_bytes() != data:
            path.write_bytes(data)
            written += 1
    keep = {p.resolve() for p in files}
    removed = 0
    for old in (root.rglob(pattern) if recursive else root.glob(pattern)):
        if old.resolve() not in keep:
            old.unlink()
            removed += 1
    return written, removed
