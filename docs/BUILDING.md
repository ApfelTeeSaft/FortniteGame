# Building and verifying

## Prerequisites (as found on the development machine)

| Component | Version | Why |
| --- | --- | --- |
| Visual Studio 2019 | 16.11 (`D:\VS2019`), MSBuild 16 | Required solution format and build driver |
| VS2015 C++ toolset (v140) | `cl.exe` 19.00.24215.1 for x64 | Exact compiler recorded in the reference Rich header (build 24215) |
| Windows SDK | 10.0.10586.0 | Pinned. The original SDK version is not yet established. Nothing matched so far depends on SDK codegen |
| Python | 3.10+ with `capstone` 5 (`pefile` optional) | Matching and report tools |
| Reference EXE | SHA-256 `9731a6b5…eb449102` at `2.5/2.5/FortniteGame/Binaries/Win64/` (repository-relative) | Local only, never committed |

## Build

```
"D:\VS2019\MSBuild\Current\Bin\MSBuild.exe" FortniteGameCode\FortniteGameCode.sln -p:Configuration=ClientShipping -p:Platform=x64
```

Objects go to `FortniteGameCode/Build/ClientShipping/obj/` (ignored by Git). The
project produces a static library: Stage 1 compares objects function by function
and links no executable yet.

## Compiler switches

`ClientShipping|x64` mirrors UE4.20 `VCToolChain.cs` for a Win64 Shipping module
built with VS2015, optimized, without LTCG, exceptions or RTTI:

`/c /Zc:inline /Oi /Gy /Zm850 /wd4819 /source-charset:utf-8 /execution-charset:utf-8 /Ox /Ot /Ob2 /D_HAS_EXCEPTIONS=0 /Z7 /MD /bigobj /fp:fast /Zo /Zp8 /W4 /wd4456 /wd4458 /wd4459 /wd4463 /wd4838 /TP /GS /GR-`
plus `_WIN32_WINNT=WINVER=0x0601`, `_CRT_STDIO_LEGACY_WIDE_SPECIFIERS=1` and `UE_BUILD_SHIPPING=1`.

The evidence for `/GS` is that 10,095 unwind records share one handler, which fits
`__GSHandlerCheck`. Recovered modules are compiled as unity translation units
(`Module.<Name>.cpp`) only where cross-file inlining evidence requires it. The
documented example is D3D11RHI.

`tools/matching/msvc.py` runs the same compiler with the same switches on a single
file, for quick experiments.

## Decrypted reference (local, optional but needed for most matches)

Function bodies in the shipping EXE are encrypted on disk. Supply a decrypted image of the
same build: a PE-file dump, a raw module-region dump or a full-memory `.dmp`. Then run

```
python tools/matching/ingest_dump.py --dump <path>
```

It validates the image against the original's plaintext data and writes the normalized
image to `local-output/reference-dump/` (ignored). Only hashes and statistics go to
`analysis/decrypted-reference.json`. Never commit the dump or the normalized image.

## Generated code

`FortniteGameCode/Source/Generated/UHT/**` and `analysis/functions-uht-*.json` are produced
from the reference's reflection data. Regenerating them needs the decrypted image. Run the
tools in this order:

```
python tools/analysis/reflection.py      # analysis/reflection-natives.json
python tools/analysis/unity_order.py     # analysis/unity-order.json (unity source order, units)
python tools/codegen/uht_creators.py     # class fragments: StaticRegisterNatives, creators, constructor
python tools/codegen/uht_structs.py      # USTRUCT fragments
python tools/codegen/uht_enums.py        # UENUM fragments (constructor; StaticEnum in .static)
python tools/codegen/uht_classes.py      # Classes.gen.h, IMPLEMENT_CLASS fragments
python tools/codegen/unity.py            # Unity/*.gen.cpp: fragments in recovered order
```

Only `Source/Generated/UHT/Unity/*.gen.cpp` is compiled. Each unity unit `#include`s per-item
fragments in the order of the original unity file, after `UnityPrologue.h`, a stand-in for
the engine headers' namespace-scope objects. `StaticEnum` fragments are compiled in per-run
units (`<unit>.s<k>`).

The generators rewrite only files whose content changed, so MSBuild recompiles only those.
The generated sources are committed, so a checkout builds without the decrypted image.

## Verify

```
python tools/matching/compare.py --build    # rebuild, compare, update analysis/functions.json
python tools/matching/compare.py --check    # fail if recorded results are stale
python tools/progress/generate.py           # regenerate docs/images/byte-match-progress.svg
python tools/progress/generate.py --verify  # fail if the SVG is stale or the manifest inconsistent
python tools/matching/selftest.py           # all of the above plus synthetic unwind tests
```

## IDA (optional)

```
"C:\Program Files\IDA Professional 9.4\idat.exe" -A -L<log> -S"tools/ida/export_metadata.py <out.json>" <binary>
```

`idat` returned exit code 173 even after a successful export. Check the JSON and log
instead of the exit code. Databases (`*.i64`, `*.id*`) stay local.
