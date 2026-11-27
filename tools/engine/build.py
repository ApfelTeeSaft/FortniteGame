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
definitions (ue_target.PROJECT_DEFINITIONS) applied. An engine .cpp whose line numbers differ
in the reference is compiled through an overlay (tools/engine/overlay.py): a local copy whose
#line directives give its lines the original numbers of analysis/engine-lines.json, under its
own file name, and the headers tools/engine/layout.py patches, where Fortnite's classes are
laid out differently, through its mirror of their include root: the response file's /I of
the root (and of its ancestors, searched first) and the wrappers' includes name the mirror,
and /showIncludes checks that no original file of the root is opened (--plain: every file as
it is). A build record per module
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
import layout  # noqa: E402
import msvc  # noqa: E402
import ue_target as T  # noqa: E402

OBJ_ROOT = T.ROOT / "FortniteGameCode" / "Build" / "ClientShipping" / "obj"
ENGINE_OBJ = OBJ_ROOT / "Engine"
WRAPPERS = T.BUILD_DIR / "wrappers"
OVERLAY_ROOT = T.BUILD_DIR / "overlay"
DROP = ("/Yu", "/Fp", "/Fo", "/Yc")
DROP_EXACT = {"/Z7", "/Zo"}
INCLUDING = "Note: including file:"

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


def wrapper_copy(path: Path, overrides: dict, mirrored: bool = False) -> Path:
    """A force-included wrapper header with the project's definitions applied. Its own
    includes are absolute, so the copy works from anywhere; with mirrored, those in a root
    tools/engine/layout.py mirrors name the mirror's copy."""
    src = path.read_text(encoding="utf-8", errors="replace")
    for k, v in overrides.items():
        src, n = re.subn(rf"^#define {re.escape(k)} .*$", f"#define {k} {v}", src, flags=re.M)
    if mirrored:
        def mirror(m):
            return f'{m.group(1)}"{layout.mirror_path(m.group(2))}"' if layout.mirrored_root(m.group(2)) else m.group(0)
        src = re.sub(r'^(\s*#\s*include\s*)"([^"]+)"', mirror, src, flags=re.M)
    rel = path.relative_to(T.INTERMEDIATE)
    out = WRAPPERS / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists() or out.read_text(encoding="utf-8", errors="replace") != src:
        out.write_text(src, encoding="utf-8")
    return out


def rewrite(response: Path, obj: Path, overrides: dict, tag: str, transform=None,
            mirrors: bool = False) -> tuple[Path, Path, list[Path], bool]:
    """(our response file, the action's source, overlay and wrapper files, whether it uses a
    mirrored include root) from UBT's response file. transform(source) -> (source to
    compile, directories to search last, files it wrote). With mirrors, the include roots
    tools/engine/layout.py patches are searched in its mirror instead."""
    lines = response.read_text(encoding="utf-8", errors="replace").splitlines()
    out, source, extra, written, wrappers = [], None, [], [], []
    mirrored = False
    if mirrors:
        layout.prepare()
    for line in lines:
        s = line.strip()
        if not s or s in DROP_EXACT or s.startswith(DROP):
            continue
        if mirrors and s.startswith("/I"):
            d = s[2:].strip().strip('"')
            if layout.mirrored_root(d):              # the root: searched in the mirror only
                out.append(f'/I "{layout.mirror_path(d)}"')
                mirrored = True
                continue
            if layout.holds_mirrored_root(d):        # an ancestor ("CoreUObject/Public/..."): mirror first
                out.append(f'/I "{layout.mirror_path(d)}"')
                mirrored = True
        if s.startswith("/FI"):
            wrappers.append(wrapper_copy(Path(s[3:].strip(chr(34))), overrides, mirrors))
            out.append(f'/FI"{wrappers[-1]}"')
            continue
        if s.startswith('"') and not s.startswith('"/'):
            source = Path(s.strip('"'))
            if transform is not None:
                compiled, extra, written = transform(source)
                s = f'"{compiled}"'
        out.append(s)
    out += [f'/I "{d}"' for d in extra]
    if mirrored:
        out.append("/showIncludes")
    out.append(f'/Fo"{obj}"')
    rsp_dir = T.BUILD_DIR / "rsp" / tag if tag else T.BUILD_DIR / "rsp"
    rsp = rsp_dir / response.parent.name / response.name
    rsp.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(out) + "\n"
    if not rsp.exists() or rsp.read_text(encoding="utf-8") != text:   # unchanged: keep its time stamp
        rsp.write_text(text, encoding="utf-8")
    return rsp, source, written + wrappers, mirrored


