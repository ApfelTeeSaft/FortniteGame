"""Drive the historical MSVC 19.00.24215.1 (VS2015 Update 3, toolset v140) compiler.

The canonical build is FortniteGameCode/FortniteGameCode.sln (VS2019, v140).
This module gives the matching tools the same compiler with the same UE4.20
Win64 Shipping switches for quick, single-file experiments, and can drive
MSBuild for the solution.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

VS140_VCVARS = Path(r"C:\Program Files (x86)\Microsoft Visual Studio 14.0\VC\vcvarsall.bat")
VS2019_MSBUILD = Path(r"D:\VS2019\MSBuild\Current\Bin\MSBuild.exe")
WINDOWS_SDK = "10.0.10586.0"
EXPECTED_CL_BANNER = "Version 19.00.24215.1 for x64"

# Mirrors FortniteGameCode.vcxproj (ClientShipping|x64) and UE4.20 VCToolChain.cs.
UE420_SHIPPING_FLAGS = [
    "/nologo", "/c", "/Zc:inline", "/Oi", "/Gy", "/Zm850", "/wd4819",
    "/D_CRT_STDIO_LEGACY_WIDE_SPECIFIERS=1", "/D_SILENCE_STDEXT_HASH_DEPRECATION_WARNINGS=1",
    "/source-charset:utf-8", "/execution-charset:utf-8",
    "/Ox", "/Ot", "/Ob2", "/D_HAS_EXCEPTIONS=0", "/Z7", "/MD", "/bigobj", "/fp:fast",
    "/Zo", "/Zp8", "/wd4456", "/wd4458", "/wd4459", "/wd4463", "/wd4838", "/TP", "/GS",
    "/GR-", "/W4",
    "/DUNICODE", "/D_UNICODE", "/DWIN32=1", "/D_WIN32_WINNT=0x0601", "/DWINVER=0x0601",
    "/DPLATFORM_WINDOWS=1", "/DUE_BUILD_SHIPPING=1", "/DWITH_EDITOR=0",
    "/DFNGC_MATCHING_HARNESS=1",
]


def _run_in_vcvars(command: str, cwd: Path) -> subprocess.CompletedProcess:
    with tempfile.NamedTemporaryFile("w", suffix=".bat", delete=False) as bat:
        bat.write("@echo off\r\n")
        bat.write(f'call "{VS140_VCVARS}" amd64 {WINDOWS_SDK} >nul || exit /b 1\r\n')
        bat.write(command + "\r\n")
        name = bat.name
    try:
        return subprocess.run(["cmd.exe", "/d", "/c", name], cwd=cwd, capture_output=True,
                              text=True, errors="replace")
    finally:
        os.unlink(name)


def compiler_banner() -> str:
    r = _run_in_vcvars("cl 2>&1", Path.cwd())
    return r.stdout.splitlines()[0].strip() if r.stdout else ""


def compile_cpp(source: Path, obj: Path, extra: list[str] | None = None,
                include_dirs: list[Path] | None = None) -> subprocess.CompletedProcess:
    obj.parent.mkdir(parents=True, exist_ok=True)
    flags = list(UE420_SHIPPING_FLAGS) + list(extra or [])
    # A later /GS or /GS- in `extra` overrides the default, as with cl itself.
    for inc in include_dirs or []:
        flags.append(f'/I"{inc}"')
    cmd = "cl " + " ".join(flags) + f' /Fo"{obj}" "{source}"'
    return _run_in_vcvars(cmd, source.parent)


def build_solution(sln: Path, configuration: str = "ClientShipping") -> subprocess.CompletedProcess:
    return subprocess.run([str(VS2019_MSBUILD), str(sln), f"-p:Configuration={configuration}",
                           "-p:Platform=x64", "-v:minimal", "-nologo"],
                          capture_output=True, text=True, errors="replace")
