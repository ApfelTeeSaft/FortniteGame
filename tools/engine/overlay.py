"""Overlay copies of engine .cpp files: the reference's __LINE__ numbering.

Fortnite's engine files have lines added or removed relative to the public UE4.20.0 tree, so
the __LINE__ values that shipping logging and fatal errors pass differ. An overlay is a local
copy of a .cpp, placed under FortniteGameCode/Build/Engine/, with

- `#line N "<file>"` before its first line: N - 1 lines of offset, and the file name __FILE__
  is to have (build.py: the original path, so that nothing else changes; lines.py's
  measurement: the reference's, D:\\Build\\++FN25\\Sync\\Engine\\Source\\...\\X.cpp, the unity
  files having included absolute paths there as UBT's do here);
- `#line M` before chosen lines, so every line whose original number is known
  (analysis/engine-lines.json, tools/engine/lines.py) gets that number;
- its quote includes that resolve in the original file's directory rewritten to absolute
  paths, so they find what they found before (the original directory is also passed with /I
  for headers that rely on the include stack).

The directives change only numbering and the presumed file name, not the code. A directive is
placed only where it cannot fall inside a macro's arguments, a comment, a string or a
continued line, and in the same preprocessor region as the line it renumbers. The engine
source itself is never modified; overlays are local build products like the objects.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ue_target as T  # noqa: E402

BUILD_ROOT = "D:\\Build\\++FN25\\Sync"
LINES_JSON = T.ROOT / "analysis" / "engine-lines.json"
INCLUDE = re.compile(r'^(\s*#\s*include\s*)"([^"]+)"', re.M)
CONDITIONAL = re.compile(r"^\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b")


def reference_file(src: Path) -> str:
    """The reference's __FILE__ for an engine .cpp, as a C string literal's contents."""
    rel = os.path.normpath(str(src.relative_to(T.ROOT)))
    return (BUILD_ROOT + "\\" + rel).replace("\\", "\\\\")


def original_file(src: Path) -> str:
    """__FILE__ of the .cpp compiled in place (the unity file's absolute include), as a C
    string literal's contents."""
    return os.path.normpath(str(src)).replace("\\", "\\\\")


def is_engine_source(path: Path) -> bool:
    try:
        rel = path.relative_to(T.ENGINE)
    except ValueError:
        return False
    return rel.parts[0] in ("Source", "Plugins") and path.suffix.lower() == ".cpp"


def raw_prefix(line: str, i: int) -> bool:
    """Does the '"' at i open a raw string literal (R"..., u8R"..., LR"...)?"""
    j = i - 1
    while j >= 0 and (line[j].isalnum() or line[j] == "_"):
        j -= 1
    return line[j + 1:i] in ("R", "u8R", "uR", "UR", "LR")


def scan(text: str) -> tuple[list[bool], list[int], list[bool], list[tuple]]:
    """Per line (1-based; index 0 unused): may a directive go before it, the brace depth at
    its start, whether the previous code line ended a statement or block, and the
    preprocessor region in effect before it (a tuple of (#if group, branch) from the outside
    in: a directive is processed wherever the line it renumbers is, if its region is that
    line's or encloses it)."""
    lines = text.split("\n")
    n = len(lines)
    safe, depth, boundary, region = [False] * (n + 2), [0] * (n + 2), [False] * (n + 2), [()] * (n + 2)
    in_block, raw, cont, directive = False, None, False, False
    paren = brace = groups = 0
    stack: list[tuple[int, int]] = []
    prev_end = ";"
    for k, line in enumerate(lines, 1):
        line = line.rstrip("\r")
        safe[k] = not in_block and raw is None and not cont and paren == 0
        depth[k] = brace
        boundary[k] = prev_end in ";{}#:"
        region[k] = tuple(stack)
        if not cont and not in_block and raw is None:
            directive = line.lstrip().startswith("#")
            m = CONDITIONAL.match(line)
            if m:
                if m.group(1).startswith("if"):
                    groups += 1
                    stack.append((groups, 0))
                elif m.group(1) == "endif":
                    if stack:
                        stack.pop()
                elif stack:
                    stack[-1] = (stack[-1][0], stack[-1][1] + 1)
        i, m, last = 0, len(line), None
        while i < m:
            if raw is not None:
                j = line.find(")" + raw + '"', i)
                if j < 0:
                    i = m
                    break
                i = j + len(raw) + 2
                raw, last = None, '"'
                continue
            if in_block:
                j = line.find("*/", i)
                if j < 0:
                    i = m
                    break
                i, in_block = j + 2, False
                continue
            c = line[i]
            if c == "/" and line.startswith("//", i):
                break
            if c == "/" and line.startswith("/*", i):
                in_block, i = True, i + 2
                continue
            if c == '"' or (c == "'" and not (i and line[i - 1].isdigit())):
                if c == '"' and raw_prefix(line, i):
                    j = line.find("(", i)
                    raw, i = line[i + 1:j], j + 1
                    continue
                j = i + 1
                while j < m and line[j] != c:
                    j += 2 if line[j] == "\\" else 1
                i, last = j + 1, c
                continue
            if not directive:
                if c == "(":
                    paren += 1
                elif c == ")":
                    paren = max(0, paren - 1)
                elif c == "{":
                    brace += 1
                elif c == "}":
                    brace = max(0, brace - 1)
            if not c.isspace():
                last = c
            i += 1
        cont = line.endswith("\\") and raw is None and not in_block
        if directive and not cont:
            prev_end = "#"
        elif last is not None and not directive:
            prev_end = last
    return safe, depth, boundary, region


def plan(constraints: list[tuple[int, int]], text: str) -> tuple[int, list[tuple[int, int]], list[tuple[int, int]]]:
    """Numbering for one file: (number of line 1, [(line, number)] directives before lines,
    constraints that could not be placed). constraints: (our line, original line), one per
    line, sorted by line (lines.derive). Where the offset changes between two known lines,
    the directive goes at the latest safe line of the least brace depth between them (between
    functions where it can: the change is somewhere in that stretch, and nothing says where)."""
    safe, depth, boundary, region = scan(text)
    cur, prev, inserts, dropped = 0, 0, [], []
    for L, R in constraints:
        d = R - L
        if d != cur:
            r = region[L]
            cands = [k for k in range(prev + 1, L + 1)
                     if safe[k] and k + d >= 1 and region[k] == r[:len(region[k])]]
            if not cands:
                dropped.append((L, R))
                continue
            low = min(depth[k] for k in cands)
            k = max(cands, key=lambda k: (depth[k] == low, boundary[k], k))
            inserts.append((k, k + d))
            cur = d
        prev = L
    first = 1
    if inserts and inserts[0][0] == 1:
        first = inserts.pop(0)[1]
    return first, inserts, dropped


def number(line: int, first: int, inserts: list[tuple[int, int]]) -> int:
    """The number a plain-source line gets in the overlay."""
    base, at = first, 1
    for k, num in inserts:
        if k <= line:
            base, at = num, k
    return base + line - at


def overlay_text(src: Path, text: str, first: int, inserts: list[tuple[int, int]], name: str) -> str:
    def absolute(m):
        target = src.parent / m.group(2)
        if target.is_file():
            return f'{m.group(1)}"{os.path.normpath(str(target))}"'
        return m.group(0)
    lines = text.split("\n")
    at = dict(inserts)
    out = [f'#line {first} "{name}"']
    for k, line in enumerate(lines, 1):
        if k in at:
            out.append(f"#line {at[k]}")
        out.append(line)
    return INCLUDE.sub(absolute, "\n".join(out))


def write_if_changed(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.encode("utf-8")
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)


def read_source(src: Path) -> str:
    raw = src.read_bytes()
    if raw.startswith(b"\xff\xfe"):
        return raw[2:].decode("utf-16-le")
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return raw.decode("utf-8", errors="surrogateescape")


def overlay_unit(unit: Path, out_root: Path, module: str, numbering) -> tuple[Path, list[Path], list[Path]]:
    """(source to compile, original directories for /I, files written) for one compile
    action's source. numbering(index, src) -> None (compile the file as it is) or (number of
    line 1, directives, __FILE__ literal); index counts the unit's engine .cpp files in order.
    A unit none of whose files is overlaid is compiled as it is."""
    files, dirs = [], []

    def one(src: Path, index: int) -> Path | None:
        how = numbering(index, src)
        if how is None:
            return None
        first, inserts, name = how
        text = read_source(src)
        dst = out_root / "src" / src.relative_to(T.ROOT)
        data = overlay_text(src, text, first, inserts, name)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists() or dst.read_bytes() != data.encode("utf-8", errors="surrogateescape"):
            dst.write_bytes(data.encode("utf-8", errors="surrogateescape"))
        files.append(dst)
        if src.parent not in dirs:
            dirs.append(src.parent)
        return dst

    if not unit.name.startswith("Module."):
        dst = one(unit, 0) if is_engine_source(unit) else None
        return (unit, [], []) if dst is None else (dst, dirs, files)
    index = 0
    out_lines = []
    for line in unit.read_text(encoding="utf-8", errors="replace").split("\n"):
        m = re.match(r'^#include "([^"]+\.cpp)"', line)
        if m and is_engine_source(Path(m.group(1))):
            dst = one(Path(m.group(1)), index)
            out_lines.append(line if dst is None else f'#include "{dst}"')
            index += 1
        else:
            out_lines.append(line)
    if not files:
        return unit, [], []
    dst = out_root / "units" / module / unit.name
    write_if_changed(dst, "\n".join(out_lines))
    files.append(dst)
    return dst, dirs, files


def load_lines() -> dict[str, list[tuple[int, int]]]:
    """Engine-relative .cpp path ('Engine/Source/...') -> [(our line, original line)]."""
    if not LINES_JSON.exists():
        return {}
    m = json.loads(LINES_JSON.read_text(encoding="utf-8"))
    return {f: [(c[0], c[1]) for c in cs] for f, cs in m["files"].items()}


def final_numbering(lines: dict[str, list[tuple[int, int]]]):
    """numbering() for build.py: the recovered original line numbers, for the files whose
    numbers differ; the others are compiled as they are."""
    cache: dict = {}

    def numbering(index: int, src: Path):
        rel = src.relative_to(T.ROOT).as_posix()
        if rel not in cache:
            cache[rel] = None
            if rel in lines:
                first, inserts, _ = plan(lines[rel], read_source(src))
                if first != 1 or inserts:
                    cache[rel] = (first, inserts, original_file(src))
        return cache[rel]
    return numbering
