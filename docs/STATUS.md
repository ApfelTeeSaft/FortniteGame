# Status

Stage 1 (exact-match client decompilation): **in progress, blocked for bulk matching** by on-disk code encryption.
Stages 2–4 have not started.

| Item | State (verified 2026-11-20) |
| --- | --- |
| Reference | `FortniteClient-Win64-Shipping.exe`, 82,298,304 bytes, SHA-256 `9731a6b5…eb449102`, linked 2018-02-14, `++Fortnite+Release-2.5-CL-3889387`, version resource `4.20.0-3889387` |
| Compiler evidence | Rich header: Utc1900 C/C++ build 24215, Linker 14.00.24215, no LTCG product ids. The local v140 `cl.exe` is 19.00.24215.1 and its objects carry `@comp.id` prodid 261, build 24215 |
| VS2019 solution | `FortniteGameCode.sln` `ClientShipping\|x64` (toolset v140) builds with 0 errors and 0 warnings |
| Exact functions | **2 / 157,719** primary `.pdata` functions (0.0013 %), both SEH filter funclets (84 bytes). Raw-byte identical, no relocations, no masking |
| Structure-only evidence | 3 parents whose compiled size, every unwind code and C scope offsets equal the reference records. Their bodies are encrypted, so the match state stays `unknown` |
| Code protection | 157,716 of 157,719 primary functions fail the prologue-vs-unwind check. Leaf code outside `.pdata` is encrypted too. See [REVERSE_ENGINEERING.md](REVERSE_ENGINEERING.md#code-protection) |
| Whole-file identity | Not achievable as things stand: encrypted bodies, a protector section, a patched entry stub and an Authenticode signature (`0x17C0` bytes) |
| IDA | IDA Professional 9.4 `idat.exe` headless export verified on a test binary. The reference has not been analysed in IDA this cycle (encrypted bodies) |

## Blocker: no plaintext code to match against

Each function body in the main `.text` is encrypted separately; the `0xCC` padding,
`.pdata`, `.xdata` and `.rdata` are plaintext. The entry stub calls into a second
`.text` section that has no `.pdata`, which is presumably the runtime decryptor.
Byte matching needs a decrypted image of this exact build. Producing one means
running the client or defeating its protection, which is the owner's decision.
The project has not done either. Until a decrypted reference is supplied, exact
matching is limited to the few plaintext units.

## Next verifiable tasks

1. **Needs owner decision:** obtain a decrypted image of build CL 3889387. Then add it as a
   second, separately fingerprinted reference (never committed). Teach `compare.py` to use
   it for bodies and the original file for metadata.
2. Use plaintext metadata to locate more functions: compiled size plus unwind record plus
   scope/GS data. This works where a reconstruction yields a unique signature among the
   157,719 records. Record these as structural evidence, never as `exact`.
3. Recover reflection data from plaintext `.rdata`/`.data`: UClass/UFunction registration
   tables and native function pointers. That maps names onto `.pdata` ranges ahead of body
   matching.
4. Identify the three most-used exception handlers: 10,095 records use RVA `0x02D98C70`,
   1,415 use `0x02D9AE16` and 465 use `0x02D993EC`. Fix their CRT identities from evidence
   and add them to `analysis/symbols.json` with that evidence.

## Reproduce

```
python tools/matching/fingerprint.py      # analysis/build-fingerprint.json
python tools/matching/survey.py           # analysis/plaintext-survey.json
python tools/matching/selftest.py         # build, compare --check, progress --verify
```
