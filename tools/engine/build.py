"""Compile UE4.20 engine modules from the local engine tree with the reference's toolchain.

Each of UnrealBuildTool's compile actions for UE4Game Win64 Shipping (tools/engine/ue_target.py:
a unity file or a single source, and its response file) is run with MSVC 19.00.24215.1 as UBT
would run it, from Engine/Source, with three changes that do not alter code:

- the object goes to FortniteGameCode/Build/ClientShipping/obj/Engine/<Module>/, where
  compare.py reads objects;
- no precompiled header is created or used (/Yu, /Fp dropped): the wrapper header is still
  force-included, so the code sees the same declarations and definitions;
- no debug information (/Z7, /Zo dropped).

The force-included wrappers that carry the definitions are copied with the project's
definitions (ue_target.PROJECT_DEFINITIONS) applied. A build record per module
(FortniteGameCode/Build/Engine/<Module>.build.json) lists each action's object, the sources it
includes and any errors. Usage:

    python tools/engine/build.py Core [CoreUObject ...] [--jobs N] [--define NAME=VALUE ...]
    python tools/engine/build.py --all
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "matching"))
import msvc  # noqa: E402
import ue_target as T  # noqa: E402

OBJ_ROOT = T.ROOT / "FortniteGameCode" / "Build" / "ClientShipping" / "obj"
ENGINE_OBJ = OBJ_ROOT / "Engine"
WRAPPERS = T.BUILD_DIR / "wrappers"
DROP = ("/Yu", "/Fp", "/Fo", "/Yc")
DROP_EXACT = {"/Z7", "/Zo"}

_ENV = None


def vc_environment() -> dict:
    """The environment vcvarsall.bat sets for v140 x64 and the reference's Windows SDK."""
    global _ENV
    if _ENV is None:
        with tempfile.NamedTemporaryFile("w", suffix=".bat", delete=False) as bat:
            bat.write("@echo off\r\n")
            bat.write(f'call "{msvc.VS140_VCVARS}" amd64 {msvc.WINDOWS_SDK} >nul || exit /b 1\r\nset\r\n')
            name = bat.name
        try:
            r = subprocess.run(["cmd.exe", "/d", "/c", name], capture_output=True, text=True, errors="replace")
        finally:
            os.unlink(name)
        env = {}
        for line in r.stdout.splitlines():
            k, sep, v = line.partition("=")
            if sep and k:
                env[k] = v
        if "INCLUDE" not in env:
            raise SystemExit("vcvarsall failed: " + r.stdout[-2000:])
        _ENV = env
    return _ENV


def cl_path(env: dict) -> str:
    """cl.exe on the vcvars PATH (CreateProcess searches the parent's PATH, not env's)."""
    path = next(v for k, v in env.items() if k.upper() == "PATH")
    exe = shutil.which("cl.exe", path=path)
    if exe is None:
        raise SystemExit("cl.exe not on the vcvars PATH")
    return exe


def wrapper_copy(path: Path, overrides: dict) -> Path:
    """A force-included wrapper header with the project's definitions applied. Its own
    includes are absolute, so the copy works from anywhere."""
    src = path.read_text(encoding="utf-8", errors="replace")
    for k, v in overrides.items():
        src, n = re.subn(rf"^#define {re.escape(k)} .*$", f"#define {k} {v}", src, flags=re.M)
    rel = path.relative_to(T.INTERMEDIATE)
    out = WRAPPERS / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists() or out.read_text(encoding="utf-8", errors="replace") != src:
        out.write_text(src, encoding="utf-8")
    return out


def rewrite(response: Path, obj: Path, overrides: dict) -> tuple[Path, Path]:
    """(our response file, the action's source) from UBT's response file."""
    lines = response.read_text(encoding="utf-8", errors="replace").splitlines()
    out, source = [], None
    for line in lines:
        s = line.strip()
        if not s or s in DROP_EXACT or s.startswith(DROP):
            continue
        if s.startswith("/FI"):
            out.append(f'/FI"{wrapper_copy(Path(s[3:].strip(chr(34))), overrides)}"')
            continue
        if s.startswith('"') and not s.startswith('"/'):
            source = Path(s.strip('"'))
        out.append(s)
    out.append(f'/Fo"{obj}"')
    rsp = T.BUILD_DIR / "rsp" / response.parent.name / response.name
    rsp.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(out) + "\n"
    if not rsp.exists() or rsp.read_text(encoding="utf-8") != text:   # unchanged: keep its time stamp
        rsp.write_text(text, encoding="utf-8")
    return rsp, source


def included_sources(unit: Path) -> list[str]:
    """The .cpp files a unity file includes (or the unit itself)."""
    if not unit.name.startswith("Module."):
        return [str(unit)]
    return re.findall(r'^#include "([^"]+\.cpp)"', unit.read_text(encoding="utf-8", errors="replace"), re.M)


def compile_action(response: Path, overrides: dict, env: dict) -> dict:
    module = response.parent.name
    unit_name = response.name[:-len(".cpp.obj.response")]
    obj = ENGINE_OBJ / module / f"{unit_name}.obj"
    obj.parent.mkdir(parents=True, exist_ok=True)
    rsp, source = rewrite(response, obj, overrides)
    rec = {"unit": unit_name, "object": str(obj.relative_to(OBJ_ROOT)).replace("\\", "/"),
           "sources": [str(Path(p).relative_to(T.ROOT)).replace("\\", "/") if Path(p).is_absolute() else p
                       for p in included_sources(source)]}
    inputs = [source] + [Path(p) for p in included_sources(source)] + [rsp]
    if obj.exists() and obj.stat().st_mtime > max(p.stat().st_mtime for p in inputs if p.exists()):
        rec["ok"] = True
        return rec
    r = subprocess.run([cl_path(env), f"@{rsp}"], env=env, cwd=T.ENGINE_SOURCE, capture_output=True,
                       text=True, errors="replace")
    rec["ok"] = r.returncode == 0
    if r.returncode:
        rec["errors"] = "\n".join([l for l in r.stdout.splitlines() if "error" in l][:8])
        if obj.exists():
            obj.unlink()
    return rec


def build_module(module: str, jobs: int, overrides: dict) -> dict:
    env = vc_environment()
    acts = T.actions(module)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        units = list(ex.map(lambda a: compile_action(a, overrides, env), acts))
    record = {"module": module, "overrides": overrides, "seconds": round(time.time() - t0, 1), "units": units}
    (T.BUILD_DIR / f"{module}.build.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
    ok = sum(u["ok"] for u in units)
    print(f"{module}: {ok}/{len(units)} units compiled in {record['seconds']}s", flush=True)
    return record


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("modules", nargs="*")
    ap.add_argument("--all", action="store_true", help="every module UBT wrote compile actions for")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 8)
    ap.add_argument("--define", action="append", default=[], help="override a definition, NAME=VALUE")
    a = ap.parse_args()
    T.export()
    overrides = dict(T.PROJECT_DEFINITIONS)
    overrides.update(dict(d.split("=", 1) for d in a.define))
    names = T.compiled_modules() if a.all else a.modules
    for n in names:
        build_module(n, a.jobs, overrides)
    return 0


if __name__ == "__main__":
    sys.exit(main())
