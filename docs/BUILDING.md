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
py -m tools.matching.self_test local-output/x64/ClientShipping/FortniteGameCode.dll --alternate-toolchain local-output/v140/Probe.dll
```

Use the original executable for the following commands. All comparisons read it directly from disk.

```powershell
py -m tools.matching.fingerprint
py -m tools.matching.verify_symbols
py -m tools.matching.audit_unwind --ida-inventory local-output/ida-functions.jsonl
py -m tools.matching.compare local-output/x64/ClientShipping/FortniteGameCode.dll
```

The unwind audit accepts the full local IDA inventory to corroborate a matching range. Omit `--ida-inventory` to run the PE checks independently.

The comparison report tracks the candidate image SHA-256 separately from individual raw-byte results. The current report has an empty function list and `whole_file_exact: false`. For both a leaf and a branching synthetic function, the test verifies exact equality, a byte mismatch, and rejection of a shortened original extent. The synthetic functions are excluded from the Fortnite manifest.
