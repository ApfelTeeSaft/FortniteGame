# Reverse-engineering method and findings

## Coordinates

All addresses are RVAs relative to image base `0x140000000`. Main `.text` maps
RVA `0x1000` to file offset `0x600`, so for RVAs in that section
`file offset = RVA - 0xA00`. Manifest ranges are `.pdata` `[BeginAddress, EndAddress)`,
which is the extent the compiler recorded, including any trailing `int3`.

## Code protection

Survey method (`tools/matching/survey.py`): every `RUNTIME_FUNCTION` is decoded, and
its `UNWIND_INFO` prologue codes are checked against a linear decode of the on-disk
bytes. The check covers push register, allocation size, frame register and register saves.

| Population | Count | Prologue agrees with unwind record |
| --- | --- | --- |
| `.pdata` entries | 253,131 | 11 |
| primary (non-chained) entries in main `.text` | 157,719 | 3: entry stub `0x02D996CC`, filters `0x02DAE750`, `0x02DAE780` |
| chained fragments | 95,412 | 8 |

Further observations:

* Inside low-entropy pages the `0xCC` inter-function padding is intact, but function
  bodies decode as random instructions. Encryption is therefore per function, not per page.
* Bytes outside every `.pdata` range (leaf code) are encrypted in the same way.
* `.rdata`, `.xdata` (unwind and scope tables), `.pdata`, imports and resources are plaintext.
* The entry point `0x02D996CC` (18 bytes, the shape of `mainCRTStartup`) keeps
  `sub rsp,28h`, but its first call targets RVA `0x04DDF2FC` in a second `.text` section
  (`0x04DDD000`, 3.5 MB, no `.pdata`). The rest of the stub is encrypted. The entry is
  therefore not matchable as on disk.
* Even exception-handler thunks are encrypted, so handler identities must come from usage
  patterns, not bytes.

## Decrypted reference (`tools/matching/ingest_dump.py`)

The owner supplied a PE-file dump of the running module, which stays local and is never
committed. Ingestion maps it through its own section table and handles the load base: the
delta is the value agreed by all 200,000 sampled DIR64 sites in plaintext sections, and it
is subtracted at all 788,029 sites. The dump is accepted only if it is byte-identical to the
original over the linker-produced extents: `.rdata` from the end of the original IAT to the
end of the export directory, plus the exception and resource directories. Every other
differing byte is accounted for:

| Region | Differing bytes | Explanation |
| --- | --- | --- |
| original IAT at `.rdata` start | 4,790 | runtime-bound import addresses |
| `.rdata` after the export directory | 21,474 | protector code (former import directory and names) |
| `.pdata` after the exception directory, `.rsrc` after the resource directory, `_RDATA` tail, `.gfids` | 897 | protector code in section slack |

After ingestion, 157,439 of 157,632 primary functions with unwind codes have prologues that
agree with their records (99.88 %). On disk only 3 do.

The decrypted image is the protector's runtime view, which differs from the linker output in
one systematic way: import references. The protector built a new import table in `.idata`
and pointed 25,348 `call [rip+X]` sites and every import thunk at it. 62 call sites still use
the original IAT. `symbols_auto.py` names both tables independently. The `.idata` slots are
named by their plaintext descriptors. Original IAT slots are named through the runtime
address they share with exactly one protector slot. A field may match either slot of the
same import, and the manifest records which.

## Matching rules (`tools/matching/compare.py`)

* `exact`: sizes are equal and every byte is identical to the reference: on-disk bytes where
  plaintext, otherwise the validated decrypted image (`reference_state: decrypted`). A
  relocation field counts only if its symbol resolves from evidence independent of the bytes
  being compared:
  - `analysis/symbols.json`;
  - import tables;
  - a unique import thunk;
  - a unique data match: a NUL-terminated literal on a string boundary, or a data block at
    its alignment;
  - an already-exact function, iterated to a fixpoint;
  - **corroboration (leave-one-out):** the same symbol observed at one address in a
    *different* manifest function whose size and every non-relocation byte equal the
    reference. Internal-linkage symbols (literals, statics) count only within the same
    object file. Observations made in the function under test are never used for its own
    fields, and conflicting observations resolve nothing;
  - **section-relative (leave-one-out):** a symbol in a non-COMDAT data section, predicted
    from a neighbour in that section that another function observed, using the
    object-file offset difference. Every prediction must agree.

  Nothing is masked. Every resolved field records its evidence in `analysis/functions.json`,
  and a wrong prediction simply fails the byte comparison. The repository owner approved
  counting corroborated fields toward `exact` on 2026-11-20.
* `relocation-equivalent`: identical except for unresolved relocation fields. Not exact.
* `partial` / `unmatched`: some or no bytes agree.
* `unknown`: the reference body is encrypted and no decrypted image is available.
  Structural evidence is recorded alongside but never upgrades the state.

`compare.py --check` on a machine without the local decrypted image skips the entries that
were verified against it and reports how many it skipped.

Structural evidence compares plaintext metadata with the compiled object: the `.pdata`
size, the `UNWIND_INFO` header and codes, and C scope-table entries. Scope entries are
compared as offsets from the function start; filter fields are compared through the
manifest RVA of an exactly matched funclet. Handler RVAs are reported, not compared,
until their identity is independently established.

## Denominator

