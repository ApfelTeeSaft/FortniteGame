# Status

Stage 1 (exact-match client decompilation): **in progress**. A validated decrypted image of
the reference build now supplies plaintext function bodies. Stages 2–4 have not started.

| Item | State (verified 2026-11-20) |
| --- | --- |
| Reference | `FortniteClient-Win64-Shipping.exe`, 82,298,304 bytes, SHA-256 `9731a6b5…eb449102`, linked 2018-02-14, `++Fortnite+Release-2.5-CL-3889387`, version resource `4.20.0-3889387` |
| Decrypted reference | Owner-supplied PE dump, SHA-256 `c81fe58a…2f97370`, local only. After un-rebasing all 788,029 DIR64 sites it is byte-identical to the original over 23.5 MB of linker-produced plaintext. Prologues verify for 157,439 of 157,632 primary functions with unwind codes (99.88 %). See `analysis/decrypted-reference.json` |
| Compiler evidence | Rich header: Utc1900 C/C++ build 24215, Linker 14.00.24215, no LTCG product ids. The local v140 `cl.exe` is 19.00.24215.1 and its objects carry `@comp.id` prodid 261, build 24215 |
| VS2019 solution | `FortniteGameCode.sln` `ClientShipping\|x64` (toolset v140) builds with 0 errors and 0 warnings |
| Exact functions | **26,579 / 157,719** primary `.pdata` functions (16.85 %, 1,458,859 bytes):
- 2 matching on-disk plaintext (SEH filter funclets);
- 5 hand-reconstructed functions matching the decrypted image;
- 26,572 generated UHT functions:
  - classes: 10,534 UFunction creators, 3,227 `Z_Construct_UClass_*`, 696 `StaticRegisterNatives*`,
    923 `FCompiledInDefer` initializers;
  - packages: 551 package-scope delegate creators and 68 `Z_Construct_UPackage_*`;
  - USTRUCTs: 2,097 `Z_Construct_UScriptStruct_*`, 1,860 `StaticStruct`, 1,782 `NewStructOps`,
    1,888 `StaticRegisterNatives` and 1,253 `FCompiledInDeferStruct` initializers;
  - UENUMs: 1,071 `Z_Construct_UEnum_*`, 374 `<Enum>_StaticEnum` and 248 `FCompiledInDeferEnum` initializers.

Generated code is compiled in 182 unity units in the reference's recovered source order (`docs/REVERSE_ENGINEERING.md`, "Module layout model"). Every relocation is resolved from independent or leave-one-out evidence. Also exact, outside the denominator: 696 `StaticClass` thunks, 1,248 `AutoInitialize` initializers and `FCommandLine::IsInitialized` |
| Relocation-equivalent | 9,252 in the denominator, mostly:
- the 3,283 `GetPrivateStaticClass` bodies (template-instance and literal fields);
- registration initializers blocked by `&C::StaticClass`, or by package-name literals that
  hand-written code also uses;
- statics next to items not modelled yet.

One enum registration initializer is `partial` (shared literal copy, see
`docs/REVERSE_ENGINEERING.md`). The per-manifest counts are in `analysis/functions-uht-*.json` |
| Named functions | 16,734 denominator functions (10.6 %) named from UHT reflection tables: 4,215 exec thunks, 11,127 `Z_Construct_UFunction_*` creators, and registrar/`GetPrivateStaticClass` pairs for 696 attributed classes. See `analysis/reflection-natives.json` |
| Whole-file identity | Not achievable as things stand: encrypted bodies on disk, a protector section and rewritten import references, a patched entry stub, and an Authenticode signature |
| IDA | IDA Professional 9.4 `idat.exe` headless export verified on a test binary. The reference has not been analysed in IDA yet |

## Protector effects that matching must account for

* Function bodies are encrypted on disk; the dump supplies them.
* The protector built its own import table in `.idata`. In the decrypted image 25,348
  `call [rip+X]` sites and all 761 import thunks reference that table. Only 62 call sites
  still reference the original linker IAT at the start of `.rdata`. `__imp_X` therefore
  resolves to either named slot of the same import; the manifest records which one matched.
* The section slack after the export, exception and resource directories, the `_RDATA` tail
  and all of `.gfids` hold protector code, not original data.

## Next verifiable tasks

1. Grow corroboration by reconstructing more callers of shared symbols. Candidates are
   `FCommandLine::Set`/`Append` (they reference the arrays and `bIsInitialized`) and other
   `FParse::Param` / `FCommandLine::Get` callers found by masked search over the decrypted image.
2. Resolve per-occurrence literal copies (no `/GF`, and holes are packed with literals from
   earlier in the TU). Either reconstruct the literal sequence of the surrounding Core unity
   TU, or accept the getters as relocation-equivalent.
3. Extend generated-code matching. 18,381 functions share the 47-byte UHT singleton shape.
   The callee and its parameter-record layout identify each kind:
   - 11,742 UFunction creators (`ConstructUFunction` `0x0138CF20`);
   - 3,283 class constructors (`ConstructUClass` `0x0138C5D0`);
   - 2,176 struct constructors (`ConstructUScriptStruct` `0x0138FA20`);
   - 1,094 enum constructors (`ConstructUEnum` `0x0138C910`);
   - 86 package constructors (`ConstructUPackage` `0x0138D3B0`).

   An earlier version of this file swapped the class and struct counts.

   Done:
   - 10,553 creators and 1,031 class constructors;
   - for 1,523 USTRUCTs, the constructor, `StaticStruct`, `NewStructOps` and both
     registration initializers;
   - for 1,094 UENUMs, the constructor, `StaticEnum` (824 plain) and the registration
     initializer.

   See the per-category counts above.

   Next:
   - The 587 structs whose `StaticStruct` inlines the package singleton (their `.gen.cpp`
     follows `<Module>.init.gen.cpp` in the unity file) and the 66 without `StaticStruct`
     (noexport).
   - Module layout model, in place: 182 unity units built from per-item fragments in the
     order recovered from `.CRT$XCU`. They contain all classes (`Classes.gen.h`,
     `IMPLEMENT_CLASS`), structs, enums, package-scope delegates, and package constructors at
     their `init.gen.cpp` position, which opens a unity file. Remaining:
     - the creators of the 11 function tables not attributed to a class;
     - the 7 intrinsic classes;
     - `GetPrivateStaticClass` fields (`InternalConstructor<C>` / `InternalVTableHelperCtorCaller<C>`,
       ICF-folded empty `StaticRegisterNatives`);
     - package-name literals in the registration initializers.
   - The remaining class constructors, 3,326 `GetPrivateStaticClass` bodies and the 4,215
     exec thunks.
4. Run the IDA export on the decrypted image for call graphs and cross-references.

## Reproduce

```
python tools/matching/fingerprint.py                    # analysis/build-fingerprint.json
python tools/matching/survey.py                         # analysis/plaintext-survey.json
python tools/matching/ingest_dump.py --dump <dump>      # local decrypted image + analysis/decrypted-reference.json
python tools/matching/selftest.py                       # build, compare --check, progress --verify
```
