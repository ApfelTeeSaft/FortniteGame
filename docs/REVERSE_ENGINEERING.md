# Stage 1 reverse engineering

The supplied executable is at `2.5/2.5/FortniteGame/Binaries/Win64/FortniteClient-Win64-Shipping.exe` relative to this checkout. The root `Engine/`, `Samples/`, and `Templates/` belong to the local Unreal distribution. Its `Engine/Build/Build.version` reports UE `4.20.0`, branch `++UE4+Release-4.20`, and changelist and compatible changelist `0`. The client contains UTF-16LE strings `4.20.0-3889387` and `++Fortnite+Release-2.5-CL-3889387`. The common version number leaves the internal fork, layouts, and generated code unresolved.

## PE evidence

[The machine-readable fingerprint](../analysis/build-fingerprint.json) records the section table, data directories, import module names, reflected packages, Rich records, and file hash. The image is PE32+ AMD64 with preferred base `0x140000000`, Windows GUI subsystem, COFF timestamp `2018-02-14 18:25:22 UTC`, and 90 exports. It has two sections named `.text`. The first has entropy 7.988 bits per byte and many sampled entry points contain implausible instructions. The exception data directory holds 253,131 runtime-function slots. IDA reported 102,168 entries with invalid unwind data. Together these are consistent with a transformed on-disk image. The exact transformation and which original functions remain visible on disk are unresolved.

The debug directory includes a CodeView record for `FortniteClient-Win64-Shipping.pdb`. The local reference tree lacks that PDB. The certificate table has 6,080 bytes at file offset `0x4E7AE00`. Windows identifies the signer as Epic Games Inc. and reports `HashMismatch`. Full-file reproduction would have to account for the post-link layout and signature bytes. The cause of the signature mismatch is unresolved. [Microsoft PE format](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format)

The PE linker version is `14.0`. The Rich header contains several build numbers, including `24215`. Imports include `MSVCP140.dll`, `VCRUNTIME140.dll`, and UCRT API sets. The linker and Rich records make MSVC 2015 Update 3 a strong candidate. The exact compiler used for each translation unit and the original optimization, inlining, LTCG, ICF, and PGO settings remain unresolved. The v140 and v142 probes produce the same bytes for the tested synthetic function, so a small exact match alone cannot identify the compiler. [Microsoft compiler build versions](https://learn.microsoft.com/en-us/cpp/error-messages/compiler-warnings/compiler-warnings-by-compiler-version)

Reflected strings include `/Script/FortniteGame`, `/Script/FortniteUI`, `/Script/Engine`, and `/Script/CoreUObject`. They identify logical packages inside the image. Native code boundaries for those packages remain unresolved. The RTTI counts measure marker hits and may include embedded strings outside RTTI descriptors.

A separate static spot check looked for six common MSVC x64 stack-allocation and
register-save prefixes at first-section runtime-function starts. The only
observed match was the PE entry point at `0x2D996CC`. Its initial stack
allocation and call are readable, followed by opaque bytes. This check helps
prioritize candidates and makes no claim about all possible prologues.

## Local IDA export

Start at the repository root and use the installed `idat.exe`. Keep the database, logs, and exports under `local-output/`. The PDB plugin is disabled in batch mode so the run can finish without a symbol-server lookup or a file prompt.

```powershell
$ida = 'C:\Program Files\IDA Professional 9.4\idat.exe'
$null = New-Item -ItemType Directory -Force local-output
$ref = '2.5\2.5\FortniteGame\Binaries\Win64\FortniteClient-Win64-Shipping.exe'
Start-Process -Wait -WindowStyle Hidden $ida -ArgumentList @(
    '-A', '-Opdb:off', '-Llocal-output\ida-analysis.log',
    '-olocal-output\client25.i64',
    '"-Stools\ida\export_functions.py local-output\ida-functions.jsonl"',
    $ref
)
```

The first JSONL row binds the export to the input SHA-256 and IDA version. Subsequent rows contain the RVA ranges, raw offsets where available, chunks, and IDA classification flags. Reuse the saved database for targeted export.

```powershell
Start-Process -Wait -WindowStyle Hidden $ida -ArgumentList @(
    '-A', '-Opdb:off', '-Llocal-output\ida-selected.log',
    '"-Stools\ida\export_functions.py local-output\ida-selected.jsonl 0xf724d0 0xf72d40 0xf7d7c0 0x105eb60 0x28805b0 0x28c2470"',
    'local-output\client25.i64'
)
```

Selected records include incoming and outgoing cross-references, disassembly, and pseudocode when Hex-Rays produces it. A missing function start produces an explicit error row. Treat all output as hypotheses on opaque ranges and verify boundaries against independent evidence. For example, the registration pair labelled `GetBuildingMeshComponent` points to `0xF724D0`. Its runtime-function slot agrees on the start and records end RVA `0xF724FF`, but IDA found no function start there.

The supplied engine's `FNameNativePtrPair` in `Engine/Source/Runtime/CoreUObject/Public/UObject/CoreNative.h` and the registrar emitted by `Engine/Source/Programs/UnrealHeaderTool/Private/CodeGenerator.cpp` explain the observed name-pointer and function-pointer pairs. [The symbol inventory](../analysis/symbols.json) records six corroborated pairs, their ranges, hashes of the actual on-disk bytes, and confidence levels. A confirmed reflected label leaves native C++ ownership and signature open.

## Match accounting

For a recovered function, record its source path, original range and hash,
candidate export, and the matcher's result in the function manifest. Put the
original RVA above the C++ definition along with the evidence for its identity.

A function enters the eligible set when independent evidence establishes a unique start, complete code range, and original game or engine implementation. Keep identified but unresolved records visible with an exclusion reason. Exclude generated reflection thunks, compiler helpers, imports, duplicate or overlapping ranges, and third-party library code from this metric. IDA discovery and exception counts are reported independently of this denominator.

The initial matcher accepts direct PE exports for straight-line leaf functions. It independently decodes a complete candidate ending in `ret`, checks executable file backing and the original range hash, then compares the raw bytes with no normalization. It reports a shared prefix as `partial` when bytes diverge, and `unmatched` if they diverge immediately. The manifest reserves distinct statuses for relocation-equivalent, instruction-equivalent, and unimplemented functions. Only complete raw equality with verification metadata counts toward the SVG.
