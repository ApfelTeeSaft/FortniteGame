# Status

Stage 1 (exact-match client decompilation): **in progress**. A validated decrypted image of
the reference build now supplies plaintext function bodies. Stages 2–4 have not started.

| Item | State (verified 2026-11-20) |
| --- | --- |
| Reference | `FortniteClient-Win64-Shipping.exe`, 82,298,304 bytes, SHA-256 `9731a6b5…eb449102`, linked 2018-02-14, `++Fortnite+Release-2.5-CL-3889387`, version resource `4.20.0-3889387` |
| Decrypted reference | Owner-supplied PE dump, SHA-256 `c81fe58a…2f97370`, local only. After un-rebasing all 788,029 DIR64 sites it is byte-identical to the original over 23.5 MB of linker-produced plaintext. Prologues verify for 157,439 of 157,632 primary functions with unwind codes (99.88 %). See `analysis/decrypted-reference.json` |
| Compiler evidence | Rich header: Utc1900 C/C++ build 24215, Linker 14.00.24215, no LTCG product ids. The local v140 `cl.exe` is 19.00.24215.1 and its objects carry `@comp.id` prodid 261, build 24215 |
| VS2019 solution | `FortniteGameCode.sln` `ClientShipping\|x64` (toolset v140) builds with 0 errors and 0 warnings |
| Exact functions | **4 / 157,719** primary `.pdata` functions (0.0025 %, 136 bytes). Two match on-disk plaintext (SEH filter funclets). Two match the decrypted image (`SafeCreateDXGIFactory` in D3D11RHI and its D3D12-shaped twin), with every relocation resolved from independent evidence |
| Relocation-equivalent | `SafeTestD3D11CreateDevice` and `D3D11RHI_ShouldCreateWithD3DDebug`: every non-relocation byte is identical. Three wide literals occur 3+ times in `.rdata`, and `FCommandLine::Get`/`FParse::Param` are not matched yet |
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

1. Recover `FCommandLine::Get` (`0x01193BC0`, 0x6C bytes) and `FParse::Param` (`0x011BFED0`,
   0x178 bytes) from Core. Matching them resolves the callee fields of two pending functions
   through the fixpoint. `Get` needs the shipping expansion of `UE_CLOG(..., Fatal, ...)`.
2. Resolve per-TU string literal copies. With `/Ox` there is no string pooling, so identical
   literals repeat per translation unit. This needs a faithful unity layout or more of
   each TU's literals.
3. Recover reflection data from plaintext `.rdata`/`.data` (UClass/UFunction registration
   and native function tables) to name `.pdata` ranges at scale, then batch-match small
   leaf-like functions.
4. Run the IDA export on the decrypted image for call graphs and cross-references.

## Reproduce

```
python tools/matching/fingerprint.py                    # analysis/build-fingerprint.json
python tools/matching/survey.py                         # analysis/plaintext-survey.json
python tools/matching/ingest_dump.py --dump <dump>      # local decrypted image + analysis/decrypted-reference.json
python tools/matching/selftest.py                       # build, compare --check, progress --verify
```
