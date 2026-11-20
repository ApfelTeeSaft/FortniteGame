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
  - a unique data match: a NUL-terminated literal, or a data block at its alignment. A
    literal occurrence counts if it is aligned to its character width and preceded by a zero
    byte. A wide literal directly after a narrow string ("idx\0" then L"...") cannot be told
    apart from a wide suffix, so both count; over-counting only turns a unique result into
    an ambiguous one;
  - **literal elimination (leave-one-out):** without `/GF` each use of a literal has its own
    copy. All copies of the content are enumerated (fewer than 64). If every copy but one is
    the observed target of a *different* symbol, in *other* relocation-equivalent-or-better
    functions, the remaining copy is this symbol's;
  - an already-exact function, iterated to a fixpoint;
  - **corroboration (leave-one-out):** the same symbol observed at one address in a
    *different* manifest function whose size and every non-relocation byte equal the
    reference. Internal-linkage symbols (literals, statics) count only within the same
    object file. Observations made in the function under test are never used for its own
    fields, and conflicting observations resolve nothing;
  - **section-relative (leave-one-out):** a data symbol is predicted from neighbours that
    *other* functions observed. Neighbours are taken from the object's data layout, i.e.
    same-named sections, COMDATs included, in object order with their alignment, as the
    linker places one object's contributions. The prediction supported by the most
    neighbours is used if it strictly outnumbers every alternative. A prediction that then
    fails to reproduce the reference bytes is reported as an unresolved field, not as a
    byte difference.

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

## Third family: UHT UFunction creators (generated, `tools/codegen/uht_creators.py`)

11,097 of the 11,127 `Z_Construct_UFunction_*` / `Z_Construct_UDelegateFunction_*` creators
have the same 47-byte body. UHT 4.20 emits it for
`static UFunction* ReturnFunction; if (!ReturnFunction) ConstructUFunction(ReturnFunction, Statics::FuncParams); return ReturnFunction;`.
The generator writes one UHT-shaped translation unit per class
(`FortniteGameCode/Source/Generated/UHT/<Class>.gen.cpp`, 1,238 classes). Each
`FFunctionParams` value is decoded from the binary's own record.

Each creator has five relocation fields, all resolved without reading the creator's code:

| Field | Evidence |
| --- | --- |
| `Statics::FuncParams` | content: the only `FFunctionParams` record in `.data` whose `NameUTF8` names the function. For 2,034 shared names, the only one also matching the class's consensus `OuterFunc`. Where the name was unique (9,063 creators), the record agreed with each creator's `lea` in every case |
| `ConstructUFunction` | corroborated by the other creators |
| `ReturnFunction` (3 fields) | section-relative to sibling creators' observed slots. Each static local gets its own COMDAT `.bss` section, which the linker places in object order |