The denominator is the 157,719 primary `.pdata` functions in the main `.text`. It
includes compiler-generated funclets, CRT and third-party code because encrypted
bodies make finer classification impossible. Leaf functions without `.pdata` are not
counted. Exact matches are broken down by category in the progress image.

## First reconstructed family: delay-load SEH guards (D3D11RHI / D3D12RHI)

Parents were found through C scope tables whose filter field points at the two
plaintext funclets:

| RVA | Function | Result |
| --- | --- | --- |
| `0x02DAE750` | filter of `SafeTestD3D11CreateDevice` | exact vs on-disk bytes, 42/42 |
| `0x02DAE780` | filter of `SafeCreateDXGIFactory` (ICF-folded, two parents) | exact vs on-disk bytes, 42/42. The D3D12 source compiles to the same bytes |
| `0x016138D0` | `SafeCreateDXGIFactory` (D3D11) | exact vs decrypted image, 26/26. GUID resolved by unique content, `CreateDXGIFactory1` by its import thunk |
| `0x0165FEB0` | `SafeCreateDXGIFactory` (D3D12-shaped twin) | exact vs decrypted image, 26/26 (IDXGIFactory4 GUID, `CreateDXGIFactory` thunk) |
| `0x016138F0` | `SafeTestD3D11CreateDevice` | exact vs decrypted image, 318/318. `FParse::Param` via its exact match; `FCommandLine::Get` and the three literals corroborated by `D3D11RHI_ShouldCreateWithD3DDebug` |
| `0x015FEDD0` | `D3D11RHI_ShouldCreateWithD3DDebug` | exact vs decrypted image, 88/88, corroborated the other way. Located by content: the only same-shape function whose literals read `d3ddebug`/`d3debug`/`dxdebug` (the other reads `NoEpicPortal`/`q`/`EpicPortal`) |

## Second family: Core command-line helpers

| RVA | Function | Result |
| --- | --- | --- |
| `0x011BFED0` | `FParse::Param` | exact vs decrypted image, 376/376. Inlines `TCString::Strifind(..., true)`, the `wcslen` loop and `iswspace`; `_wcsnicmp`/`iswspace` resolve through import tables |
| `0x01193BC0` | `FCommandLine::Get` | relocation-equivalent. `bIsInitialized`, `LogInit`, `FMsg::Logf_InternalImpl` and `FDebug::AssertFailed` are corroborated by the other getters, but its five literal copies are not |
| `0x01194B20` | `FCommandLine::GetForLogging` | relocation-equivalent (same reason) |
| `0x011953C0` | `FCommandLine::GetOriginalForLogging` | relocation-equivalent (same reason) |
| `0x01199E30` | `FCommandLine::IsInitialized` | exact, 8/8, but a leaf without `.pdata` (outside the denominator) and located by its own signature |
| — | `FCommandLine::GetOriginal` | not present in the image: no function matches even with the line immediate ignored. Presumably removed by `/OPT:REF` |

The fatal-log line immediates (29, 35, 47) and the `"Unknown"` source file (`DO_CHECK 0`)
agree with public 4.20.0. Without `/GF` every literal occurrence gets its own copy. The
original unity TU also packs small literals into alignment holes left by earlier literals,
so a literal used once with repeated text cannot be pinned to its copy until more of that
TU is reconstructed. Those fields stay unresolved rather than guessed.

Before the dump arrived, structural matches had already pinned down two differences from
public 4.20.0 (see [ENGINE_DIFFERENCES.md](ENGINE_DIFFERENCES.md)). They also showed
that `D3D11RHI_ShouldCreateWithD3DDebug` is inlined across files, i.e. a unity build.
Byte comparison against the decrypted bodies confirmed both differences.

## Reflection registration data (`tools/analysis/reflection.py`)

UHT-generated tables in plaintext `.rdata` name functions directly. The output is
`analysis/reflection-natives.json`, with names and RVAs only.

| Table | Layout | Found |
| --- | --- | --- |
| `FNameNativePtrPair[]` (per class, in `StaticRegisterNatives<Class>`) | {name, exec thunk} | 956 arrays, 4,460 entries, 4,215 distinct exec thunks (some ICF-folded) |
| `FClassFunctionLinkInfo[]` (per class, in `FClassParams`) | {`Z_Construct_UFunction_*`, name} | 1,249 arrays, 11,130 entries |

The two layouts interleave the same pointer kinds, so a run read at the wrong 8-byte
alignment looks like the other table with one entry fewer. Each run takes the reading with
the longer run.

Class attribution follows unique RIP-relative `LEA` references in the decrypted code: the
native array is loaded by exactly one function (`StaticRegisterNatives<Class>`). That
function's address is loaded by exactly one function (`GetPrivateStaticClass`), which also
loads `TEXT("<Class>") + 1`, i.e. a wide string + 2. This attributes 696 of 956 arrays. No
class, registrar or `GetPrivateStaticClass` is shared between attributions. In total
16,734 denominator functions (10.6 %) now carry reflection-derived names. Names from these
tables count as `confirmed`; class attribution as `high-confidence inferred`.

## Naming confidence

`confirmed` needs direct evidence such as an exported symbol, reflection string or
debug data. Names inferred from engine source plus unique structural agreement are
`high-confidence inferred`. Shape-only agreement is `low-confidence inferred`.