def action_source(response: Path) -> Path:
    """The source file UBT's response file compiles."""
    for line in response.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s.startswith('"') and not s.startswith('"/'):
            return Path(s.strip('"'))
    raise ValueError(f"no source in {response}")


def included_sources(unit: Path) -> list[str]:
    """The .cpp files a unity file includes (or the unit itself)."""
    if not unit.name.startswith("Module."):
        return [str(unit)]
    return re.findall(r'^#include "([^"]+\.cpp)"', unit.read_text(encoding="utf-8", errors="replace"), re.M)


def compile_action(response: Path, overrides: dict, env: dict, obj_root: Path = ENGINE_OBJ, tag: str = "",
                   numbering=None, overlay_root: Path | None = None) -> dict:
    """Compile one action. With numbering, its engine .cpp files are compiled through overlays
    (tools/engine/overlay.py) written under overlay_root, and the headers tools/engine/layout.py
    patches through its mirror; tag keeps response files apart."""
    module = response.parent.name
    unit_name = response.name[:-len(".cpp.obj.response")]
    obj = obj_root / module / f"{unit_name}.obj"
    obj.parent.mkdir(parents=True, exist_ok=True)
    transform = None
    if numbering is not None:
        import overlay
        transform = lambda src: overlay.overlay_unit(src, overlay_root, module, numbering)  # noqa: E731
    rsp, source, written, mirrored = rewrite(response, obj, overrides, tag, transform, mirrors=numbering is not None)
    if mirrored:
        written = written + [layout.stamp()]
    try:
        objrel = str(obj.relative_to(OBJ_ROOT)).replace("\\", "/")
    except ValueError:
        objrel = str(obj)
    rec = {"unit": unit_name, "object": objrel,
           "sources": [str(Path(p).relative_to(T.ROOT)).replace("\\", "/") if Path(p).is_absolute() else p
                       for p in included_sources(source)]}
    if numbering is not None:
        rec["overlay"] = True
    inputs = [source] + [Path(p) for p in included_sources(source)] + [rsp] + written
    if obj.exists() and obj.stat().st_mtime > max(p.stat().st_mtime for p in inputs if p.exists()):
        rec["ok"] = True
        return rec
    r = subprocess.run([cl_path(env), f"@{rsp}"], env=env, cwd=T.ENGINE_SOURCE, capture_output=True,
                       text=True, errors="replace")
    out = [l for l in r.stdout.splitlines() if not l.startswith(INCLUDING)]
    originals = sorted({l[len(INCLUDING):].strip() for l in r.stdout.splitlines() if l.startswith(INCLUDING)
                        and layout.mirrored_root(l[len(INCLUDING):].strip())})
    rec["ok"] = r.returncode == 0 and not originals
    if not rec["ok"]:
        rec["errors"] = "\n".join([l for l in out if "error" in l][:8] +
                                  [f"original header of a mirrored root: {p}" for p in originals[:8]])
        if obj.exists():
            obj.unlink()
    return rec


def build_module(module: str, jobs: int, overrides: dict, numbering=None) -> dict:
    env = vc_environment()
    acts = T.actions(module)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        units = list(ex.map(lambda a: compile_action(a, overrides, env, numbering=numbering,
                                                      overlay_root=OVERLAY_ROOT), acts))
    record = {"module": module, "overrides": overrides, "seconds": round(time.time() - t0, 1),
              "overlays": numbering is not None, "units": units}
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
    ap.add_argument("--plain", action="store_true",
                    help="compile the engine files as they are, without the overlays (tools/engine/overlay.py)")
    a = ap.parse_args()
    T.export()
    overrides = dict(T.PROJECT_DEFINITIONS)
    overrides.update(dict(d.split("=", 1) for d in a.define))
    names = T.compiled_modules() if a.all else a.modules
    numbering = None
    if not a.plain:
        import overlay
        numbering = overlay.final_numbering(overlay.load_lines())
    for n in names:
        build_module(n, a.jobs, overrides, numbering)
    return 0


if __name__ == "__main__":
    sys.exit(main())
