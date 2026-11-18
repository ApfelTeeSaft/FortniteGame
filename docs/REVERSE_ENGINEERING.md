# Stage 1 reverse engineering

The supplied executable is at `2.5/2.5/FortniteGame/Binaries/Win64/FortniteClient-Win64-Shipping.exe` relative to this checkout. The root `Engine/`, `Samples/`, and `Templates/` belong to the local Unreal distribution. Its `Engine/Build/Build.version` reports UE `4.20.0`, branch `++UE4+Release-4.20`, and changelist and compatible changelist `0`. The client contains UTF-16LE strings `4.20.0-3889387` and `++Fortnite+Release-2.5-CL-3889387`. The common version number leaves the internal fork, layouts, and generated code unresolved.

## PE evidence

[The machine-readable fingerprint](../analysis/build-fingerprint.json) records the section table, data directories, import module names, reflected packages, Rich records, and file hash. The image is PE32+ AMD64 with preferred base `0x140000000`, Windows GUI subsystem, COFF timestamp `2018-02-14 18:25:22 UTC`, and 90 exports. It has two sections named `.text`. The first has entropy 7.988 bits per byte and many sampled entry points contain implausible instructions. The exception data directory holds 253,131 runtime-function slots. IDA reported 102,168 entries with invalid unwind data. Together these are consistent with a transformed on-disk image. The exact transformation and which original functions remain visible on disk are unresolved.

The debug directory includes a CodeView record for `FortniteClient-Win64-Shipping.pdb`. The local reference tree lacks that PDB. The certificate table has 6,080 bytes at file offset `0x4E7AE00`. Windows identifies the signer as Epic Games Inc. and reports `HashMismatch`. Full-file reproduction would have to account for the post-link layout and signature bytes. The cause of the signature mismatch is unresolved. [Microsoft PE format](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format)

The PE linker version is `14.0`. The Rich header contains several build numbers, including `24215`. Imports include `MSVCP140.dll`, `VCRUNTIME140.dll`, and UCRT API sets. The linker and Rich records make MSVC 2015 Update 3 a strong candidate. The exact compiler used for each translation unit and the original optimization, inlining, LTCG, ICF, and PGO settings remain unresolved. The v140 and v142 probes produce the same bytes for the tested synthetic function, so a small exact match alone cannot identify the compiler. [Microsoft compiler build versions](https://learn.microsoft.com/en-us/cpp/error-messages/compiler-warnings/compiler-warnings-by-compiler-version)

Reflected strings include `/Script/FortniteGame`, `/Script/FortniteUI`, `/Script/Engine`, and `/Script/CoreUObject`. They identify logical packages inside the image. Native code boundaries for those packages remain unresolved. The RTTI counts measure marker hits and may include embedded strings outside RTTI descriptors.

The [unwind audit](../analysis/unwind-audit.json) examined 153,169 file-backed
prologues with supported version-1 unwind operations. This includes integer
and SIMD register saves, frame-pointer setup, and records with exception or
termination handlers. The code-range matcher accepts flagless records.
Three prologues agree with their unwind records. The
entry point at `0x02D996CC` lacks a complete body. The other two are SEH
filters with complete bodies and one trailing trap each. [Microsoft x64 exception handling](https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64)

The SIMD probe keeps a double-precision argument alive across a call, causing
the compiler to save a nonvolatile XMM register. It matches across v140 and
v142. Changing the source register in the saved instruction fails prologue
validation. The COFF regression checks reject truncated headers, symbol
tables, and code sections with relocations. The leaf matcher also rejects
`LOOP`, which Capstone identifies through its branch-relative group.

## Startup control-flow discovery

The [bounded static trace](../analysis/startup-flow.json) begins at the PE
entry point and records 32 blocks with seven pending addresses. Each decoded
range has a file offset, section index, hash, instruction counts, and outgoing
direct edges. These metadata establish where the static decoder followed
bytes. They leave original function boundaries and runtime reachability open.

The entry-point call at `0x02D996D0` targets `0x04DDF2FC` in section 10.
That block saves integer and SIMD registers, checks stack alignment, and
transfers into section 0. A direct call at `0x002A7976` targets
`0x0005BAC5`, where a frame setup and guard check are readable. Its disjoint
continuations require further analysis. The saved IDA database has no
function beginning at that address. The startup routine's purpose is unknown.

## Recovered compiler-generated filters

The filters at `0x02DAE750` and `0x02DAE780` accept MSVC delay-load
exception codes `0xC06D007E` and `0xC06D007F`. The saved IDA database
corroborates the instruction boundaries. Three PE scope records point to the
two RVAs and verify that they are exception filter targets. The local UE
Windows D3D11 and D3D12 device sources both use an `IsDelayLoadException`
predicate with these codes. The exact enclosing C++ function names remain
inferred because their bodies are opaque.

The C++ probe uses synthetic parent functions and lets MSVC generate the
filters. The verifier finds the named COFF symbols, checks their independent
runtime-function boundaries through the object's `.pdata` relocations, and
reads the complete relocation-free code ranges. The small filter matches all
42 bytes on both toolchains. The wider filter differs at offset `0x0C` in
its exception-pointer spill displacement. The build covers a standalone
layout reproduction and records both entries outside the progress denominator.
[Function manifest](../analysis/functions.json)

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

The matcher resolves the candidate from a direct PE export. Its default
`leaf` boundary method decodes a straight-line body through `ret` on both
sides. For functions with internal branches, use
`"boundary_method": "pe-runtime-function"`. This method requires a unique,
non-overlapping runtime-function range in each image, a supported version-1
unwind prologue matching the code, and a body that decodes through its final
near return. Internal branch targets must land on decoded instruction
boundaries. The raw comparison includes any trailing `INT3` bytes covered
by the runtime-function record. Chained unwind entries, handlers in the
compared body, indirect jumps, and branches leaving the
range are outside this method's current scope.

Both methods check executable file backing and the original range hash before
comparing the raw code bytes. Call displacements are compared as stored.
A shared prefix yields `partial` when bytes diverge. An immediate difference
yields `unmatched`. The manifest reserves distinct statuses for
relocation-equivalent, instruction-equivalent, and unimplemented functions.
Only complete raw equality with verification metadata counts toward the SVG.
