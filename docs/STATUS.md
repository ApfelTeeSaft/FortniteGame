# Status

Stage 1 (exact-match client decompilation): **in progress**. A validated decrypted image of
the reference build now supplies plaintext function bodies. Stages 2–4 have not started.

| Item | State (verified 2026-11-20) |
| --- | --- |
| Reference | `FortniteClient-Win64-Shipping.exe`, 82,298,304 bytes, SHA-256 `9731a6b5…eb449102`, linked 2018-02-14, `++Fortnite+Release-2.5-CL-3889387`, version resource `4.20.0-3889387` |
| Decrypted reference | Owner-supplied PE dump, SHA-256 `c81fe58a…2f97370`, local only. After un-rebasing all 788,029 DIR64 sites it is byte-identical to the original over 23.5 MB of linker-produced plaintext. Prologues verify for 157,439 of 157,632 primary functions with unwind codes (99.88 %). See `analysis/decrypted-reference.json` |
| Compiler evidence | Rich header: Utc1900 C/C++ build 24215, Linker 14.00.24215, no LTCG product ids. The local v140 `cl.exe` is 19.00.24215.1 and its objects carry `@comp.id` prodid 261, build 24215 |
| VS2019 solution | `FortniteGameCode.sln` `ClientShipping\|x64` (toolset v140) builds with 0 errors and 0 warnings |
| Exact functions | **12,287 / 157,719** primary `.pdata` functions (7.79 %, 569,030 bytes):
- 2 matching on-disk plaintext (SEH filter funclets);
- 5 hand-reconstructed functions matching the decrypted image;
- 12,280 generated UHT functions: 10,553 UFunction creators, 1,031 `Z_Construct_UClass_*` and
  696 `StaticRegisterNatives*`.

Every relocation is resolved from independent or leave-one-out evidence. Also exact, outside the denominator: 533 `StaticClass` thunks and `FCommandLine::IsInitialized` |
| Relocation-equivalent | 104: three `FCommandLine` getters (per-occurrence literal copies), 98 generated creators and 3 class constructors (layout gaps). `FCommandLine::GetOriginal` is absent from the image (presumably `/OPT:REF`) |
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
3. Extend generated-code matching. 18,381 functions share the 47-byte UHT singleton shape:
   - 11,742 UFunction creators;
   - 3,283 struct constructors;
   - 2,176 `Z_Construct_UClass_*` constructors;
   - 1,094 enum constructors;
   - 86 package constructors.

   Struct, enum and package-scope delegate constructors need a per-header `.bss` model:
   - each struct contributes `ReturnStruct` *and* its `StaticStruct` singleton;
   - function-less classes put `GetPrivateStaticClass`'s slot before `OuterClass`;
   - code order does not follow slot order.

   Reconstructing `StaticStruct`/`StaticEnum` (and `GetPrivateStaticClass`) supplies those
   neighbours without circular ordering. Next comes the 4,215 exec thunks (`DEFINE_FUNCTION`),
   already named, whose call targets are mostly corroborated natives.
4. Run the IDA export on the decrypted image for call graphs and cross-references.

## Reproduce

```
python tools/matching/fingerprint.py                    # analysis/build-fingerprint.json
python tools/matching/survey.py                         # analysis/plaintext-survey.json
python tools/matching/ingest_dump.py --dump <dump>      # local decrypted image + analysis/decrypted-reference.json
python tools/matching/selftest.py                       # build, compare --check, progress --verify
```
