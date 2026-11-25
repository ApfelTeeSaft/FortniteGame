"""The UE4.20 engine target the reference's engine code was built as, from UnrealBuildTool.

UBT is built from the local engine tree (Engine/Source/Programs/UnrealBuildTool) and run for the
engine's game target, UE4Game Win64 Shipping, with -JsonExport and -SkipBuild, pinned to the
reference's toolchain (VS2015 v140, Windows SDK 10.0.10586.0). That evaluates every module's
Build.cs for this platform and configuration, runs UnrealHeaderTool (the real generated
headers, Engine/Intermediate/Build/Win64/UE4/Inc/<Module>/), and writes each module's unity
files and the exact compiler response file of each (Engine/Intermediate/Build/Win64/UE4/
Shipping/<Module>/*.cpp.obj.response) with the definitions in force-included wrapper headers
(PCH.<Module>.h, SharedPCH.<Module>.h, Definitions.<Module>.h). tools/engine/build.py compiles
those actions; nothing about the compile environment is reconstructed by hand.

The engine tree and everything UBT writes stay local (Engine/ is not tracked). Usage:

    python tools/engine/ue_target.py export [--force]
"""
from __future__ import annotations

import json
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "Engine"
ENGINE_SOURCE = ENGINE / "Source"
UBT_DIR = ENGINE_SOURCE / "Programs" / "UnrealBuildTool"
UBT_EXE = ENGINE / "Binaries" / "DotNET" / "UnrealBuildTool.exe"
UBT_CONFIG = ENGINE / "Saved" / "UnrealBuildTool" / "BuildConfiguration.xml"
INTERMEDIATE = ENGINE / "Intermediate" / "Build" / "Win64" / "UE4" / "Shipping"
BUILD_DIR = ROOT / "FortniteGameCode" / "Build" / "Engine"
TARGET_JSON = BUILD_DIR / "UE4Game-Win64-Shipping.json"

# UBT must use the reference's toolchain for UHT's own build too: left alone it picks the newest
# compiler and SDK, whose headers it cannot compile.
UBT_CONFIG_XML = """<?xml version="1.0" encoding="utf-8" ?>
<Configuration xmlns="https://www.unrealengine.com/BuildConfiguration">
  <WindowsPlatform>
    <Compiler>VisualStudio2015</Compiler>
    <WindowsSdkVersion>10.0.10586.0</WindowsSdkVersion>
  </WindowsPlatform>
</Configuration>
"""

# Where the reference's target differs from UE4Game's. Measured on Core (tools/engine/build.py,
# then the locator): with logging in shipping 3,884 compiled functions locate uniquely instead of
# 3,803 (+53 KB); with checks in shipping only 2,819. Fortnite's shipping client logs.
PROJECT_DEFINITIONS = {"USE_LOGGING_IN_SHIPPING": "1"}


def export(force: bool = False) -> Path:
    """Build UBT if needed and run it for UE4Game Win64 Shipping (which also runs UHT)."""
    if TARGET_JSON.exists() and INTERMEDIATE.is_dir() and not force:
        return TARGET_JSON
    sys.path.insert(0, str(ROOT / "tools" / "matching"))
    import msvc
    UBT_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    UBT_CONFIG.write_text(UBT_CONFIG_XML, encoding="utf-8")
    if not UBT_EXE.exists():
        r = subprocess.run([str(msvc.VS2019_MSBUILD), str(UBT_DIR / "UnrealBuildTool.csproj"),
                            "-p:Configuration=Development", "-p:Platform=AnyCPU", "-v:minimal", "-nologo"],
                           capture_output=True, text=True, errors="replace")
        if r.returncode:
            raise SystemExit(r.stdout[-3000:])
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([str(UBT_EXE), "UE4Game", "Win64", "Shipping", f"-JsonExport={TARGET_JSON}", "-SkipBuild"],
                       cwd=UBT_EXE.parent, capture_output=True, text=True, errors="replace")
    if r.returncode or not TARGET_JSON.exists():
        raise SystemExit(r.stdout[-3000:])
    return TARGET_JSON


@lru_cache(maxsize=None)
def target() -> dict:
    return json.loads(TARGET_JSON.read_text(encoding="utf-8"))


def modules() -> dict:
    return target()["Modules"]


def compiled_modules() -> list[str]:
    """Modules UBT wrote compile actions for, in name order."""
    return sorted(p.name for p in INTERMEDIATE.iterdir() if p.is_dir() and any(p.glob("*.cpp.obj.response")))


def actions(module: str) -> list[Path]:
    """The module's compile actions: its unity files or single sources, UHT's generated units
    included. Where the repository's UHT generators already hold a function's address, the
    mapper leaves it to them (tools/engine/map.py); the rest of UHT's code is covered here."""
    return sorted((INTERMEDIATE / module).glob("*.cpp.obj.response"))


if __name__ == "__main__":
    if sys.argv[1:2] == ["export"]:
        print(export(force="--force" in sys.argv))
    else:
        print(__doc__)
