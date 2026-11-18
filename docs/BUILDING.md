# Stage 1 build and verification

Run from the repository root. The Visual Studio 2019 solution builds an x64 comparison DLL with exported synthetic functions. This configuration provides an isolated place to compare generated code while the first client functions are being recovered.

## Prerequisites

- Visual Studio 2019 with Desktop development with C++, MSVC v142 version `14.29.30133`, and Windows SDK `10.0.19041.0`.
- Python 3.11 or later, with the pinned PE and disassembly packages below. The progress generator uses only the Python standard library.
- For the optional historical compiler experiment, Visual Studio 2015 Update 3 x64 tools with compiler `19.00.24215.1` and linker `14.00.24215.1`.
- For reference checks, the original shipping executable at `2.5/2.5/FortniteGame/Binaries/Win64/FortniteClient-Win64-Shipping.exe`. A copy elsewhere can be selected with `--reference`. IDA Professional 9.4 with IDAPython is required only for the IDA export.

## Build and check

Open `FortniteGameCode/FortniteGameCode.sln` and build `ClientShipping|x64`, or run these commands from a Visual Studio 2019 Developer PowerShell.

```powershell
py -m pip install -r tools/matching/requirements.txt
msbuild FortniteGameCode/FortniteGameCode.sln /t:Rebuild /p:Configuration=ClientShipping /p:Platform=x64
py -m tools.matching.self_test local-output/x64/ClientShipping/FortniteGameCode.dll
py tools/progress/generate.py --verify
```

The comparison DLL uses `/O2 /Ob2 /Gy /MD /GS /EHsc /fp:precise` with whole-program optimization disabled. The linker disables incremental linking and identical COMDAT folding, so exported functions can be identified individually. These are baseline experiment settings. The shipping settings remain unresolved.

```powershell
./tools/matching/probe-v140.ps1
py -m tools.matching.self_test local-output/x64/ClientShipping/FortniteGameCode.dll --alternate-toolchain local-output/v140/Probe.dll --funclet-object local-output/v140/DelayLoadFilterProbe.obj
```

Use the original executable for the following commands. All comparisons read it directly from disk.

```powershell
py -m tools.matching.fingerprint
py -m tools.matching.verify_symbols
py -m tools.matching.audit_unwind --ida-inventory local-output/ida-functions.jsonl
py -m tools.matching.trace_flow --blocks 32
py -m tools.matching.compare local-output/x64/ClientShipping/FortniteGameCode.dll
py -m tools.matching.compare_funclets local-output/x64/ClientShipping/obj/DelayLoadFilterProbe.obj --verify
py -m tools.matching.compare_funclets local-output/v140/DelayLoadFilterProbe.obj --verify
```

The unwind audit accepts the full local IDA inventory to corroborate a matching range. Omit `--ida-inventory` to run the PE checks independently.

The PE comparison reports `whole_file_exact: false` and has no matched
functions in the linked comparison DLL. The two shipping-image funclet
comparisons use the generated object files. `--verify` checks the recorded
statuses and range hashes independently of changes to the object file's
build metadata.

The synthetic self-test verifies exact equality, a byte mismatch, and rejection
of a shortened original extent for a leaf, a branching function, a
function with a large stack allocation, and a function saving a nonvolatile
SIMD register. Additional negative tests reject a changed SIMD register,
truncated COFF files, code with relocations, and relative loops in the leaf
matcher. The static trace test checks calls, returns, and pending addresses
when its block limit is reached. The large-frame
test disables security-cookie generation only for its two synthetic functions
so it can exercise flagless unwind records in the standalone DLL.

The static trace is bounded discovery over executable file-backed bytes. Use
`--start 0x0005BAC5` to trace from the newly identified startup call target.
Its output lists pending addresses when the traversal reaches its block limit.
It provides instruction and edge metadata for subsequent IDA work.