Ordering was established from the reference. A class's delegate signatures come first,
in header order (their creators' code addresses preserve it). Its functions follow,
sorted by name, which is also the `FClassFunctionLinkInfo` order. Some classes have
unreconstructed statics between the two blocks, which the majority rule tolerates.

Results:

| Count | State |
| --- | --- |
| 10,342 | exact against the decrypted image |
| 309 | relocation-equivalent: 208 classes have a single creator, so no sibling can predict its `ReturnFunction`; the rest sit across layout gaps |
| 446 | not emitted: no unique `FFunctionParams` record |

### Class constructors

The same 47-byte shape also covers class, struct, enum and package constructors: 18,381
functions in all. The callee and the layout of the parameter record each one loads tell
them apart:

| Callee | Record | Singletons |
| --- | --- | --- |
| `ConstructUFunction` `0x0138CF20` | `FFunctionParams` (`.data`) | 11,742 |
| `ConstructUClass` `0x0138C5D0` | `FClassParams` (`.rdata`) | 3,283 |
| `ConstructUScriptStruct` `0x0138FA20` | `FStructParams` (`.data`) | 2,176 |
| `ConstructUEnum` `0x0138C910` | `FEnumParams` (`.data`) | 1,094 |
| `ConstructUPackage` `0x0138D3B0` | `FPackageParams` (`.rdata`) | 86 |
 For the 1,034 classes whose
`FFunctionParams` records agree on one `OuterFunc`, the generator also emits the class
constructor, with:
- `FuncInfo[]` rebuilt from the function table;
- `StaticCppClassTypeInfo`, flags, counts and config name decoded from `FClassParams`;
- dependency, property and interface arrays declared but still pending.

The fields resolve the same way as for creators:
- `ClassParams` from the `FClassParams` record that references the class's function table;
- `ConstructUClass` corroborated;
- `OuterClass` section-relative, with UHT emitting the class constructor right after the
  class's functions.

1,031 are exact. The added `OuterClass` neighbour also resolves most single-creator classes,
raising exact creators from 10,342 to 10,553.

### Native registrars and `StaticClass` thunks

`StaticRegisterNatives<Class>` is a uniform 34-byte function: `call GetPrivateStaticClass`,
`mov r8d, N`, `lea rdx, Funcs`, tail-`jmp RegisterFunctions`. All 696 attributed registrars
are exact. Their fields resolve as follows:

| Field | Evidence |
| --- | --- |
| `Funcs` | the class's `FNameNativePtrPair` array from the reflection tables |
| `RegisterFunctions` | corroborated across registrars |
| `GetPrivateStaticClass` | the unique function that LEA-loads `&StaticRegisterNatives<Class>` (part of the attribution chain), or corroboration by the class's `StaticClass` thunk |

The thunk (`jmp GetPrivateStaticClass`, 5 bytes, no `.pdata` entry, named by `FClassParams`) is
emitted because the class constructor takes `&Class::StaticClass`. 533 thunks are exact. They
are reported outside the denominator, so they don't count toward the headline figure.

### Struct constructors and `StaticStruct` (`tools/codegen/uht_structs.py`)

A USTRUCT's UHT 4.20 output, in order:
1. `F<S>::StaticStruct()`: static `Singleton`, then `GetStaticStruct(Z_Construct_UScriptStruct_F<S>, <package singleton>(), TEXT("<S>"), sizeof, Get_..._CRC())`.
2. Two registration objects with dynamic initializers: `FCompiledInDeferStruct` and `FScriptStruct_<Pkg>_StaticRegisterNatives<S>`.
3. The `_Statics` (`NewStructOps`, property parameters, `ReturnStructParams`).
4. `Z_Construct_UScriptStruct_F<S>()`: static `ReturnStruct`.
5. `Get_..._CRC()`.

The two registration objects are emitted at the end of each generated file instead (see
**Statics layout** below).

In the reference, `StaticStruct` takes one of two forms:
- 1,523 compile to an 82-byte function split into three `.pdata` fragments: a primary entry
  and two chained ones. MSVC shrink-wraps the `rbx` save into the slow path.
- 587 inline the package singleton. This happens when the struct's `.gen.cpp` follows
  `<Module>.init.gen.cpp` in the module's unity file.

The plain form is the attribution chain. Its LEA of a 47-byte singleton identifies that
singleton as the struct's constructor, and its wide literal gives the name. The generator
writes one translation unit per plain struct:

| Field | Evidence |
| --- | --- |
| `ReturnStructParams` | the only `FStructParams` record in `.data` with this `NameUTF8` and package `OuterFunc` |
| `ConstructUScriptStruct`, `GetStaticStruct` | corroborated across constructors / `StaticStruct`s |
| `ReturnStruct` / `Singleton` | section-relative to each other (leave-one-out) |
| package singleton | the 47-byte singleton whose `FPackageParams` name the package |
| `Get_..._CRC` | the only 16-byte-aligned `mov eax, imm32; ret` with that constant |
| `Z_Construct_UScriptStruct_F<S>` (in `StaticStruct`) | the exact constructor |
| `TEXT("<S>")` (three copies) | literal elimination: one copy each for `StaticStruct` and the two registration initializers |
| `TCppStructOps<F<S>>` vtable | corroborated between `NewStructOps` and the `StaticRegisterNatives` initializer |
| `operator new`, `FName::FName`, `DeferCppStructOps`, `UObjectCompiledInDeferStruct` | corroborated |

Locating the other functions:
- `NewStructOps` is the record's `StructOpsFunc` (53 bytes). `/OPT:ICF` folded identical
  bodies, so 1,294 functions serve 1,523 structs, and a shared body lists the other structs as
  folded sources.
- The two registration initializers sit in the grouped dynamic-initializer code. The
  `FCompiledInDeferStruct` one is the only function of its 66-byte shape that loads the
  struct's `StaticStruct`. The `StaticRegisterNatives` one is the only function of its
  92-byte shape whose `FName` literal is the struct name, with `sizeof`/`alignof` equal to the
  record's.

`ICppStructOps` is shimmed with the engine layout and constructor only. Construction code
does not depend on the vtable's contents, and only its address is resolved.

**Statics layout.** MSVC puts each function-local static in its own COMDAT `.bss` section,
but every zero-initialized namespace-scope object of a translation unit shares one plain
`.bss` section. That section is created at the first such object. In the original unity
file an earlier object created it, so each struct's `Singleton` and `ReturnStruct` are
adjacent: 1,514 of 1,523 have `ReturnStruct == Singleton + 8`.

A per-struct translation unit with the registration objects in UHT position would put that
section between the two (offsets 0/8/9/16). The generator therefore emits them at the end
of the file, which leaves code generation unchanged: none of these functions inlines
another. The other 9 structs have further statics between the two slots, so the prediction
fails and they stay relocation-equivalent.

**Results.** Exact:
- 1,514 constructors;
- 1,423 `StaticStruct`s;
- all 1,294 `NewStructOps`;
- 1,427 `StaticRegisterNatives` initializers.

The `FCompiledInDeferStruct` initializers stay relocation-equivalent. Their
`L"/Script/<Package>"` literal has one copy per registered type of the package, too many to
enumerate.

The remaining `StaticStruct`s and struct-ops initializers stay relocation-equivalent for two
reasons:
- 9 have layout gaps;
- 91 have a name literal with an extra copy whose user is not yet reconstructed. Elimination
  then declines, as it must.

**Fork note.** The registration initializers live in the grouped dynamic-initializer
code. They call `UObjectCompiledInDeferStruct(..., FName(TEXT("<S>")), ...)`, as the local
4.20 source declares, and `UScriptStruct::DeferCppStructOps(FName, new TCppStructOps<F<S>>)`.

**Data placement.** `FFunctionParams` and `FStructParams` sit in `.data` and `FClassParams` in
`.rdata`, in the reference and in this repository's own v140 build alike. This is compiler
behaviour, not an engine difference.

Open data question, which doesn't affect the matched code: `PropPointers` arrays are declared
but not yet reconstructed (property-parameter recovery).

### Enum constructors and `StaticEnum` (`tools/codegen/uht_enums.py`)

UHT 4.20 emits per UENUM:
1. a file-static `<E>_StaticEnum()` (static `Singleton`, `GetStaticEnum(ctor, package(), TEXT("<E>"))`);
2. an `FCompiledInDeferEnum` object;
3. `Get_..._CRC()`;
4. `Z_Construct_UEnum_<Pkg>_<E>()`, with static `ReturnEnum` and local static `Enumerators[]` and
   `EnumParams`.

A `.gen.cpp` lists its enums before its structs, delegates and classes. All 1,094 enum
singletons are LEA-loaded by exactly one `StaticEnum`:
- 824 have the 55-byte plain form;
- 270 have an 85-byte form that inlines the package singleton.

`Get_..._CRC` is unreferenced in a shipping build. `/OPT:REF` removed it, so its constant is
not in the image and it is not emitted.

**Two blocks.** MSVC compiles file-static functions first. Their code starts each unity
translation unit's `.text`, and their statics form a block at the start of its `.bss`, where
all `StaticEnum` singletons sit. Each `ReturnEnum` sits elsewhere, in its header's COMDAT
sequence, e.g. `[ReturnEnum][creators…][OuterClass][PrivateStaticClass]`. The two slots are
never neighbours, unlike `Singleton`/`ReturnStruct` for structs.

**Source order from `.data`.** UHT parameter records (`FEnumParams`, `FStructParams`,
`FFunctionParams`) are emitted to `.data` in definition order. For 967 of 1,094 enums, the
item whose record follows the enum's record also owns the next COMDAT `.bss` slot. This
statistic only supported the design and is never used as evidence. The generator groups
enums whose records are consecutive, with no other UHT record between, into runs, and never
reads a `.bss` address to do so.

Each run gets two translation units that reproduce the two blocks:
- `<First>.gen.cpp`: the constructors, whose `ReturnEnum`s anchor each other;
- `<First>.static.gen.cpp`: the `StaticEnum` functions and registration objects, whose
  `Singleton`s anchor each other.

A single translation unit would let the `Singleton` block outvote the `ReturnEnum`
neighbours. The split doesn't change code generation.

| Field | Evidence |
| --- | --- |
| `EnumParams` (`?EnumParams@?4??…`) | the only `FEnumParams` record in `.data` with this name and package `OuterFunc` |
| `ReturnEnum` / `Singleton` | section-relative within the run (leave-one-out) |
| constructor (in `StaticEnum`) | the exact constructor |
| `TEXT("<E>")` | literal elimination against the registration initializer |
| package singleton | its `FPackageParams` name |
| `ConstructUEnum`, `GetStaticEnum`, `FName::FName`, `UObjectCompiledInDeferEnum` | corroborated |

**Results.**
- 695 constructors are exact. The other 399 have no neighbour: 284 runs hold a single enum,
  and some runs are broken in the reference.
- 252 `StaticEnum`s are exact. Others lack a `Singleton` neighbour (the static-function order
  departs from record order), an exact constructor, or a unique literal.
- The 824 registration initializers are relocation-equivalent, because of the package-name
  literal.

Enumerator values are emitted as the integers stored in the reference. The C++ enum
declarations, including their underlying types, are not recovered.

## Naming confidence

`confirmed` needs direct evidence such as an exported symbol, reflection string or
debug data. Names inferred from engine source plus unique structural agreement are
`high-confidence inferred`. Shape-only agreement is `low-confidence inferred`.
