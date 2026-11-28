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
  - a unique data match: a NUL-terminated literal, or a data block at its alignment, searched
    in the read-only data; a block of 64 bytes or more also in `.data` (an initialized table
    such as `FLinearColor::sRGBToLinearTable`), with the occurrence unique over both. A
    literal occurrence counts if it is preceded by a zero byte and aligned to its character
    width, or to 8 bytes for a literal of 8 bytes or more (terminator included): MSVC places
    every such literal on an 8-byte boundary. A short wide literal directly after a narrow
    string ("idx\0" then L"...") cannot be told apart from a wide suffix, so both count;
    over-counting only turns a unique result into an ambiguous one;
  - **literal elimination (leave-one-out):** without `/GF` each use of a literal has its own
    copy. All copies of the content are enumerated (fewer than 4,096). If every copy but one is
    the observed target of a *different* symbol, in *other* relocation-equivalent-or-better
    functions, the remaining copy is this symbol's. A copy no entry observes is claimed by
    other code when, with the function under test masked out:
    - exactly one `lea [rip+disp]` in the reference targets it (or the literal one character
      in). Two or more sites mean a pooled copy, such as `StaticPackage()`'s COMDAT literal,
      which claims nothing;
    - it lies inside another object's observed literal span; or
    - another object's observed literal lies between it and the span of this object's literals
      that *other* entries observe. One object's `$SG` literals are one contiguous block.
  - **pooled float constants** (`__real@<hex>`, named by their value): the only aligned copy
    of the value in `.rdata`. Among several copies, the only one that scalar float/double code
    outside the function under test loads: `movss`/`addss`/`mulss`/... or `comiss`/`ucomiss`
    with a rip-relative operand. Other copies are table fields or lanes of vector constants.
    When scalar code loads several copies, the one loaded by at least 10 functions and by at
    least 10 times as many functions as the next copy. 16-byte `__xmm@` constants use the same
    rule with packed loads (`movaps`, `andps`, `mulps`, `pxor`, ...);
  - `__ImageBase` (linker-defined, RVA 0), and a label inside the function under test (a jump
    table's `$LN` case labels), placed from the function's own start as a branch inside it is;
  - an already-exact function, iterated to a fixpoint;
  - **corroboration (leave-one-out):** the same symbol observed at one address in a
    *different* manifest function whose size and every non-relocation byte equal the
    reference. Internal-linkage symbols (literals, statics) count only within the same
    object file. Observations made in the function under test are never used for its own
    fields, and conflicting observations resolve nothing;
  - **ICF-folded body (leave-one-out):** `/OPT:ICF` gives identical COMDAT functions one
    address. A function that is a whole relocation-free COMDAT of at most 16 bytes (`return
    nullptr`, an empty function) is identified by its section name and bytes as well as by its
    name. Other entries' observations of *any* function with the same body give its address;
    conflicting observations resolve nothing;
  - **code layout, `InternalConstructor<C>` only (leave-one-out):** see "`GetPrivateStaticClass`
    fields";
  - **section-relative (leave-one-out):** a data symbol is predicted from neighbours that
    *other* functions observed. Neighbours are taken from the object's data layout, i.e.
    same-named sections, COMDATs included, in object order with their alignment, as the
    linker places one object's contributions. Local first: on each side, the run of
    observed neighbours nearest the symbol that agree with each other gives a prediction.
    The prediction is used if the two sides agree, or if only one side has observed
    neighbours. A layout gap elsewhere in a large unit therefore cannot outvote the
    symbol's immediate neighbours. If the two sides disagree (a gap next to the symbol), a
    vtable goes where its exact slot functions' pointers are together and nowhere else (its
    first slot need not be among them). Otherwise each side's run of agreeing observed
    neighbours is counted, and the strictly longer run decides. Equal runs go to the vtable
    and slot-elimination rules, then to the side whose nearest observed neighbour has fewer
    layout items between it and the symbol, then fewer bytes (2026-11-27, "Engine class
    layouts"). In `.bss` and `.data` a slot that other entries
    observe holding another symbol is never predicted, since writable data is not folded. A
    side whose prediction lands there is dropped and the other side decides. If both sides
    land on such slots, nothing is resolved. A prediction that then fails to reproduce the
    reference bytes is reported as an unresolved field, not as a byte difference.

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

## Fourth family: command-line switch checks (hand-written, 2026-11-24)

`FParse::Param` (exact) and `FCommandLine::Get` are called together by 229 functions in the
decrypted image, 145 of them primary `.pdata` functions. Each loads its switch names as wide
literals. 101 of the 145 load a literal that the 4.20 tree passes to
`FParse::Param(FCommandLine::Get(), TEXT("..."))`, which names the function. Most have
function-local statics (thread-safe initialization), use members of their class, or are
fragments of split functions.

The first batch is the complete ones that touch nothing else:

| RVA | Function | Result |
| --- | --- | --- |
| `0x01112B50` | `FGenericPlatformMisc::AllowThreadHeartBeat` | exact |
| `0x015FECE0` | `D3D11RHI_PreferAdaperVendor` (the 4.20 spelling) | exact |
| `0x0164F8A0` | `D3D12RHI_PreferAdapterVendor` | exact; `static inline` in the tree but out of line in the reference, kept by the TU's anchor table |
| `0x008641F0` | neutral `FortniteGame_NoAlternateAIDirectorBalance_008641F0` | exact; Fortnite switch, no source |
| `0x00EF0D50` | neutral `FortniteGame_NoActivities_00EF0D50` | exact; Fortnite switch, no source |
| `0x02517390` | `FLauncherCheckModule::WasRanFromLauncher` (`IsEnabled()` inlined) | relocation-equivalent: `TEXT("q")` |
| `0x01FFE540` | `UGameplayStatics::HasLaunchOption` | relocation-equivalent: the `TEXT("")` of `FString::operator*` |

Every relocation of the exact five is evidenced:
- `FParse::Param` by its exact match;
- `FCommandLine::Get` by corroboration;
- each switch literal by its unique content. The two adapter-vendor twins each hold a copy of
  the same three literals, so those resolve by literal elimination against each other.

The two others each wait on a pooled `??_C@` literal of an inline function: `L"q"`, and
`L""`. Both are too short to find by content. A second reconstructed user of the same pooled
literal would corroborate it.

Infrastructure added:
- `Shims/FortniteGameCode/CommandLineDecls.h` declares `FCommandLine`, `FParse` and
  `FGenericPlatformMisc`, self-contained. Both `EngineDecls.h` and translation units built
  on the UHT shims, which have their own `FName`, can include it.
- `FString::operator*` in `ContainersRecovered.h`.
- `uht_classes.py` gives `UGameplayStatics` an `FNGC_EXTRA_MEMBERS_` hook (`EXTRA_MEMBERS`).
  A hand-written TU declares the class's recovered natives through it before including
  `UHTRecovered.h`. The same route serves the other 5,273 named native implementations.

### Thread-safe statics (2026-11-24)

Most of the other switch checks cache their result: `static bool b = FParse::Param(...)`. MSVC's
thread-safe initialization adds five fields to such a function:
- `_tls_index` (`.data`);
- the CRT's `_Init_thread_epoch`, read through the thread's TLS block. Its field is a `SECREL`
  offset into `.tls` (`mov edx, 0x18`);
- `_Init_thread_header` and `_Init_thread_footer`;
- the static itself and its guard `$TSS0`, a pair in `.bss`: the 1-byte static, then the
  4-byte guard, 8 bytes in all.

`compare.py` now handles `SECREL` fields as offsets into the reference's `.tls` section, for
both observation and resolution. The four CRT fields are shared by every such function, so
they resolve by corroboration once two of them are reconstructed.

The static and guard are referenced by their own function only. The only evidence for them
is layout: the slots of neighbouring statics, observed by other entries. Of the image's 2,307
thread-safe-static functions, 1,092 have another's static within 24 bytes. Three clusters
hold only command-line checks. Each lies in its source order, so each is reconstructed whole,
in that order, and its pairs place each other section-relatively:

| Cluster (reference `.bss`) | Functions | Result |
| --- | --- | --- |
| `0x046AEBD8..0x046AEBEF` (`Stats2.cpp`) | `FStats::EnabledForCommandlet`, `HasLoadTimeStatsForCommandletToken`, `HasLoadTimeFileForCommandletToken` | all exact. The first calls the other two, which resolve by their exact matches |
| `0x047C9418..0x047C9427` (`WindowsD3D12Device.cpp`'s unit) | `D3D12RHI_ShouldCreateWithD3DDebug`, `D3D12RHI_ShouldCreateWithWarp` | both exact |
| `0x047C91F0..0x047C91FF` (another D3D12RHI unit) | `D3D12RHI_ShouldCreateWithD3DDebug` (second copy), `D3D12RHI_ShouldForceCompatibility` | both exact |

The D3D12 checks are file-static functions of `D3D12RHIPrivate.h`. The recovered header
defines them, and each recovered unit keeps the ones the reference holds through its anchor
table. In both units our compiler emits the two pairs in definition order, as the reference
holds them. Two singles keep every byte but their
static and guard, whose neighbours belong to functions not reconstructed:
- `FGenericPlatformProcess::SupportsMultithreading`;
- `D3D11RHI_ShouldAllowAsyncResourceCreation`.

Both are relocation-equivalent.

### Attribute getters (`tools/codegen/attribute_getters.py`, 2026-11-24)

The largest family of thread-safe-static functions sitting next to each other in `.bss` is
GameplayAbilities' `GAMEPLAYATTRIBUTE_PROPERTY_GETTER`. Each attribute set class has an inline
static getter per attribute:

```cpp
static FGameplayAttribute Get<Property>Attribute()
{
    static UProperty* Prop = FindFieldChecked<UProperty>(<Class>::StaticClass(), FName(TEXT("<Property>")));
    return Prop;
}
```

84 instances share one 162-byte shape, in 12 classes:
- the class comes from the `GetPrivateStaticClass` they call, with `StaticClass()` inlined;
- the property comes from their `FName` literal.

Each instance's static (pointer, then guard: 16 bytes) is a COMDAT. The copy the reference
keeps comes from the first object that uses the getter, inlined or not. So a run of adjacent
statics is one object's first-use order, which nothing independent of those statics shows:
- the getters' code does not group them. The code comes from the first object that emits a
  getter out of line, and within an object it is sorted by name;
- declaration order matches some runs, such as `UFortDamageSet`'s 13. Others follow first
  use: `UFortHealthSet`'s `HealingSourceBaseMultiplier` sits between `Shield` and `Damage`.

The generator therefore emits each class's getters in one unit, in declaration order. That
order is read from the property offsets in the class's `FClassParams` property array (records
`{Type, NameUTF8, ObjectFlags, PropertyFlags, ArrayDim, RepNotifyFuncUTF8, Offset, ...}`), not
from the statics. The section-relative rule does the rest:
- a getter whose reference neighbours are its declaration neighbours resolves;
- elsewhere a side lands on another getter's observed slot and is dropped, or the prediction
  fails the byte comparison.

`uht_classes.py` gives each of these classes a member hook, through which the unit declares
the getters; they are defined out of line as `inline`, each with its RVA. The getters'
callees resolve by corroboration across the family:
- `FGameplayAttribute(UProperty*)`;
- `FindFieldChecked<UProperty>`;
- `FName::FName`;
- the CRT's thread-init functions.

`UFortRegenHealthSet`'s 6 are left out, because its `FClassParams` is not located.

Result: all 78 generated getters match outside their relocations. 51 are exact. The other 27
are relocation-equivalent, waiting on their own static (one also on a pooled literal), with
no regressions. Two classes are fully exact:
- `UFortAdvancedMovementSet` (7);
- `UFortCharacterAttrSet` (4).

`UFortDamageSet` has 12 of 14 exact; its `WeaponSkill` getter keeps its static in another
object.

## Fifth family: Core vector math (2026-11-24)

| RVA | Function | Result |
| --- | --- | --- |
| `0x01112E50` | `FGenericPlatformMath::Atan2` | exact |
| `0x011A6B30` | `FVector::ToOrientationRotator` | exact |
| `0x011A1EA0` | `FVector::Rotation` | exact |
| `0x011A8000` | `FRotator::Vector` | exact |
| `0x00AA95F0` | `FMath::VRand` | exact |
| `0x0208D930` | `UKismetMathLibrary::RandomUnitVector` | exact |
| `0x020812F0` | `UKismetMathLibrary::GetForwardVector` | exact |

The chain was found from `UKismetMathLibrary::execConv_VectorToRotator`. Its callee at
`0x011A1EA0` passes `this` and the return slot straight on, so it is a member function:
`FVector::Rotation`. The Kismet function itself is inlined into its thunk, and
`native-implementations.json` names the callee after it at low confidence.

`Atan2` is the 4.20 minimax polynomial. The source keeps its coefficients in a
`static const float c[7]` with negative entries. The compiler folds the array into pooled
scalar constants, so the reference subtracts positive ones, and the reconstruction compiled
from the same source does the same.

The pooled constants needed new evidence. A `__real@` float is 4 bytes, too short for the
unique-data search:
- the six coefficients are each the only aligned copy of their value in `.rdata`;
- `1.0`, `PI`, `PI/2` and `180/PI` have 339, 5, 5 and 5 copies. In each case exactly one copy
  is loaded by scalar float instructions elsewhere; the others are lanes of vector constants
  or table fields;
- some values have several scalar-loaded copies. The pooled copy is shared by every unit that
  uses the value, while a unit's own constant of the same value serves only that unit, so the
  pooled copy is loaded by far more functions. A copy counts when at least 10 functions load
  it, and at least 10 times as many as load the next copy. Measured on the reference:

  | Value | Copies | Scalar-loaded | Functions loading the top two |
  | --- | --- | --- | --- |
  | `-1.0` | 87 | 7 | 883, 26 |
  | `2.0` | 71 | 2 | 774, 1 |
  | `1e-8` | 7 | 3 | 1,061, 3 |

  Closer counts resolve nothing.

`Shims/FortniteGameCode/MathDecls.h` declares the few Core math members the chain uses.

The second batch follows the Kismet natives `execGetForwardVector` and
`execRandomUnitVector`:
- `UKismetMathLibrary::GetForwardVector` forwards to `FRotator::Vector`, which expands
  `FMath::SinCos` (the 4.20 minimax polynomials) for pitch and yaw;
- `UKismetMathLibrary::RandomUnitVector` forwards to `FMath::VRand`.

`FMath::VRand` is inline in `Math/Vector.h`, but the reference calls one out-of-line copy. Which
object emitted that copy is not established. `UnrealMath.cpp` emits it through an anchor table,
and the comparison checks only its bytes and relocations.

The two Kismet functions are declared in the generated class body through the
`FNGC_EXTRA_MEMBERS_UKismetMathLibrary` hook.

In the same run, two attribute getters became exact: `UFortBuildingTrapSet::GetDurabilityAttribute`
and `GetMaxDurabilityAttribute`. Their `Prop` statics and guards resolve section-relative
to each other (leave-one-out). The cause of the change is not established:
- the previous run's observations, replayed offline, resolve them by the same rule;
- no rule that applies to them changed.

Every getter object was recompiled in this run, because the shared generated header changed,
so the objects the previous runs compared may have differed.

## Sixth family: Kismet math natives (2026-11-24)

75 functions, all compiled from the 4.20 bodies:
- `KismetMathLibrary.cpp` (Engine): 50 natives, the static `EaseAlpha` and the twelve
  `ReportError_*` helpers;
- `UnrealMath.cpp` (Core): the interpolation and segment helpers the inlined Kismet functions
  call;
- `GenericPlatformMath.cpp` (Core): `FGenericPlatformMath::FmodReportError`.

72 are exact, 45 of them in the denominator. 27 are leaves without `.pdata`: `ResetRandomStream`,
the `FRandomStream` natives, the range and `InRange_*` helpers, nine of the `ReportError_*`
leaves and `FmodReportError`. The other three `ReportError_*` leaves are relocation-equivalent
(see below).

| Group | Functions | Result |
| --- | --- | --- |
| Core `FMath` (`0x0118B150`-`0x011A7F30`) | `ClosestPointOnSegment`, `PointDistToSegment`, `PointDistToLine`, `FInterpTo`, `FInterpConstantTo`, `VInterpTo`, `VInterpConstantTo`, `Vector2DInterpTo`, `Vector2DInterpConstantTo`, `CInterpTo` | 10 exact |
| Kismet, `.pdata` | `RandomBoolWithWeight`, `GenericPercent_FloatFloat`, `Log`, `FMod`, `MakePulsatingValue`, the six `Max/MinOf*Array`, `Ease`, `VEase`, `EaseAlpha`, `RandomRotator`, `FindClosestPointOnLine`, `ClampVectorSize`, `GetVectorArrayAverage`, `ClampAxis`, `NormalizeAxis`, `MakeTimespan(2)`, `BreakTimespan(2)`, `CreateVectorFromYawPitch`, `GetYawPitchFromVector`, `SeedRandomStream`, `IsPointInBox`, `GetRightVector`, `GetUpVector`, `GetAxes`, `BreakRotIntoAxes`, `MakePlaneFromPointAndNormal`, `LinePlaneIntersection(_OriginNormal)` | 35 exact |
| Kismet leaves | `Hypotenuse`, `InRange_FloatFloat`, `InRange_IntInt`, `MapRangeClamped`, `MapRangeUnclamped`, `NormalizeToRange`, `ResetRandomStream`, the nine stream natives (`MakeRandomStream` ... `RandomRotatorFromStream`) | 16 exact |
| `ReportError_*` (`0x0208EA80`-`0x0208EBE0`) | twelve 21-byte tail calls to `FFrame::KismetExecutionMessage` | 9 exact, 3 relocation-equivalent |
| `FGenericPlatformMath::FmodReportError` (`0x0126F320`) | `ret 0` | exact |

**Names.**
- `native-implementations.json` names a native's callee after the UFunction. For the Core
  callees of inlined Kismet functions, it records that name at low confidence; they are Core
  functions. One `UnrealMath.obj` run has its COMDATs in alphabetical order of their
  decorated names, which confirms the Core names: `?CInterpTo@FMath` `0x0118B150`,
  `?ClosestPointOnSegment` `0x0118BD30`, `?FInterpConstantTo` `0x01190A40`, `?FInterpTo`
  `0x01190AA0`, ... `?Vector2DInterpTo` `0x011A7F30`, `?Vector@FRotator` `0x011A8000`.
- The same order places `GenericPercent_FloatFloat` between `FromSeconds` and `GetAxes`. Its
  UFunction `Percent_FloatFloat` is custom-thunked.
- It also maps the twelve leaves at `0x0208EA80` + 0x20·k, which the natives list under
  `Divide_ByteByte` and the like, to `ReportError_DaysInMonth`, `ReportError_Divide_ByteByte`,
  ... `ReportError_Sqrt`. Their literals and warning ids agree.

**What the reconstruction needed.**
- `MathDecls.h` is now the one definition of the Core math types for both Core's code and the
  UHT world, which `ScriptRecovered.h` now takes from it. It adds the `FWindowsPlatformMath`
  SSE forms (`FloorToInt`, `TruncToInt`, `InvSqrt`) and the `FMath` interpolation templates.
  The UHT units were rebuilt with no changed result.
- `FMatrix` needs its user-declared default constructor. Without one, v140 treats a
  `FRotationMatrix` temporary as a `/GS` buffer and adds a cookie the reference lacks.
- `FRotationMatrix`'s constructor is inline in 4.20, but the reference calls an out-of-line copy
  at `0x009C4CB0`. It is only declared, and the call resolves by corroboration among the four
  reconstructed callers (two more, `FRotator::RotateVector`/`UnrotateVector`, are not yet
  reconstructed).
- `MapRangeClamped`/`Unclamped` use the pre-4.20 `GetRangePct` (`docs/ENGINE_DIFFERENCES.md`,
  #9).
- `EaseAlpha`'s jump table follows the code inside its `.pdata` range. Its `$LN` case labels
  and the `__ImageBase` base now resolve: the labels from the function's own start, as
  branches inside it do, and `__ImageBase` as RVA 0.
- `FmodReportError` is empty in shipping (`ensureMsgf` is compiled out): `ret 0`, which
  `/OPT:ICF` shares with other empty functions. Its address is where all four reconstructed
  callers (`GenericPercent_FloatFloat`, `ClampAxis`, `NormalizeAxis`, `FMod`) call. The calls
  resolve to the exact entry; each also has the other three callers as corroboration.

**Open at the time** (both since resolved or taken up in the seventh family):
- `ReportError_Sqrt`, `ReportError_ProjectVectorOnToVector` and `ReportError_DaysInMonth`
  each use one warning `FName` that no other entry uses. The reference keeps the four ids in
  declaration order (`DivideByZeroWarning` `0x04897810`, then +8, +0x10, +0x18). Our object
  orders them by v140's own per-name order: `InvalidDate`, `DivideByZero`, `ZeroLength`,
  `NegativeSqrt`. That order does not depend on use order, symbol count or `/Gw`, so
  section-relative prediction fails. The unit's dynamic initializers now resolve them (seventh
  family).
- Not attempted then: the vectorized `FRotator` helpers, `FQuat`/`FTransform` functions, the
  date and time natives, and `FRotator::RotateVector`/`UnrotateVector`.

## Seventh family: FQuat, FRotationMatrix and the Kismet unit's initializers (2026-11-24)

| Group | Functions | Result |
| --- | --- | --- |
| Core quaternion and matrix code | `FRotator::FRotator(const FQuat&)` `0x01188C70`, `FQuat::Rotator` `0x011A2050`, `FRotator::GetInverse` `0x01194C60`, `FQuat::Slerp_NotNormalized` `0x011A5A50`, `FMatrix::Rotator` `0x011A1EC0`, `FVector::RotateAngleAxis` `0x00579DF0` | 6 exact |
| `FRotationMatrix::MakeFrom*` (`0x0119B690`-`0x0119DCCD`) | `X`, `Y`, `Z`, `XY`, `XZ`, `YX`, `YZ`, `ZX`, `ZY` | 9 exact |
| Kismet natives | `ComposeRotators`, `TransformRotation`, `InverseTransformRotation`, `RLerp`, `REase`, `RotatorFromAxisAndAngle`, `MakeRotationFromAxes`, `RotateAngleAxis` | 8 exact |
| Kismet unit's dynamic initializers (`0x001D0730`-`0x001D0A69`) | 21 `GlobalVectorConstants`, the 4 Blueprint warning ids | 11 exact, 14 relocation-equivalent |

All 23 functions are in the denominator. The initializers are leaves outside it.

**Names.**
- The Kismet natives' Core callees are named, as in the sixth family, by their place in Core's
  alphabetical COMDAT order: `??0FRotator` sorts first, then `?GetInverse@FRotator`,
  `?MakeFromX@FRotationMatrix` ... `?MakeFromZY`, `?Rotator@FMatrix` before
  `?Rotator@FQuat`, and `?Slerp_NotNormalized@FQuat`.
- The nine `MakeFrom*` bodies are what the exec thunks of `MakeRotFrom*` call before
  `FMatrix::Rotator`.
- `FVector::RotateAngleAxis` is inline in `Vector.h`; the reference calls an out-of-line copy.
  `UnrealMath.cpp` emits it through an external member pointer, since a member function's
  address does not fit the anchor table.

**What the reconstruction needed.**
- `FQuat` has a user-provided copy constructor in 4.20 that copies member by member.
  `IMPLEMENT_ASSIGNMENT_OPERATOR_MANUALLY` gates only `operator=`. Without the constructor,
  `RLerp` copied the slerp result with one `movaps` where the reference copies four floats.
- The VectorRegister parts of `FQuat` and `FTransform` live in `QuatRecovered.h`:
  - `VectorQuaternionMultiply2`, which reads `QMULTI_SIGN_MASK0`-`2`;
  - `Normalize`, which reads `Float0001` and `FloatOneHalf`;
  - `FTransform::TransformRotation`.

  A unit includes `QuatRecovered.h` after defining its own constants, as each original unity
  file has its own copies.
- `KismetMathLibrary.cpp` defines the 21 constants its reference unit has, in header order.

**Constant slots.** Our object lays out the 21 constants and the 4 warning ids in v140's own
per-name order. The reference's order is not reproduced:
- it holds `FloatOne`, `XYZMask`, `SignMask`, `Float180`, ... from `0x04897730`, and the warning
  ids in declaration order at `0x04897810`;
- `/Gw` does not change v140's order (tested on the four warning ids).

The unit's own dynamic initializers resolve the slots instead, with no layout model.
- Each is a leaf at `0x001D0730`-`0x001D0A69` that stores the constant's value, or constructs the
  warning's `FName`, into its slot. The value or the literal names it.
- The unit's `??__E` functions sort alphabetically, at every position. That order also tells the
  two 1e-8 constants apart: `SmallLengthThreshold` (`0x04897890`), then `SmallNumber`
  (`0x04897780`).
- As manifest entries, each initializer observes its slot. A function using the constant is then
  corroborated without the initializer under test, and the reverse.

This resolved `RLerp`'s `Float0001` and `FloatOneHalf`, and the three `ReportError_*` leaves
left open in the sixth family. The 14 constants no reconstructed function uses yet leave their
initializers relocation-equivalent, with nothing to corroborate them.

**Open.**
- The remaining Kismet natives: 56 of the 149 targets, 42 with `.pdata`. They include:
  - the `FTransform` functions (`TLerp`, `TEase`, `TInterpTo`, `ComposeTransforms`,
    `InvertTransform`, `Transform_Determinant`, `IsPointInBoxWithTransform`);
  - `FRotator::Quaternion` (`UnrealMath`'s own constants);
  - the vectorized `FRotator` helpers;
  - the date and time natives;
  - `FRotator::RotateVector`/`UnrotateVector`.
- `UnrealMath.obj`'s constants (`0x046A0EB0`-`0x046A1040`) are the next set of initializers
  to recover. `FRotator::Quaternion` uses nine of them (eighth family).

## Eighth family: UnrealMath's constants and their users (2026-11-24)

`UnrealMath.cpp`'s reference unit has 24 `GlobalVectorConstants`, at
`0x046A0EB0`-`0x046A1040`. Their leaf initializers sit in two alphabetical runs, before and
after the unit's six log-category initializers (`??__ELog...`): `0x00129070`-`0x00129140` and
`0x00129270`-`0x00129371`. Each is named by the value it stores. Equal values are told apart
by position in the run:
- the 1.0 at `0x00129120` sorts between `FloatMinusOne` and `FloatOneHalf`, so it is
  `FloatOne`, not `RotationSignificantThreshold`, which also rounds to 1.0f;
- the 0.01 at `0x00129340` sorts between `SmallNumber` and `TwoPi`, so it is
  `ThreshQuatNormalized`, not `FloatOneHundredth`;
- the two 1e-8 constants follow the same rule as in the Kismet unit.

`UnrealMath.cpp` now defines the 24 in header order, and the 24 initializers are manifest
entries. With them, these became exact:

| RVA | Function | Constants it reads |
| --- | --- | --- |
| `0x011A0970` | `FRotator::Quaternion` | `VectorSinCos`: `DEG_TO_RAD_HALF`, `OneOverTwoPi`, `TwoPi`, `SignBit`, `Pi`, `SignMask`, `PiByTwo`, `FloatMinusOne`, `FloatOne` |
| `0x011A0B00` | `FMath::RInterpConstantTo` | the vectorized `FRotator::GetNormalized`: `Float360`, `Float180` |
| `0x011A0D30` | `FMath::RInterpTo` | the same, and `IsNearlyZero` (`SignMask`) |
| `0x011912C0` | `FQuat::FindBetweenNormals` | `FQuat::Normalize`: `Float0001`, `FloatOneHalf` |
| `0x01191460` | `FQuat::FindBetweenVectors` | the same |
| `0x011A5870` | `FQuat::SlerpFullPath_NotNormalized` | none (`acosf`, `sinf`) |
| `0x011A5EF0` | `FQuat::Squad` | the normalization |

13 of the 24 initializers are exact. The other 11 store constants that no reconstructed
function reads yet, so they are relocation-equivalent.

The names follow the alphabetical COMDAT order:
- `FindBetweenNormals`/`FindBetweenVectors` sit between `FInterpTo` and `FixedTurn`;
- `SlerpFullPath_NotNormalized` sorts before `Slerp_NotNormalized` (`F` < `_`);
- `Squad` sorts after `Slerp_NotNormalized`.

`FRotator::Normalize`, `GetNormalized` and `IsNearlyZero` take the 4.20 vector forms
(`VectorNormalizeRotator`), with `VectorSinCos`, in `QuatRecovered.h`.

Still open in this unit:
- `FQuat::ToSwingTwist` reads `FQuat::Identity`, which nothing else reconstructed uses;
- `FQuat::CalcTangents` calls `FQuat::Log`/`Exp`;
- the `FTransform` functions (`GetRelativeTransform` and others) need more of
  `TransformVectorized.h`.

## Ninth family: FTransform natives (2026-11-24)

| RVA | Function | Notes |
| --- | --- | --- |
| `0x02093D00` | `UKismetMathLibrary::TLerp` | 2,364 bytes. Both rotations are normalized (`VectorNormalizeQuaternion`), then one of three paths: `FTransform::Blend`, the Euler path (`RLerp` inlined), or the dual-quaternion path |
| `0x0206EDB0` | `FDualQuat::operator*(const FDualQuat&)` | The out-of-line product called by the two inlined `FDualQuat(const FTransform&)` in `TLerp`. Inline in `DualQuat.h`; the Kismet object emits it, sorted first among its COMDATs (`??D`) |
| `0x02093C20` | `UKismetMathLibrary::TEase` | `EaseAlpha`, then `TLerp` |
| `0x02093C90` | `UKismetMathLibrary::TInterpTo` | `TLerp` with the clamped alpha (`UKismetMathLibrary::FClamp`) |
| `0x02094D80` | `UKismetMathLibrary::Transform_Determinant` | The vectorized `ToMatrixWithScale`, then the out-of-line `FMatrix::Determinant` |
| `0x0064F030` | `FMatrix::Determinant` | Inline in `Matrix.inl`; the reference calls one out-of-line copy. `UnrealMath.cpp` emits it through a member pointer |
| `0x02085F20` | `UKismetMathLibrary::IsPointInBoxWithTransform` | `FTransform::InverseTransformPosition` (`VectorQuaternionInverseRotateVector`, `GetSafeScaleReciprocal`) |
| `0x0207FDA0` | `UKismetMathLibrary::GetAzimuthAndElevation` | The frame's unit axes (`TransformVectorNoScale`), then the Core function |
| `0x01194110` | `FMath::GetAzimuthAndElevation` | Sorts between `FixedTurn` and `FRotator::GetInverse` |

All 9 are exact and in the denominator. The quick check matched every one outside its
relocation fields on the first build, `TLerp` included. Six more Kismet constant initializers
are now exact, because these functions read their constants.

The transform code is the 4.20 `TransformVectorized.h` and `DualQuat.h` forms, added to
`QuatRecovered.h`:
- `ToMatrixInternal`/`ToMatrixWithScale`, `InverseTransformPosition`, `GetSafeScaleReciprocal`,
  `Blend`, `NormalizeRotation`, `GetUnitAxis`, the accessors and the `FTransform(FQuat, FVector,
  FVector)` constructor;
- the vector helpers they use: `VectorCross`, `VectorQuaternionRotateVector`,
  `VectorNormalizeSafe`, `VectorLerpQuat`, `VectorReciprocalAccurate`, `ScalarRegister` and
  the `VectorRegister` specialization of `FMath::Lerp`.

`TransformRecovered.h` only declares these members, because the unity units include it before
their constants and before `MathDecls.h`. `EAxis` moved to `AxisRecovered.h` so it can declare
`GetUnitAxis`.

`GetAzimuthAndElevation` needed new evidence. Its unit vectors are 16-byte `__xmm@` constants:
`(1,0,0,0)`, `(0,1,0,0)` and `(0,0,1,0)` have 16 to 25 aligned copies each, inside matrices and
tables. Packed SSE code loads exactly one copy of each: 105, 88 and 123 functions. The
pooled-constant rule now covers `__xmm@` names, with packed loads (`movaps`, `andps`, `mulps`,
`pxor`, ...) in place of scalar ones, and the same dominance threshold. A value with two loaded
copies, such as `(0,0,0,1)` at 296 against 32 functions, stays unresolved.

Not reconstructed: `ComposeTransforms`, `InvertTransform`, `GetDirectionUnitVector` and
`RandomPointInBoundingBox` (`0x02430650`-`0x024316AC`). They are out-of-line copies of
`KismetMathLibrary.inl` functions. They are emitted by the generated unity unit `Engine.18`,
whose exec thunks call them, and they read that unit's constants (`0x048B7290`-`0x048B7350`;
initializers in `analysis/functions-vector-constants.json`). The twelfth family matches them.

## Tenth family: dates and times, colours and rotator helpers (2026-11-24)

| Group | Functions | Result |
| --- | --- | --- |
| Core `FDateTime` (`Misc/DateTime.cpp`, `0x011AC210`-`0x011CC377`) | the constructor, `GetDate`, `GetDay`, `GetDayOfWeek`, `GetDayOfYear`, `GetHour12`, `GetMonth`, `GetYear`, `ToIso8601`, `ToString()`, `DaysInMonth`, `DaysInYear`, `IsLeapYear`, `Now`, `ParseIso8601`, `UtcNow`, `Validate` | 17 exact (8 leaves) |
| Core `FTimespan::Assign` (`0x011D5640`) and `FWindowsPlatformTime::SystemTime`/`UtcTime` (`0x01200190`, `0x01200490`) | | 3 exact (`Assign` a leaf) |
| Core colours (`Math/Color.cpp`, `0x01157720`-`0x01181CFF`) | `FLinearColor(const FColor&)`, `FLinearColor(const FVector&)`, `FColor::FromRGBE`, `FGetHSV`, `LinearRGBToHSV`, `HSVToLinearRGB`, `LerpUsingHSV`, both `MakeRandomColor`, `MakeFromColorTemperature`, `MakeRedToGreenColorFromScalar`, `Quantize`, `ToFColor` | 11 exact (4 leaves), 2 relocation-equivalent |
| Core `UnrealMath.cpp` | `FRotator::RotateVector`/`UnrotateVector`/`Euler`/`MakeFromEuler`, `FQuat::Euler`/`MakeFromEuler`, `FVector::ToOrientationQuat`/`FindBestAxisVectors`, `FMath::ClampAngle`, `FixedTurn`, `GetReflectionVector`, `PointsAreCoplanar`, `SegmentDistToSegment(Safe)` and the solver's `Solve`, `SegmentPlaneIntersection`, `ClosestPointOnLine`, `ClosestPointOnSegment2D`, `PointDistToSegmentSquared`, `RandPointInBox`, `RandPointInCircle` | 21 exact (3 leaves) |
| Kismet natives | `BreakDateTime`, `MakeDateTime`, `ClassIsChildOf`, `FInterpEaseInOut`, `FloatSpringInterp`, `VectorSpringInterp`, `ResetFloatSpringState`, `ResetVectorSpringState`, `GetReflectionVector`, `NormalizedDeltaRotator`, `RandomUnitVectorFromStream` | 10 exact (3 leaves), `MakeDateTime` relocation-equivalent |
| The Kismet object's out-of-line copies | `GenericSpringInterp<float>` (`0x0206B500`), `GenericSpringInterp<FVector>` (`0x0206B5B0`), `FRandomStream::GetUnitVector` (`0x01C85C00`) | 3 exact |

68 functions: 65 exact (46 in the denominator, 19 leaves outside it) and 3 relocation-equivalent,
each with one field no other entry corroborates:
- `FColor::FromRGBE` reads `FLinearColor::Black`, which `Color.cpp` only declares;
- `FLinearColor::MakeFromColorTemperature`'s 15000.0f clamp (`__real@466a6000`) has several
  copies that scalar code loads, none dominant;
- `UKismetMathLibrary::MakeDateTime` is the only entry calling `FString::PrintfImpl`.

Four earlier entries became exact with them: `UGameplayStatics::HasLaunchOption` (its `TEXT("")`
literal, now corroborated by `MakeDateTime`'s `*FString`), the `UObject::StaticClass` thunk
(`ClassIsChildOf` calls `UObject::GetPrivateStaticClass`), and the Kismet unit's `Float180` and
`Float360` initializers, which `NormalizedDeltaRotator` reads.

**Locating.** Most of the Core functions are not reachable from the Kismet natives, so their
addresses come from a new tool, `tools/matching/locate.py`. It compiles nothing itself: given an
object, it masks every relocation field of each function and lists the 16-byte-aligned addresses
of the reference where all other bytes agree. Two kinds of result need more evidence:
- several hits, when bodies differ only in relocated operands. `ToIso8601` and `ToString()` are
  the same 30 bytes with different literals; `Now` and `UtcNow`, and `SystemTime` and `UtcTime`,
  differ only in their callee or import. Core's alphabetical COMDAT order decides (`ToIso8601`
  `0x011C8860` before `ToString` `0x011C9270`, `Now` `0x011BFB90` before `UtcNow`
  `0x011CC290`), and so do the literals and imports compare.py resolves;
- no hit. 18 of the 4.20 functions tried have no copy in the reference and are left out:
  `FromSRGBColor` (its body is the `FLinearColor(const FColor&)` constructor's), `FromPow22Color`,
  `ToRGBE`, `QuantizeRound`, `Desaturate`, `FLinearColor(const FVector4&)`,
  `FColor::MakeFromColorTemperature`, `ComputeAndFixedColorAndIntensity`,
  `ClosestPointOnInfiniteLine`, `CreateOrthonormalBasis`, `GetWindingAndRemainder`,
  `GetBaryCentric2D`, `ComputeBaryCentric2D`, `SphereDistToLine`, `WindRelativeAnglesDegrees`,
  `ApplyScaleToFloat`, `CartesianToPolar` and `PolarToCartesian`. They are unused (`/OPT:REF`) or
  differ; `ComputeBaryCentric2D` may be the function at `0x0118D320`, whose expression order is
  different. `GetTForSegmentPlaneIntersect` stays in the source without an address: it is inlined
  into `SegmentPlaneIntersection`.

**What the reconstruction needed.**
- New shim types in `MathDecls.h`: `FDateTime` and `EDayOfWeek`, `FWindowsPlatformTime`,
  `FVector4`, and `FColor`, moved there from `EngineStructsRecovered.h` with its constructors.
  `FLinearColor` gained the `Color.cpp` members, `FTimespan` its tick constructor and
  `FromMinutes`, `FRandomStream` `GetUnitVector`/`VRand`, and `FMatrix` `TransformFVector4`,
  `TransformVector` and `GetTransposed`.
- These declarations are behind `FNGC_CORE_MATH_EXTRAS`, which only the Core units and
  `KismetMathLibrary.cpp` define. With them visible to the generated UHT units, MSVC v140 emitted
  `InputCore.1`'s functions in another order: its `FKey` literals moved from offset 1672-1688 to
  the start of `.rdata`, and the `FKey` defer-struct initializer (`0x001398C0`) lost the
  section-relative evidence for its `"Key"` field (exact to relocation-equivalent). Compiling
  `InputCore.1` against each changed shim showed the `MathDecls.h` additions as the cause; with
  the guard the unit compiles as before. `EngineStructsRecovered.h` keeps the plain `FColor` for
  those units.
- `Color.cpp` defines `Pow22OneOver255Table` and `sRGBToLinearTable` with the reference's own
  values, read from its `.data` (`0x04369F00` and `0x0436A300`, 1024 bytes each, equal to the
  4.20 tables) and printed with 9 significant digits, which round-trips every float. The
  constructor's table field then resolves by its unique content.
- `FVector4`'s default constructor zero-fills, as 4.20's `FVector4(float InX = 0.0f, ...)` does.
  With an empty one, `UnrotateVector` misses the reference's three zero stores of
  `TransformFVector4`'s result.
- `FRotator::RotateVector` and `FTimespan::FromMinutes` need forms other than the public 4.20.0
  ones (`docs/ENGINE_DIFFERENCES.md`, #10 and #11).
- `FDateTime`'s constructor has no `Validate` call: the `UE_LOG(LogCore, Fatal, ...)` it guards is
  compiled out of the shipping client.
- `FCString::Strtoi` is `wcstoul` (`_tcstoul`), called through the import table, and the
  platform-time functions call `GetLocalTime`/`GetSystemTime` the same way. Both are declared, not
  taken from `Windows.h`.
- `TSubclassOf::operator*` and `UStruct::IsChildOf` for `ClassIsChildOf`: the walk reads
  `SuperStruct` at 0x30, because the generated class bodies are opaque (`TextRecovered.h`).
- `FString::Printf` forwards to the out-of-line `PrintfImpl` (`MakeDateTime`'s warning).
- `SegmentDistToSegment_Solver::Solve` is defined in its struct; v140 emits one out-of-line copy for
  both callers, as the reference has.
- `ResetFloatSpringState` is `PrevError = Velocity = 0.f`, one 8-byte store. The exec thunk calls
  the 6-byte body at `0x00E71030`, which `/OPT:ICF` shares with every identical function; the entry
  is a leaf outside the denominator.

Not reconstructed: `MinimumAreaRectangle` (its `TArray` growth and `ConvexHull2D` template
callees), the five `From*` timespan natives (`FText::Format` with `FFormatNamedArguments`),
`FDateTime::Parse` and `FTimespan::Parse` (string splitting), and `FTransform::GetRelativeTransform`
(`0x01195910`: a thread-safe static and the Core unity unit's vector constants).

## Eleventh family: transforms and the minimum-area rectangle (2026-11-24)

| Group | Functions | Result |
| --- | --- | --- |
| Core `TransformVectorized.cpp` (compiled through `UnrealMath.cpp`) | `FTransform::GetRelativeTransform` (`0x01195910`, the target of `ConvertTransformToRelative`), `GetRelativeTransformReverse`, `SetToRelativeTransform`, `GetRelativeTransformUsingMatrixWithScale`, the `FTransform::Identity` initializer (`0x00128F90`) | 5 exact (the initializer outside the denominator) |
| Out-of-line copies `UnrealMath.cpp` emits | `FMatrix::Inverse` (`0x00696430`), `FMatrix::RemoveScaling` (`0x00575220`), `FQuat(const FMatrix&)` (`0x00569390`) | 2 exact; the quaternion constructor relocation-equivalent (its `nxt[3]` table has no second user) |
| Core `UnrealMath.cpp` | `FMatrix::ToQuat`, `FQuat::ToSwingTwist`, `FQuat::CalcTangents`, `ClampFloatTangent` | 4 exact |
| Kismet | `MinimumAreaRectangle` (`0x0208AB40`) | not exact: 8 padding bytes (below) |
| Out-of-line copies the Kismet object emits | `FMatrix::InverseFast` (`0x00674050`), `TArray<FVector>::ResizeGrow` (`0x02508DB0`), `TArray<int32>::ResizeGrow` (`0x018F3E90`) and `ResizeTo` (`0x01F99E30`), `ConvexHull2D::ComputeConvexHull<FDefaultAllocator>` (`0x008C9CF0`) | 4 exact; `ComputeConvexHull` partial |

18 functions: 15 exact (14 in the denominator), 1 relocation-equivalent and 2 partial. With them
eight more of `UnrealMath.cpp`'s constant initializers are exact (`FloatZero`, `QINV_SIGN_MASK`,
the three `QMULTI_SIGN_MASK`s, `SmallNumber`, `ThreshQuatNormalized`, `XYZMask`): these functions read
their constants. `GetRelativeTransform` needed its callee exact first, and that callee needed the
out-of-line `RemoveScaling`, located by its body (`0x00575220`).

**One Core unity unit.** `GetRelativeTransform` reads the constants `UnrealMath.cpp` defines
(`FloatOne` `0x046A0EB0`, `XYZMask` `0x046A0EC0`, `ThreshQuatNormalized`, ...), and
`FTransform::Identity` (`0x046A0E80`) sits in the same `.bss` block. The reference builds both
files in one Core unity unit, so `UnrealMath.cpp` includes `TransformVectorized.cpp` at its end;
the project lists it as a unity member, as `Module.D3D11RHI.cpp`'s members are. The `Identity`
initializer's decorated name (`??__E?Identity@FTransform`) sorts before the unit's
`??__EDEG_TO_RAD` (`0x00129070`), where it is. `FMatrix::Identity` and `FQuat::Identity` have no
initializer, in the reference or here: they are constant data.

**What the reconstruction needed** (all behind `FNGC_CORE_MATH_EXTRAS`, see the tenth family):
- the 4.20 matrix routines: `VectorMatrixMultiply`, the scalar `VectorMatrixInverse`,
  `FMatrix::operator*`, `Inverse`, `InverseFast`, `RemoveScaling`, `SetAxis`, `GetOrigin`, and
  `FQuat(const FMatrix&)`. `Inverse`, `InverseFast` and the quaternion constructor are `inline`,
  not `FORCEINLINE`: v140 keeps them out of line, as the reference does;
- `FTransform::IsRotationNormalized`, `Private_AnyHasNegativeScale` and
  `ConstructTransformFromMatrixWithDesiredScale`, defined in `TransformVectorized.cpp`, where
  the unit's `ThreshQuatNormalized` exists;
- `TArray::Add`/`Emplace`/`AddUninitialized`, `ResizeGrow` with `DefaultCalculateSlackGrow`, and
  `Forward` (`ContainersRecovered.h`). The growth copies are generic: `/OPT:ICF` gives every
  TArray of the same element size one body, here named by the caller's instantiation;
- `GetRelativeTransform` and `GetRelativeTransformUsingMatrixWithScale` each keep a thread-safe
  `static ScalarRegister STolerance` (`_Init_thread_header`/`_footer` and the TLS epoch).

**Not matched.**
- `MinimumAreaRectangle` is byte-identical except for 8 of the 10 bytes at `+0x3D6`. That span
  is alignment padding between an unconditional `jmp` and a loop head, and no branch reaches it.
  v140 fills it with one 10-byte NOP. The reference has `90 35 48 8B 83 10 01 00 00 48`, which is
  not a NOP and occurs nowhere else in `.text`. The on-disk bytes are the same as the decrypted
  ones there, although the protector encrypts function bodies on disk. So the protector, not
  the compiler, most likely wrote them. Under the matching rules the function stays
  partial; the bytes are not masked.
- `ComputeConvexHull`'s copy (818 bytes) comes out at 847: v140 keeps the hull point `C.X` in a
  callee-saved register (one more `xmm` saved) and builds the second determinant product in the
  other operand order. Swapping the product in the source changes nothing; the cause is upstream.
- 9 of the 4.20 functions tried have no copy in the reference: the three `FVector4` orientation
  helpers fold into the `FVector` ones already matched (`0x011A6B30`, `0x011A6820`), `SquadFullPath`
  has the same masked body as `Squad` (`0x011A5EF0`), and `PlaneAABBIntersection`,
  `SphereConeIntersection`, `QInterpTo` and `QInterpConstantTo` are absent. `FQuat::Log` and
  `Exp` stay in the source without an address: `CalcTangents` inlines them.
- The four `.inl` copies in the generated Engine.18 unit (`ComposeTransforms`, `InvertTransform`,
  `GetDirectionUnitVector`, `RandomPointInBoundingBox`) read about a dozen of that unit's vector
  constant slots (`0x048B7290`-`0x048B7350`). `tools/codegen/unity.py` defines only the constants
  whose initializers open the unit's `.CRT$XCU` entries (`FloatOne`); modelling the others would
  change a generated unit with exact entries, so they wait. The twelfth family matches them.

## Twelfth family: the Engine.18 transform copies (2026-11-25)

| Group | Functions | Result |
| --- | --- | --- |
| `KismetMathLibrary.inl` copies in the generated unit `Engine.18` | `ComposeTransforms` (`0x02430650`), `GetDirectionUnitVector` (`0x02430CE0`), `InvertTransform` (`0x024313F0`), `RandomPointInBoundingBox` (`0x024315F0`) | 4 exact |
| `Engine.18`'s `GlobalVectorConstants` initializers (`0x00204630`-`0x00204841`, `.CRT$XCU` entries 20497-20510) | 13 new, and `FloatOne`'s (relocation-equivalent before) | 12 exact, outside the denominator; `Float360` and `Float180` relocation-equivalent |

All four copies matched on the first build. With them 12 of the unit's 14 constants have a
reader, so their initializers are exact too.

**The constants the analysis missed.** `tools/analysis/unity_order.py` reads a unit's header
constants from the leaf initializers after its `FloatOne` marker. It stopped at the first
initializer of another form. `FloatZero`'s loads nothing:
`xorps xmm0, xmm0; movaps [slot], xmm0; ret`. Three units therefore recorded only `FloatOne`:
- `Engine.18`, with 14 constants;
- `UMG.1`, with 17;
- `SocialTypes.1`, with 13.

The analysis now reads the zero form too. The table holds 59 initializers of that form; the
other 56 are outside the UHT units' constant runs.

**Placement.** In 4.20 the four are `KISMET_MATH_INLINE`, plain `inline`. v140 keeps
out-of-line copies where `Engine.18`'s exec thunks call them. Those thunks are not
reconstructed, so `Classes/Kismet/KismetMathLibrary.inl` defines the four without `inline`,
which gives the same code. `tools/codegen/unity.py` compiles it at the end of `Engine.18`
(`UNIT_SOURCES`), after the unit's constants and fragments. `KismetMathLibraryUnity.h` opens
the unit with `FNGC_CORE_MATH_EXTRAS` and the class-body declarations.

**Headers.**
- `TransformMathRecovered.h` holds 4.20's `FTransform::Multiply`,
  `MultiplyUsingMatrixWithScale`, `operator*`, `Inverse`, `InverseFast` and the
  `VectorRegister` constructor.
- `Private_AnyHasNegativeScale` and `ConstructTransformFromMatrixWithDesiredScale` moved
  there from `TransformVectorized.cpp`. `UnrealMath.obj` is byte-identical afterwards.
- `Engine.18` has no `SmallLengthThreshold` and none of `VectorSinCos`'s constants. A unit
  that defines `FNGC_QUAT_WITHOUT_SINCOS` therefore gets only declarations of those two
  functions from `QuatRecovered.h`.

**The three units.** Their existing functions compile to the same code, with string-literal
names normalised. MSVC's order of the unnamed string literals in `.rdata` changed, as it did
for `InputCore.1` in the tenth family, but no match changed. The 28 new initializers of `UMG.1`
and `SocialTypes.1` are relocation-equivalent: nothing reconstructed reads those constants yet.

## Thirteenth family: the timespan From* natives (2026-11-25)

| Group | Functions | Result |
| --- | --- | --- |
| Kismet natives | `FromDays` (`0x0207D8E0`), `FromHours` (`0x0207DBF0`), `FromMilliseconds` (`0x0207DF00`), `FromMinutes` (`0x0207E200`), `FromSeconds` (`0x0207E500`) | 5 relocation-equivalent: their argument-name literals (below) |
| Out-of-line copy the Kismet object emits | `TArray<TCHAR>::ResizeGrow` (`0x005757C0`) | exact |
| Core `GenericPlatform/GenericPlatformString.cpp` | `FGenericPlatformString::Memcpy` (`0x0111CAE0`) | exact |

**What the natives compile to.** In 4.20 each one clamps to `FTimespan::MinValue()` or
`MaxValue()` and reports the clamp: `Args.Add(TEXT("DaysValue"), Days)`, then
`LogRuntimeError(FText::Format(LOCTEXT(...), Args))`. In shipping `UE_RAISE_RUNTIME_ERRORS` is 0, so
`LogRuntimeError(Message)` expands to nothing and neither `FText::Format` nor `LOCTEXT` is
compiled. What remains is the `FFormatNamedArguments` map built and destroyed around one `Add`.
The reference matches that:
- `FString`'s literal constructor, inlined: `TArray<TCHAR>::ResizeGrow` and
  `FGenericPlatformString::Memcpy`, the out-of-line forwarder `FPlatformString::Convert` calls;
- the `FFormatArgumentValue(float)` temporary (type 2, an unset `TOptional<FText>`);
- `TSet::Emplace` (`0x0027C9A0`) and the map's destruction, inlined except
  `TSparseArray::Empty` (`0x00295B40`).

`SetRecovered.h` models the 4.20 layouts of `TBitArray`, `TSparseArray`, `TSet` and `TMap`, with
their construction and destruction. `Emplace` and `Empty` are only declared: `Emplace` calls six
more out-of-line set helpers. Their addresses are corroborated across the five natives.
`EngineStructsRecovered.h` swaps its empty `TSet` stand-in for this header only in a unit that
defines `FNGC_SET_RECOVERED` (`KismetMathLibrary.cpp`). The other units' objects are unchanged
apart from string-literal names and positions; no match changed.

**The normal path is an older form.** The reference truncates `Days * TicksPerDay` with no
`+ 0.5` and no rounding, as `FromMinutes` does (`docs/ENGINE_DIFFERENCES.md` #11 and #12).
Minutes, seconds and milliseconds multiply in single precision (`mulss`, `cvttss2si`): their tick
counts are exact as floats, and v140's `/fp:fast` then keeps `(double)float * constant` in float.
The four new `FTimespan` helpers, with `MinValue`, `MaxValue` and `GetTotal*`, are in `MathDecls.h`.

**Why the natives are not exact.** Each one names its argument twice, once per branch, and the
reference holds two per-occurrence copies of that literal (for example `DaysValue` at
`0x037CAD50` and `0x037CADF0`). Only the native itself references either copy. Literal elimination
leaves the entry under test out of its own evidence, so both copies stay free for each relocation.
Nothing else says which copy belongs to which branch. All other bytes and relocations match.

## Fourteenth family: the date and time parsers and their FString members (2026-11-25)

| Group | Functions | Result |
| --- | --- | --- |
| Core `Misc/DateTime.cpp`, `Misc/Timespan.cpp` | `FDateTime::Parse` (`0x011C0050`), `FTimespan::Parse` (`0x011DEC10`) | 2 relocation-equivalent: their one-character literals (below) |
| Core `Containers/String.cpp` (new) | `FString::Find` (`0x01103630`), `IsNumeric` (`0x01104260`, a leaf), `ParseIntoArray` (`0x01105410`), `Replace` (`0x01108D80`), `ReplaceInline` (`0x011092B0`), `StartsWith` (`0x0110A820`), `ToUpper() const &` (`0x0110D720`), `ToUpper() &&` (`0x0110D7D0`), `ToUpperInline` (`0x0110D860`) | 9 exact |
| Out-of-line copies `String.cpp`'s object emits | `TCString<TCHAR>::Stristr` (`0x00276040`), `TCString<TCHAR>::IsNumeric` (`0x007B94B0`), `TArray<FString>::ResizeGrow` (`0x025605C0`) and `ResizeTo` (`0x0139F3B0`), `TArray<TCHAR>::ResizeTo` (`0x019D1E90`) | 5 exact |

16 functions: 14 exact (13 in the denominator) and 2 relocation-equivalent. These are the
Kismet natives `DateTimeFromString` and `TimespanFromString`: `KismetMathLibrary.inl` inlines
their wrappers, so the exec thunks call Core's parsers directly.

**Both parsers follow the 4.20 source.** Every byte matches with the relocations masked.
- `FDateTime::Parse`: `Replace`, two `ReplaceInline`s, `ParseIntoArray`, seven `Atoi`s through
  `_wtoi`'s import slot. `Validate` is inlined (it calls `DaysInMonth`), then the constructor.
- `FTimespan::Parse` needed 4.20's header forms of `TArray::AddDefaulted`, `InsertDefaulted`
  (`memmove`, then `memset`: `FString` is a zero-construct type), the pointer iterators of
  ranged for in shipping, and `FString::Left`, `operator+=` and `AppendChars`.
- One byte depended on `FString::CheckInvariants`: in shipping its `checkSlow`s are empty, but
  its unused `int32 Num = Data.Num()` stays. Without it, the null-terminator store after
  `AppendChars`' `memcpy` encoded as `[rdi+rbx]`, not the reference's `[rbx+rdi]`. The reference
  uses both orders elsewhere (321 and 252 times after a `memcpy` call), so the context decides.

**The FString members are 4.20's, with one older condition.** `ParseIntoArray` splits
`if (Start && DelimLength)`: the reference does not test the first character as 4.20.0 does
(`docs/ENGINE_DIFFERENCES.md` #13). `ToUpper() &&` and `ToUpperInline` were located by their
masked bodies. Each has a `ToLower` twin with the same masked body; the `towupper` import slot
and the decorated-name order pick these. `TCString::IsNumeric` is defined in its class in 4.20,
but the reference keeps it out of line: `FString::IsNumeric` tail-jumps to it. v140 does the
same here.

**Shims.** `ContainersRecovered.h` has the members behind `FNGC_STRING_EXTRAS`. Only the units
that parse define it (`DateTime.cpp`, `Timespan.cpp`, `String.cpp`, after `MathDecls.h`), so other
objects are unchanged apart from string-literal names. `Misc/RecoveredCString.h` gains `Atoi`,
`Strcmp`, `Strncmp`, `Strstr`, `Stristr`, `IsNumeric` and `TChar::ToUpper`/`IsDigit`.

**Why the parsers are not exact.** Their literals are one-character strings: `L"-"`, `L" "`,
`L":"`, `L"."`, `L","`, `L"+"`. The image holds dozens of copies of each (72 of `L"-"`, 320 of
`L" "`), and several stay free after literal elimination. `FDateTime::Parse` alone uses four
copies of `L" "`, and `FTimespan::Parse` five of `L":"`. Leaving the entry under test out of
its own evidence, nothing assigns them.

## Bulk engine reconstruction (`tools/engine/`, 2026-11-25)

Engine code is no longer recovered one function at a time. The supplied UE4.20.0 tree is
compiled module by module with the reference's toolchain, and every compiled function is
located in the reference and verified by `compare.py`. Hand-written reconstructions and the UHT
generators keep their entries; the bulk pass fills the addresses they do not hold.

**Compile environments come from UnrealBuildTool itself.** UBT is built from the engine tree and
run for UE4Game Win64 Shipping with `-JsonExport -SkipBuild`, pinned to VS2015 v140 and Windows
SDK 10.0.10586.0. It builds and runs UnrealHeaderTool (real `.generated.h` files for the
target's UObject modules) and writes every module's unity files and the exact compiler response
file of each. `tools/engine/build.py` runs those 285 actions for 92 modules unchanged except for
the object path, no precompiled header (its wrapper header is still force-included) and no debug
information. All 285 compile, in about 15 minutes.

**One project setting differs from UE4Game.** Fortnite's shipping client logs:
`USE_LOGGING_IN_SHIPPING=1` places 3,884 of Core's functions uniquely instead of 3,803, while
`USE_CHECKS_IN_SHIPPING=1` drops it to 2,819. The definition is applied to copies of the
wrapper headers (`ue_target.PROJECT_DEFINITIONS`).

**Mapping** (`tools/engine/map.py`, `locate.PdataIndex`). The reference's 157,719 primary
`.pdata` functions are indexed by length (a primary entry plus its contiguous chained entries).
A compiled function is compared with the functions of its length, relocation fields masked:
- one equal function: proposed there;
- several (identical bodies that differ only in their targets, such as `FString::ToUpper` and
  `ToLower`): each candidate's relocation fields are read in the reference, and only a candidate
  that agrees with every independently known target (an import slot, a literal or data block
  unique by content, a function another manifest already matches) stays. Exactly one: proposed;
- none: not proposed.
An address another manifest already holds is left to it, and one address gets one name.

**Verification.** A proposal is only a location. `compare.py` resolves every relocation as for
any other entry. One rule is new: bulk entries contribute observations only once exact, and
never as ICF-folded bodies. Without it a misplaced relocation-equivalent entry put shared
symbols at a second address: the first full run cost 1,886 existing exact matches (bodies such
as `GetPrivateStaticClass` lost their ICF-folded `StaticRegisterNatives` call) and never reached
a fixpoint. With it, no existing match changed.

**Results.** 92 modules, 285 compile actions, 24,461 proposed functions:
14,855 exact (14,855 in the denominator),
9,333 relocation-equivalent, 273 partial (a field
resolved by evidence to an address the reference does not hold). No existing match changed.

| Module | Exact | Relocation-equivalent | Partial |
| --- | --- | --- | --- |
| Engine | 4,936 | 3,350 | 66 |
| Renderer | 2,141 | 1,091 | 6 |
| Core | 1,416 | 765 | 41 |
| CoreUObject | 791 | 475 | 60 |
| AIModule | 681 | 344 | 25 |
| BuildPatchServices | 477 | 264 | 20 |
| Slate | 278 | 234 | 2 |
| Navmesh | 256 | 30 | 0 |
| UMG | 251 | 163 | 2 |
| AnimGraphRuntime | 251 | 112 | 3 |
| SlateCore | 234 | 161 | 3 |
| MovieScene | 197 | 165 | 4 |

**Systematic causes of the unplaced functions** (`tools/engine/nearmiss.py`, Core: 388 of 2,593
unplaced functions of 24 bytes or more have a same-length reference function at 85% or more):
- **Line numbers.** `__LINE__` immediates differ by a few lines (`FMallocBinned2::MallocExternal`
  passes 775, the reference 769): Fortnite's files have extra or fewer lines. Shipping logging
  passes `__LINE__` even where the file name is suppressed. Recovered and applied:
  "Engine line numbers" below.
- **Class layouts.** `FText` functions allocate `0x160` bytes where the reference allocates
  `0x210`; an `IFileManager` virtual is at `0xE0` instead of `0xD8`; a `TSetElement` of
  `FDisplayStringEntry` is 72 bytes instead of 40. The internal fork's classes differ.
- **Different literals.** Path lengths differ (`FPaths::ScreenShotDir`).
- **Build root.** The reference's `__FILE__` strings start `D:\Build\++FN25\Sync\` (1,061 engine
  paths; 32 more from `D:\Build\++FNS\Sync\`), with absolute include directories
  (`...\Runtime\Slate\Public\Widgets/Views/STreeView.h`). Literals compiled from `E:\FortniteGame`
  can never resolve by content; only three are in Core.
- **Unity composition.** Inlining across the `.cpp` files of one unity unit depends on which
  files share it (`FPaths::ProjectUserDir` is 1,045 bytes in the reference, 333 here). UBT groups
  the public tree's files; Fortnite's tree had other files and sizes.

## Engine line numbers (`tools/engine/lines.py`, `overlay.py`, 2026-11-26)

Shipping logging and fatal errors pass `__LINE__` (`UE_LOG` passes `"Unknown"` for the file, but
the real line), so a function of a file in which Fortnite added or removed lines differs from the
reference in those immediates alone.

**Measuring.** Every compile action is compiled a second time with each of its engine `.cpp` files
renumbered through an overlay copy: file *i* of the unit starts at line (*i* + 1) · 50,000 + 1
(`#line` accepts at most 16,777,215). A 4-byte field below 50,000 in the regular object and
(*i* + 1) · 50,000 + *L* in the renumbered one is a `__LINE__` of file *i*, line *L*; any other
difference is reported. A macro invocation spanning lines gets the number of its last line. The
renumbered build gives each file the reference's `__FILE__`
(`D:\Build\++FN25\Sync\Engine\Source\...\X.cpp`), so its literals resolve by content. Of all
engine functions, 802 have line fields and 74 change size instead (a line below 128 becomes a
`lea reg, [reg + disp8]`).

**Locating.** A function with line fields is located with them masked as well as its relocation
fields: at its manifest address if it is exact there (an anchor, weight 1000), else at the
same-length `.pdata` functions with equal masked bytes that its relocation targets confirm: every
independently known target agrees, at least one does, and every string literal's text is what the
reference holds where the function points. The last test matters: `FGenericPlatformProcess`'s
"not implemented on this platform" stubs differ only in their message and line, and without it
they matched other stubs (`ClosePipe` matched `UField::AddCppProperty`'s, which gave its line 535
the number 196).
109 functions are located (4 anchors) and 680 are not; their other bytes differ too. In Slate
(118) and UMG (59) that is every one: `SNew` construction code whose most similar same-length
reference function is 13 to 45 % alike (the widgets' `FArguments` differ).

**Numbering** (`overlay.py`). Per line the value with two thirds of the weight, else none: 132
lines of 58 files, 42 of them renumbered (`analysis/engine-lines.json`). `MallocBinned2.cpp`
keeps its numbers up to line 479 (anchored by exact functions) and has six fewer from line 775
on. Where the offset changes between two known lines, a `#line` directive goes at the latest
line of the least brace depth between them (between functions where it can: nothing says where
in that stretch the lines changed) that is safe: not in a comment, string, continued line or
macro arguments (no parenthesis open), and in the preprocessor branch of the line it renumbers or
one enclosing it. Only renumbered files are compiled through an overlay, under their own file
name; quote includes that resolve beside the original are made absolute, and the original
directory is passed with `/I`.

**Not the build root as well.** Compiling every file under the reference's `__FILE__` made 7 more
functions exact, but its longer literals changed other objects' data layout and every lambda's
name (MSVC derives them from the file). That tipped compare.py's section-relative inference and
map.py's choice between folded bodies for 11 exact functions, so the build-root fix stays a
separate step.

**Name choice at folded addresses** (`map.py`, `choose_names`). When several symbols are proposed
at one address, the one already exact there stays; otherwise the one whose relocations the
evidence supports best: independently known targets, string literal text at the target, the
targets the module's uniquely placed functions see, and callers whose relocation lands there.
The choices are revised until they agree (a lambda's outer and inner function stay one lambda's),
then the first by name decides. Name order alone had given `UParticleModuleColorOverLife::
InitializeDefaults` the address of `ColorScaleOverLife`'s, whose string only the latter matches.

**Vtables by known slots** (`compare.py`, `_known_pointers`). Where a data symbol's layout
neighbours resolve nothing, a vtable whose first slot (and any others) are exact functions is
placed at the one 8-aligned place in `.rdata` holding all those pointers at their offsets. The
first slot must be among them: Fortnite's `UObject` has one virtual fewer (ENGINE_DIFFERENCES
#14), and without RTTI vtables lie back to back, so the later slots of a `UObject` class match
one slot off. 15 entries resolve a field this way. One is `TPromiseBase<TTuple<TSet<FString>,
TSet<FString>>>`'s constructor: new matches observe the vtable's left neighbours, and its layout
inference now ties two neighbours to two.

**Results.** 52,409 exact (52,095 before), no regression against the previous commit. 25 of the
314 are functions of renumbered files and 4 resolve through known pointers; the other 285 are
placements map.py makes now that the engine's 14,855 exact functions are known targets (16,497
ambiguous functions decided by relocations instead of 14,602), and the name choice. Engine
manifests: 24,814 entries, 15,169 exact, 9,413 relocation-equivalent, 232 partial.

## Engine class layouts (`tools/engine/layout.py`, 2026-11-27)

Fortnite's engine is an internal snapshot from before UE4.20's release, and some of its classes
declare other virtual functions than public 4.20.0. A virtual call compiles to a vtable
displacement, so every function that calls a moved virtual differs in that displacement. This
pass measures where the reference's vtables differ and models the differences in the build.

**Measuring.** A vtable of ours is placed in the reference where the most of its exact slots'
pointers sit, at the same offsets. For the `UObject` family the first slots are shared by
hundreds of classes, so the choice between equally voted places is made by the class's own
slots: the place where most of them hold a reference function with the same masked bytes,
within three slots. Each slot is then aligned by body similarity (same length, 90 % of the bytes
equal outside relocation fields), and the steps in the offset between ours and the reference's
are read off. Short bodies (`ret`, `xor al, al`) say nothing on their own. Their order is
compared as a sequence instead, against all of a class's reference vtables (overrides tell
the slots apart), and against callers whose slots are known. Some return paths in the image
are obfuscated (`lea rsp, [rsp+8]; jmp [rsp-8]` for `ret`; `push rbp; lea rbp, [rip+X];
xchg [rsp], rbp; ret` for a jump) and are followed through.

**UObject.** Every pair of exact slots on one side of public offset `0xA0` keeps its distance
in the reference; every pair across it is 8 bytes closer. The slot at `0xA0` is
`Serialize(FStructuredArchive::FRecord)`: MSVC places overloads together, in reverse order. UHT
overrides it in 324 generated classes; `IAssetRegistry` declares it too, and the reference's
`UAssetRegistryImpl` has one `Serialize` thunk where ours has two (ENGINE_DIFFERENCES #14). The
overload and UHT's overrides are made non-virtual, not removed; only the interface's pure
virtual goes (see "Data order" below).

**Derived classes.** The UObject fix made 951 functions exact and cost 16. The 5 that lost
their placement call virtuals of classes that have one more virtual than public 4.20: the two
differences had cancelled. Those classes were measured the same way (ENGINE_DIFFERENCES
#16–#18):
- `UActorComponent::OnRep_IsActive` is not virtual (its exec thunk jumps to it directly);
- `AActor::RewindForReplay` is not virtual;
- `AController` declares `InitNavigationControl` and `UpdateNavigationComponents` after
  `FailedToSpawnPawn`;
- `UPathFollowingComponent` has the path-following agent callbacks as its own virtuals and no
  virtual `OnNewPawn`;
- `ANavigationData` has `ProjectPoint` as its own virtual, and `CalcPathLength` before
  `CalcPathCost`;
- `UEngine` has two more virtuals after `ShouldThrottleCPUUsage` and three fewer later;
- `UMovieSceneTrack` has one more after `SupportsMultipleRows`.
A virtual the reference lacks becomes non-virtual, so its callers still compile. A slot the
reference has, where public 4.20 has none or declares the function in a 4.20 interface,
gets a placeholder virtual (`FNLayout_*`) with the slot's trivial body. Placeholders take no
name from the reference: none survives.

**Patches.** `layout.py` replaces whole lines, one for one, so `__LINE__` and the line overlays
are unaffected. Each original line is named by a hash of its text; a replacement is literal
text, the line without its first `virtual`, or other original lines joined (a declaration
moved). The engine's own text therefore stays in the local tree. Headers are compiled from a
mirror of their whole include root: MSVC looks up a quote include in the including file's
physical directory and the directories of the files that included it, before the `/I` paths. A
copied header ahead on the `/I` path would still find its neighbours in the original tree.
The response files' `/I` of the root, and of its ancestors (generated code includes
`CoreUObject/Public/...` through `/I Runtime`), name the mirror. `/showIncludes` fails any unit
that still opens an original file of a mirrored root. Measured with MSVC 19.00:
- `#line 1 "<file>"` above `#pragma once` makes the compiler include the file a second time.
- A `#line` naming another file anywhere in a header changes the order in which the compiler
  allocates static data and literals in the whole unit, for definitions in `.cpp` files too
  (`EditorLayoutsSectionName`, `LayoutService.cpp`, moved to the front of `Slate`'s `.data`).
  The mirrored copies therefore carry none; their `__FILE__` is the mirror's path, which only
  `PURE_VIRTUAL`-style stubs pass on.
- Mirroring a root without changing its files leaves every object as it was.
- Lambda and anonymous-namespace names follow the translation unit, not the header's path.

**Data order.** MSVC's order of a unit's statics, literals and vtables also depends on the
declarations it compiles. Deleting UHT's `Serialize(FRecord)` overrides moved
`FMediaAssetsModule`'s vtables in `MediaAssets` from before the `MEDIA` literal (where the
reference has them, as the plain build does) to after `LogMediaAssets`, and put an empty literal
in front of `FCopyTexture2DCS`'s vtable. Neighbours then placed those vtables wrongly. Keeping
the declarations and dropping only `virtual` leaves those units' order as the plain build's
while the vtables lose the slot, so the overload is modelled that way.

**Section-relative rules.** Where a data symbol's two sides of observed neighbours disagree,
`compare.py` now tries the symbol's own evidence before the run vote. A vtable goes where its
exact slot functions' pointers are together and nowhere else, without requiring its first
slot. Where they fit several places, a side whose prediction is one of them, and the other
side's not, decides. Equal runs that the strict rules leave open go to the side whose nearest
observed neighbour has fewer layout items between, then fewer bytes. Each was scored on every
logged disagreement first (`FN_SR_LOG=<path>`: the fields with both predictions and the side
the reference holds):

| Rule | Decided | Right | Wrong where the run vote was right |
| --- | --- | --- | --- |
| vtable's own slots, one place | 1,469 | 1,460 | 0 |
| vtable's own slots fit one side | 411 | 388 | 0 |
| nearer side, equal runs left open | what nothing else decides | | 0 by construction |

Letting the nearer side override the run vote in general would have cost 6 to 39 exact
functions in the same estimate, so it does not. A miss of the first two is reported as an
unresolved field, like any layout prediction.

**Not modelled.** The measurements also found differences that need more than a slot:
- `FArchive` has the interface from before structured archives (ENGINE_DIFFERENCES #19): 44
  virtuals and 0x88 bytes, so every derived archive's members are 8 bytes off.
- `UPathFollowingComponent`'s members are 0xE0 bytes later, and it has one interface vtable
  fewer.
- `FConsoleVariable*` hold their data at `0x68` where ours is at `0x38`, and the `ECVF_SetBy*`
  values differ.
- `FTextFormatter::Format` allocates `0x210` bytes for a history where ours allocates `0x160`.

**Results.** 53,986 exact (52,409 before). 1,610 functions became exact: 909 newly placed and
701 that were relocation-equivalent, 1,576 of them engine functions. On the way:
- the `UObject` patch alone (deleting the overload) gave 951 and cost 16. 5 had lost their
  placement to the derived classes' cancelling differences, which are now modelled;
- `#line` in the mirror and the deleted declarations had moved data in other units (above).
  Without either, 1,201 became exact and 10 regressed;
- the section-relative rules then recovered all but one.

One function is relocation-equivalent that was exact:
`TGraphTask<EURCMacro_FUpdateLightShaftOverrideDirectionCommand>::ExecuteTask` (`0x01F0EDF0`).
Its task vtable's right-hand neighbours (2 items away) predict the reference's address. The
left run of 5 agreeing neighbours, 20 items away, predicts 0x160 bytes too far and wins the
vote. Between them lie `UDecalComponent`'s, `ULightComponentBase`'s, `ULightComponent`'s and
`UDirectionalLightComponent`'s vtables, whose `USceneComponent` family is not modelled yet. A
`LightComponent.h` `__FILE__` literal is there too, 0x40 bytes longer under the mirror's path
(the reference's `D:\Build\++FN25\Sync` form lies in between). At HEAD the left prediction was
just as far off; the oversized `UObject` vtables split that run, and the right side won.

A nearer side ten times closer than the other would decide this case, but that threshold is
only where the estimate stops losing exact functions, so it is not used. Over all logged
disagreements the nearer side is right in all 73 cases where it is 16 or more times closer.
Engine manifests: 26,032 entries, 16,745 exact, 9,056 relocation-equivalent, 231 partial.

### Second batch: `USceneComponent`, `FArchive`, header-name lengths (2026-11-27)

**`USceneComponent`.** One slot fewer before `SetMobility`, inherited by every scene component:
`CalcBounds` is followed by `CalcBoundingCylinder`, `ShouldCollideWhenPlacing` and
`UpdatePhysicsVolume`, so `UpdateBounds` is not virtual. `UPrimitiveComponent`'s own virtuals
are a constant slot earlier throughout. Its apparent ±8 pairs (`AddImpulse` and
`AddAngularImpulse`, `SetAllPhysicsPosition` and `SetAllPhysicsRotation`) are bodies too alike
to tell apart, not swaps. So its `UpdateBounds` override is not virtual either.

**`FArchive`** (ENGINE_DIFFERENCES #19). The reference's 44 slots, identified by their bodies
across the 50 vtables derived from it, are public 4.20's 57 with these changes:
- 17 removed: `IsProxyOf`, `GetCacheableArchive`, `Push`/`PopSerializedProperty`, `Reset`
  and the 12 setters;
- `IsFilterEditorOnly` and `IsSaveGame` virtual;
- an empty slot after `GetArchetypeFromLoader`;
- an `IsCloseComplete`-shaped slot after `ResetCustomVersions`.

The missing 8 bytes are `SerializedPropertyChain`: the reference's `FArchive::FArchive`
(`0x011D0DA0`) stores every member ours stores except it. Modelled, the vtable has the 44 slots
in the reference's order, and the constructor's bytes equal the reference outside relocation
fields.

**Header-name lengths.** A mirrored header's `__FILE__` is the mirror's root plus the path
below it. The mirror now lives at a path exactly as long as the reference's
`D:\Build\++FN25\Sync\Engine\Source` (`local-output/mirro`), so those literals have the
reference's size and the data around them its layout. The content still differs, as it did
for every header before.

**Tried and dropped: discarded COMDATs.** Each object's layout counts every COMDAT section,
but the linker keeps one copy of a shared COMDAT, so later objects' copies take no space in the
image. A rule ranked objects in link order by the median address of their placed functions. It
then dropped the sections that an earlier object also defines, and took a discarded symbol's
neighbours from the object kept. Against the same objects, it made 60 more functions exact and
cost 18. It dropped `__real@` float constants from `Engine.gen.13` that the reference still
holds there, for one. The simple first-definer model is not how this image was linked, so the
rule is not used. The light-shaft task vtable would also need identical-COMDAT folding: the
two `UDecalComponent` delegate-instance vtables between it and its neighbours are absent in
the reference and are defined nowhere else.

**Results.** 54,299 exact (53,986 before). 316 functions became exact: 276 newly placed and 40
that were relocation-equivalent. 3 regressed:
- `FLargeMemoryWriter::GetArchiveName` (`0x00726920`). The reference function returns a copy
  of the `FString` at `0xB0`; ours now reads `0xA8`. It is a folded getter in the region of
  identical generic bodies. Its only pointer is slot 0 of a table at `0x02FA9F60`, whose other
  slots are getters of the same shape (an `FString` at `0x68` and others), not an `FArchive`
  vtable. None of the 17 other `FLargeMemoryData`, `FLargeMemoryReader` and
  `FLargeMemoryWriter` functions we compile has been placed, `FLargeMemoryData::Write` and
  `GrowBuffer` included, which do not depend on `FArchive`. So the class is most likely not
  linked, and the old match was another class's getter. It matched ours only while our
  `FArchive` was 8 bytes too large.
- `FWidget3DHitTester::FWidget3DHitTester` and
  `TGraphTask<...FDestroySkyLightCommand>::ExecuteTask`. Each has a vtable that only
  neighbours place, and its neighbours now lie across scene-component vtables one slot shorter.

The light-shaft task above is still relocation-equivalent. Engine manifests: 26,433 entries,
17,058 exact, 9,142 relocation-equivalent, 233 partial.

## Reflection registration data (`tools/analysis/reflection.py`)

UHT-generated tables in plaintext `.rdata` name functions directly. The output is
`analysis/reflection-natives.json`, with names and RVAs only.

| Table | Layout | Found |
| --- | --- | --- |
| `FNameNativePtrPair[]` (per class, in `StaticRegisterNatives<Class>`) | {name, exec thunk} | 1,180 class arrays, 9,977 entries, 9,261 distinct exec thunks (some ICF-folded) |
| `FClassFunctionLinkInfo[]` (per class, in `FClassParams`) | {`Z_Construct_UFunction_*`, name} | 1,243 arrays, 11,102 entries |

The two layouts interleave the same pointer kinds, so a run read at the wrong 8-byte
alignment looks like the other table with one entry fewer. A run is kept only when it is
longer than every run of the other kind that overlaps its shifted reading.

A native array directly after an array of function pointers (2026-11-24) breaks that rule.
An example is a class's `DependentSingletons`: read 8 bytes off, the native array is a link
array as long as itself. Its "creators" are the preceding pointer and the exec thunks, so
both readings were dropped. 25 classes lost their array this way, and their
`StaticRegisterNatives` stayed declared only. 24 of their `GetPrivateStaticClass` bodies
waited on it.

A real function-link array points only at `Z_Construct_UFunction` creators, 47-byte
singletons of one template (`uht_creators.py`). So on a tie the native reading is now kept
unless the link reading is all creators (`keep_runs`). Regenerated, the analysis gained
exactly these 25 arrays and nothing else changed. The function-link arrays are identical.

An exec thunk with no parameters is P_FINISH and a tail call. It is a leaf function without
a `.pdata` entry, and 1,374 thunks are of this kind. Pointers to them are accepted when the
code starts with P_FINISH's load of `Stack.Code` (`mov r64, [rdx+0x20]`). The first version
of the scanner accepted only `.pdata` starts, so these entries split their arrays and hid
their starts. Accepting them raised the attributed arrays from 696 to 1,155 and their entries
from 3,070 to 9,902. The scanner had also kept 7 fragments of native arrays as
function-link arrays; they are now dropped. The 16 remaining unattributed arrays are libcurl protocol tables, not UHT data.

Class attribution follows unique RIP-relative `LEA` references in the decrypted code: the
native array is loaded by exactly one function (`StaticRegisterNatives<Class>`). That
function's address is loaded by exactly one function (`GetPrivateStaticClass`), which also
loads `TEXT("<Class>") + 1`, i.e. a wide string + 2. This attributes 1,180 of 1,196 arrays.
No class, registrar or `GetPrivateStaticClass` is shared between attributions. In total
21,348 denominator functions now carry reflection-derived names. Names from these tables
count as `confirmed`; class attribution as `high-confidence inferred`. With the corrected
arrays, all 1,180 `StaticRegisterNatives<Class>` match exactly.

With the 25 arrays recovered (2026-11-24), the generators emit those classes' registrars with
their tables. This made exact, with no regressions:
- the 25 registrars;
- 24 of the waiting `GetPrivateStaticClass` bodies;
- 25 `StaticClass` thunks;
- 2 newly known exec thunks and 1 native accessor.

The last body still waits on `InternalConstructor<C>`. 6 `UMcpProfile` classes have native
UFunctions, but the reference uses the shared empty registrar. Their table is not located,
so they stay declared only.

## Native implementations (`tools/analysis/natives.py`)

Each exec thunk calls the C++ function it wraps. UHT 4.20 chooses that function's name
(`CppImplName`, `ParserHelper.h`) from the UFunction's flags:
- native RPCs (`FUNC_Net`, unless `FUNC_NetResponse`) call `<Name>_Implementation`, first
  checked by `<Name>_Validate` when `FUNC_NetValidate` is set;
- native Blueprint events call `<Name>_Implementation`;
- everything else calls `<Name>`.

The flags come from the function's `FFunctionParams` record (`+0x20`).

The thunk is disassembled from P_FINISH's store to `Stack.Code` onwards. Aliases of Stack,
Context and Context's vtable pointer are tracked through registers, spills to stack slots
(`rsp`- or `rbp`-relative), and across branches. The native call is:
- either a direct call or tail jump to a function that no other exec thunk calls. Helpers
  such as the `FString` copy are shared by many thunks.
- or a call through Context's vtable.

A thunk is named only when exactly the predicted calls are found, in order: one, or the
`_Validate` / `_Implementation` pair. For a validated RPC, the `RPC_ValidateFailed` literal
must agree with the predicted name.

The linker folds identical thunks. One `P_FINISH; jmp [vtbl+0x410]` body serves 11
UFunctions in unrelated classes. A folded thunk that calls only vtable slots is resolved
for each of its UFunctions, since the slot belongs to each owner's vtable. A folded thunk
with a direct target stays unresolved, because one address cannot carry each owner's name.

A direct native that is not static must receive Context in rcx. Of the 5,189 member
natives, 10 did not; those natives were inlined into the thunk, so the call belongs to one
of their callees. They stay unresolved.

A second check is the module range. A monolithic link keeps a module's objects together,
so a native lies next to its package's generated code. 104 named natives do not: identical
code folded with another module's, or a static native inlined around an outside call. They
are kept as `low-confidence inferred`.

| Result | Count |
| --- | --- |
| exec thunks attributed to a class | 9,193 (1,374 leaf) |
| direct natives named | 6,948, 6,842 high-confidence (5,217 in the denominator, 1,731 leaf) |
| virtual natives, located by vtable offset | 1,995 (962 of them through folded thunks) |
| unresolved (per UFunction) | 1,187: inlined or shared natives 835, folded thunk with a direct target 246, other call counts 69, no P_FINISH store 26, member call without Context 10, target already a generated function 1 |

Every UFunction's flags are known since all its `FFunctionParams` records are identified
(see the creators below). Before that, 396 UFunctions were left with "flags unknown". They
now yield 190 more direct natives and 115 more virtual natives, and 75 more folded thunks
with a direct target.

`natives.py` treats a call target that a manifest already records as a generated function as
a conflict. The native accessors (`analysis/functions-native-accessors.json`) are excluded
from that check: they are reconstructions of these natives, not other functions.

Engine headers corroborate the results where the local UE4.20.0 source declares the
function:
- 2,653 of the 2,673 direct natives are non-virtual (99.25 %). The other 20 are declared
  `virtual` in public 4.20.0 but called directly here, a candidate engine difference
  ([ENGINE_DIFFERENCES.md](ENGINE_DIFFERENCES.md) #4):
  - `UAbilitySystemComponent`: `MakeEffectContext`, `MakeOutgoingSpec`,
    `OnRep_ActivateAbilities`, `OnRep_ReplicatedAnimMontage`, `RemoveActiveGameplayEffect`,
    `RemoveActiveGameplayEffectBySourceEffect`, `SetActiveGameplayEffectLevel`,
    `SetUserAbilityActivationInhibited`, `TargetCancel`, `TargetConfirm`;
  - `UGameplayAbility::RemoveGrantedByEffect`, `UActorComponent::OnRep_IsActive`;
  - `UUserWidget::GetOwningLocalPlayer`, `UWidget::IsHovered`;
  - `UCheatManager::InvertMouse`, `UCheatManager::SetMouseSensitivityToDefault`;
  - `UCharacterMovementComponent::K2_ComputeFloorDist`, `UCharacterMovementComponent::K2_FindFloor`;
  - `ADefaultPawn::LookUpAtRate`, `ADefaultPawn::TurnAtRate`.
- Of the first 1,451 virtual natives (unshared thunks), 345 of the 355 with a declaration
  are declared `virtual` (97.2 %). The 10 others are header-inline natives whose inlined
  body calls a different virtual function (for example
  `AController::IsLocalPlayerController`). The binary alone does not show this. Where it
  matters, the vtable model exposes it: two names for one slot (2 cases, both withheld) or
  a generated thunk that does not match (2 cases, `partial`).

A thunk with a direct native depends on the native's address, which nothing else
corroborates, and on decoded parameter properties. Thunks that only call vtable slots can
match: see "Class vtables" below.

## Class vtables (`tools/analysis/vtables.py`, `tools/codegen/uht_exec.py`)

The build has no RTTI (`/GR-`), so vtables are found through code.
`InternalVTableHelperCtorCaller<C>` returns nullptr without hot reload, a single folded
`xor eax, eax; ret` for every class. `InternalConstructor<C>`, also passed to
`GetPrivateStaticClassBody`, runs `C::C(const FObjectInitializer&)` on `X.GetObj()`.
It does so by a (conditional) tail jump or with the constructor inlined. The constructor
calls the superclass's constructor and then stores C's vtable at `[this]`. The last store
of a `.rdata` address to `[this+0]` on that path is C's primary vtable. Stores at other
offsets are recorded as secondary vtables (1,253 classes, interface subobjects).

| Result | Count |
| --- | --- |
| classes with a primary vtable | 3,299 of 3,333; 27 without a store found, 7 not decoded |
| distinct vtables | 2,653; 152 are shared by 798 classes (identical vtables folded by `/OPT:ICF`) |
| UObject-derived vtable starts in `.rdata` | 2,684 |

**Slot counts.** Vtables are packed without separators, so a run of code pointers continues
into the next vtable. `UObject`'s vtable has 71 slots: slots 1-70 are inherited by 85-100 %
of its 420 direct children, and slot 71 by 5 %. Every UObject-derived vtable repeats most
of that prefix (slot 0, the destructor, differs). So a position where at least 35 of slots
1-70 match is a vtable start. A run ends at the next start.

A run followed by a non-UObject vtable still overruns: by run, `UObject` would have 136
slots. Each class therefore gets two bounds:
- an upper count: its own run, capped by every descendant's;
- a lower count from evidence: the superclass's count, its own virtual natives, and slots a
  descendant with a different vtable inherits unchanged. A function that occurs at more than
  one slot index anywhere (a folded stub) is not evidence.

No class has a lower count above its upper count. Examples (lower-upper):
- `AActor` 189-189, `UActorComponent` 116-119, `APawn` 226-229;
- `ACharacter` 265-271, `APlayerController` 421-437.

The cap matters: equal-length vtables followed by similar Slate vtables otherwise share
overrun entries (`UCommonListView` would get 119 slots where a descendant's vtable has 89).

**Names.** A virtual native names slot *i* of its class and of every descendant. The slot is
introduced by the topmost ancestor whose lower count exceeds *i*. Interface UFunctions
(`CLASS_Interface`) call through the I-class's own vtable. Their 83 slots are listed
separately; at first they produced 54 conflicts on `UObject` slots 0-8.

Each descendant's entry at slot *i* implements the function. It is named after the topmost
class on the path whose entry is that pointer. An address is reported as folded, not named,
when it:
- receives two names;
- occurs at several slot indexes; or
- carries a different high-confidence direct-native name.

| Result | Count |
| --- | --- |
| named slots | 1,771 (2 slots named differently by two UFunctions, withheld: the inlined-native error above) |
| implementations named | 1,746 (1,365 in the denominator, 1,364 not named before); 58 folded or ambiguous |

743 of the 746 names whose class the local UE4.20.0 headers declare are declared there:
the function itself, or its base name for UHT-generated `_Implementation`s. The other 3
come from the inlined-native error. This brings the named denominator functions to 27,699
(17.56 %).

**Generated declarations and thunks.** `Classes.gen.h` declares each class's new slots in
order. An introduced slot is declared by name when its UFunction's whole signature is
supported (see "Exec thunk parameters" below); `_Validate` returns bool. That gives 1,606
named declarations.

Other slots are placeholders (`virtual void FNGC_VSlot_0x<offset>()`): 4,053 gaps and 166
named slots whose signature uses a type not modelled yet. MSVC lays out single-inheritance vtables in declaration
order. The root becomes polymorphic, its destructor in slot 0 as in `UObjectBase`, and its
opaque member shrinks by the vptr, so every `sizeof` is unchanged.

A thunk that only calls slots declared by name is written as UHT 4.20's `DECLARE_FUNCTION`:
- the `P_GET_*` reads;
- `P_FINISH`;
- the optional `_Validate` check with `RPC_ValidateFailed`;
- the call.

UHT defines thunks inline in the class body. Here they are defined out of line in the class's
`IMPLEMENT_CLASS` fragment: inline definitions of only some of a unit's thunks changed
MSVC's emission order of other functions' static locals, breaking 57 `StaticEnum` layout
predictions.

Out of line, the effect is small and changes as thunks are added. Even one definition in
`Paper2D.1` moves one `StaticEnum` singleton to the front of the unit's `.bss`. With the
first 379 thunk addresses, the net was 2 `StaticEnum` matches fewer than without thunks.
The count then moved with each batch:

| Thunk addresses | `StaticEnum` | `FCompiledInDeferEnum` |
| --- | --- | --- |
| 979 | 381 (1 more) | 252 (1 more) |
| 1,052 | 380 (level) | — |
| 1,091 | 378 | 251 |
| 1,115 | 367 | 239 |
| 1,158 | 381 | 251 |
| 1,158, external `StaticEnum` | 373 | 242 |
| 1,191, external `StaticEnum` | 373 (level) | 242 (level) |
| 1,200, with the prologue's vector constants | 374 | 243 |
| 1,200, per-unit vector constants | 374 (level) | 243 (level) |

Bisecting one unit (`NVIDIAGfeSDK.1`, which has no thunk of its own) showed something more.
The order changes once enough unrelated declarations in `Classes.gen.h` change, here 31 slot
declarations gaining their signatures; no single line does it. So these layout predictions
depended on the whole unit, not only on the thunks.

The cause: UHT makes `<Enum>_StaticEnum` file-static, and MSVC emits such internal
functions' statics in an order that depends on everything parsed before them. With external
linkage they are emitted in definition order. `StaticEnum` is now generated that way (last
row; see "Enum constructors and `StaticEnum`"). Compiled against this `Classes.gen.h` and
against the one before the parameters were decoded (9301f5e92), these units give the same
order, the source order:
- `NVIDIAGfeSDK.1`, `Paper2D.1`, `CoreUObject.2` and `InputCore.1`;
- `Engine.9` (65 enums), `FortniteGame.22.s7` (54) and `AIModule.2.s6` (16);
- `Engine.4.s1`, `Foliage.2`, `FortniteGame.24.s1` and `CommonUI.4.s1`.

Main units whose thunks need the decoded parameters don't compile against the older header.

| Exec thunks generated | Count |
| --- | --- |
| UFunction thunks defined | 1,808, at 1,540 addresses (folded bodies share one manifest entry each); 949 read parameters |
| of which call a native accessor (below) | 207, all exact |
| exact | 1,530: 1,318 in the denominator, 212 leaf (no `.pdata`) |

The newly located virtual natives share some folded thunks that were already exact, such as
`P_FINISH; jmp [vtbl+0x5E8]`. Their manifest entry, one per address, now carries another
folded UFunction's name; `tools/matching/regressions.py` reports these as renames.
| relocation-equivalent | 6: `UPaperGroupedSpriteComponent::UpdateInstanceTransform`, `UFortItem::GetPreviewAssets`, `UGameplayAbility::GetContextFromOwner`, `APartyBeaconClient::ServerReservationRequest`, `IAssetRegistry::GetAssetByObjectPath` and `AFortPlayerController::ServerSetInventoryStateValue` (below) |
| `partial` | 3: natives inlined from headers (`AController::IsLocalPlayerController`, `UPrimitiveComponent::K2_IsQueryCollisionEnabled`, `ACharacter::GetBaseRotationOffsetRotator`) |

The thunks call `RPC_ValidateFailed`, `FFrame::Step` and `FFrame::StepExplicitProperty`,
and, for strings and arrays, `TArray<T>::ResizeForCopy`, `FMemory::Free` and `memcpy`
(through its import thunk). Texts add `FText`'s out-of-line constructor, copy constructor
and move assignment. Each is corroborated by the other thunks. The validated RPCs
also use `TEXT("<F>_Validate")` (literal content).
So the bytes alone, with the vtable offsets, carry the evidence.

## Exec thunk parameters (`tools/codegen/uht_props.py`)

A UFunction's `FFunctionParams` points to its property records, which give each
parameter's type, name, flags and offset (`UE4CodeGen_Private`, no metadata in shipping).
`ConstructUProperties` builds them in array order and prepends each to the function's
property chain, so the array lists parameters in reverse declaration order. Arrays and
sets are followed by one inner record, maps by two, and enum properties by their
underlying property. In all 969 parameterised virtual-native UFunctions, the `Offset` fields
decrease along the array, which confirms the order.

The thunk text follows `ExportFunctionThunk`:
- one `P_GET_<GetCPPMacroType>` per parameter (`UBOOL`, `OBJECT`, `STRUCT`, `ENUM`,
  `PROPERTY` with `U<Name>Property`);
- `_REF` and `Z_Param_Out_<Name>` for `CPF_OutParm`;
- an explicit conversion for enums.

The native's declaration follows `ExportCppDeclaration`: `const` for `CPF_ConstParm` and
`&` for `CPF_OutParm` or `CPF_ReferenceParm`. The header parser sets both for `const T&`.

Supported types:
- bool, the integer and floating-point types, `FName`;
- pointers to reflected classes;
- `UClass*` (not `TSubclassOf`);
- enums in their `UEnum::ECppForm` from `FEnumParams`;
- seven structs defined from the UE4.20 headers: `FVector`, `FRotator`, `FVector2D`,
  `FLinearColor`, `FGuid`, `FGameplayTag` and `FGameplayAbilitySpecHandle`;
- `FString`, and `TArray` of any of these element types except enums. `ConstructItems` and
  `DestructItems` are 4.20's `MemoryOps.h` pairs, chosen by `TIsBitwiseConstructible` and
  `TIsTriviallyDestructible`: placement-new copies and destructor loops for `FString`,
  `FText` and the non-trivial structs, `Memcpy` and nothing for the others;
- `FText` and `TSubclassOf<C>` (`TextRecovered.h`);
- from `EngineStructsRecovered.h`:
  - `FVector_NetQuantize` and its 10/100/Normal forms, `FHitResult`, `FPredictionKey`,
    `FColor`, `FMargin`;
  - `FKey` (`FName` and a non-thread-safe `TSharedPtr`);
  - `FUniqueNetIdRepl` (`FUniqueNetIdWrapper`'s vptr and `TSharedPtr`, then
    `ReplicationBytes`);
  - `FGameplayEffectContextHandle` (vptr and `TSharedPtr`);
  - `FGameplayTagContainer` (two `TArray<FGameplayTag>`) and `FGameplayCueParameters`;
  - `FViewTargetTransitionParams` and `FGameplayAbilityActivationInfo`, with the two enums
    their constructors name (`EViewTargetBlendFunction`,
    `EGameplayAbilityActivationMode`). These are defined with the enumerator values of the
    reference's `FEnumParams`, which agree with 4.20, and are not redeclared in
    `Classes.gen.h` (`uht_props.MODELLED_ENUMS`);
- `FGameplayAbilityTargetDataHandle` (`TArray<TSharedPtr<FGameplayAbilityTargetData>,
  TInlineAllocator<1>>`) and `FGameplayEventData`;
- `FPartyReservation` and `FPlayerReservation`, the latter with the reference's members (no
  crossplay fields; `docs/ENGINE_DIFFERENCES.md` #7);
- `FAthenaQuickChatActiveEntry`, Fortnite-only (below);
- `FAssetData` (with `FAssetDataTagMapSharedView`), `FGameplayAttribute`,
  `FGameplayEffectModifiedAttribute` and `FGameplayEffectSpecForRPC`;
- `FFastArraySerializerItem`, and the Fortnite-only `FFortItemEntry`,
  `FFortItemEntryStateValue` and `FFortGiftingInfo` (below);
- `FModifierKeysState`, `FInputEvent` and `FPointerEvent` (without 4.20's `Force`), and the
  Fortnite-only `FFortConversationSentence`, `FFortSentenceAudio` and
  `FFortFeedbackHandle` (below);
- `FGeometry`, with `FMatrix2x2` and `FTransform2D` (`FSlateRenderTransform`) (below);
- `FSlateBrush` (without 4.20's `ResourceHandle`), `FSlateColor` and `FBox2D` (below);
- `FTransform` (`TransformRecovered.h`, below);
- soft object pointers, `TSoftObjectPtr<C>` (`EngineStructsRecovered.h`): `FSoftObjectPath`,
  `TPersistentObjectPtr`, `FSoftObjectPtr` and `TSoftObjectPtr`, read with
  `P_GET_SOFTOBJECT(_REF)` (`USoftObjectProperty::GetCPPMacroType`). The class comes from
  the property's `ClassFunc`.

A struct is used only when the reference's `FStructParams` give the same `SizeOf` and
`AlignOf`. Enums are declared with their form and underlying type only, no enumerators.

The shims follow the 4.20 headers where the thunks depend on them:
- `FFrame` with its full layout (`Code` +0x20, `PropertyChainForCompiledIn` +0x80);
- the `StepCompiledIn` / `StepCompiledInRef` templates;
- the `P_GET_*` macros, `TCppType` and `GetDefaultPropertyValue()` of the property classes;
- `TEnumAsByte`;
- `UField : UObject` with `Next` at +0x28, where `StepCompiledIn` reads it in the
  reference.

`FName` became the 4.20 union with `uint64 CompositeComparisonValue`, which makes it
8-aligned. The reference agrees: `FCollisionProfileName`, holding only an `FName`, has
`AlignOf` 8. No existing match changed.

Object properties' `ClassFunc` is `Z_Construct_UClass_<C>_NoRegister`, folded with
`<C>::StaticClass` in all 456 cases. A first version mapped classes by constructor only,
which left every object parameter unsupported.

Limits:
- **Containers.** `FString` and `TArray` come from `ContainersRecovered.h`, a port of the
  4.20 members the thunks use:
  - `FMemory`: out of line on Windows, `Memcpy` inline;
  - `FHeapAllocator::ForAnyElementType` and `DefaultCalculateSlackReserve`;
  - `TArray`'s constructors, assignments, destructor, `CopyToEmpty`, `MoveOrCopy` and the
    `FORCENOINLINE ResizeForCopy`;
  - `FString`'s defaulted members.

  A by-value `FString` is copied through `CopyToEmpty` (`ResizeForCopy`, `memcpy`). A
  returned one is move-assigned into `Z_Param__Result`. The destructor's `DebugGet` dummy
  is kept as in the source; MSVC drops the side-effect-free call, as in the reference.
- **`const FString&`.** HeaderParser drops `CPF_ConstParm` from `const FString&`
  parameters; only UHT's own data keeps the reference. So the records show no flags for
  either form. RPC parameters must be const references (UHT reports an error otherwise),
  which settles 33 UFunctions. For the 20 others, the reference thunk shows the form:
  - a by-value string is copied before the native call, two direct calls each;
  - a reference passes the local's address with no call.

  18 pass by reference and 2 by value. Declaring all 53 by value first left 41 thunks
  unmatched; with the recovered forms, all match.
- **`FText` and `TSubclassOf`.** `TextRecovered.h` ports from the 4.20 headers:
  - `FText`'s members (a thread-safe `TSharedRef<ITextData>` and `Flags`, 0x18 bytes) and
    its out-of-line special members;
  - the inline release of `FSharedReferencer`: `_InterlockedDecrement` of the shared count,
    `DestroyObject` (vtable slot 0) at zero, then the weak count and the deleting destructor
    (slot 1), as the reference does;
  - `TSubclassOf`'s pointer member and constructors.

  `const FText&` keeps its flags (no special case in the header parser). UHT reads a
  `TSubclassOf` parameter as a `UClass*` (`P_GET_OBJECT(UClass, ...)`) and converts it at
  the call. An out parameter is passed as the wrapper itself (`bPassAsNoPtr`:
  `P_GET_OBJECT_REF_NO_PTR`). Its class comes from `FClassPropertyParams::MetaClassFunc`.
- **More structs.** Each struct's member offsets were checked against its reflected
  properties (`FStructParams`) before modelling. For example, `FHitResult`'s `Time` is at 8,
  its weak pointers at 96-112 and its names at 120/128; `FUniqueNetIdRepl::ReplicationBytes`
  is at 24.
  - The constructors and destructors are the 4.20 ones. `FHitResult()` is `Memzero` plus
    `Time = 1.f`; `FWeakObjectPtr()` sets `INDEX_NONE`. Each polymorphic struct's inline
    constructor stores its own vtable. Its destructor stores the struct's vtable, then the
    base's, then releases the `TSharedPtr` (non-atomic: `ESPMode::Fast` is not thread-safe
    on Windows). The other thunks corroborate the vtables' addresses.
  - `FGameplayTagContainer` (GameplayTags) is two `TArray<FGameplayTag>`, at 0 and 16.
    Its copy constructor calls the out-of-line `operator=` of `GameplayTagContainer.cpp`.
  - `FGameplayCueParameters` matches its 16 reflected properties: `EffectContext` at 8, the
    tags at 32/40, the tag containers at 48/80, `Location`/`Normal` at 112/124, the weak
    pointers at 136-160 and 176. Its copies and destructor are implicit. Its constructor
    zeroes `Location` and `Normal` through `FVector(EForceInit)`, added with `EForceInit`.
  - `TArray` elements may be any modelled type (see the list above). That added 7 thunks,
    including `TArray<FString>`, `TArray<FText>` and `TArray<FHitResult>` by value, all
    exact.
  - Soft object pointers follow the 4.20 headers, with one difference.
    - The default constructor is `TPersistentObjectPtr::Reset()`: an `INDEX_NONE` weak
      index, `NAME_None`, an emptied string and a zero tag. That needs `FName(EName)`,
      `TArray::Reset`, `Empty`, `ResizeTo` and `FString::Reset`, all ported.
    - A returned pointer is assigned through `TPersistentObjectPtr::operator=`: the weak
      pointer, the tag, then `FSoftObjectPath::operator=`. The reference passes that the
      source path's address and copies it. 4.20 takes the path by value, so this is
      modelled as an out-of-line `const&` assignment (`docs/ENGINE_DIFFERENCES.md` #6).
    - 8 thunk addresses (returns, an out parameter, two `TArray<TSoftObjectPtr<C>>` out
      parameters). 7 are exact. `UFortItem::GetPreviewAssets` is relocation-equivalent: its
      `TArray<TSoftObjectPtr<UObject>>::operator=` is called out of line and nothing else
      corroborates its address.
    - `FKey`'s struct registration initializer, lost in the previous change, is exact
      again: `InputCore.1`'s `.rdata` order moved back with these headers.
  - `FGameplayEventData` needs more of the containers and shared pointers:
    - `FGameplayAbilityTargetDataHandle`'s array uses `TInlineAllocator<1>`. Ported:
      `TInlineAllocator`, `FHeapAllocator::ForElementType`, `IfAThenAElseB`,
      `TTypeCompatibleBytes` and `RelocateConstructItems`. `TArray` picks
      `ForElementType` only for allocators with `NeedsElementType`, so heap arrays compile
      as before.
    - `TSharedPtr` had no assignment operators in the shim, so an implicit copy assignment
      copied its two pointers without touching the reference count. That stayed hidden
      until `GetContextFromOwner` came out 3 bytes short: the reference calls
      `FGameplayEffectContextHandle`'s assignment out of line. Ported from 4.20: the move
      constructor, the copy assignment (a temporary and a bitwise `Swap`) and the move
      assignment of `TSharedPtr`, `FSharedReferencer`'s, `MoveTemp` and `Swap`.
    - 6 thunk addresses. 5 are exact. `UGameplayAbility::GetContextFromOwner` is
      relocation-equivalent: it alone calls the target data handle's copy constructor and
      the context handle's copy assignment, so nothing corroborates their addresses.
      Those of `FGameplayEventData` are shared by several thunks and resolve.
    - `FFoliageTypeObject::StaticStruct` lost its literal again: `Foliage.2`'s `.rdata`
      order moved with the headers, as above.
  - `FAthenaQuickChatActiveEntry` has no source. Its members come from the reference's
    reflected properties: `Bank` (`UAthenaQuickChatBank*`, from its `ClassFunc`) at 0,
    `ContextObject` (`UObject*`) at 8, `int16 ContextValue` at 16, `int8 Index` at 18;
    SizeOf 24.
    - The default constructor is inferred from its inlined code in the thunks: one 16-byte
      zero store for the pointers, then the `int16` and the `int8`, leaving the padding. Copies
      are trivial (the thunks copy 24 bytes).
    - Its 2 thunk addresses are exact, and so is one of the 2 `FPartyReservation` thunks.
      The other, `APartyBeaconClient::ServerReservationRequest`, is relocation-equivalent: its
      `TEXT("ServerReservationRequest_Validate")` has a second copy in the image that nothing
      modelled uses, so literal elimination cannot decide.
    - `FFoliageTypeObject::StaticStruct` is exact again (the same `.rdata` ripple).
  - `FGameplayEffectSpecForRPC` follows 4.20: its default constructor is out of line
    (`GameplayEffect.cpp`), and the reference's thunks call it. They also call its implicit
    destructor, and in the by-value `_Executed_FromSpec` thunks its copy constructor, out
    of line. Several thunks share each, so the addresses corroborate.
    - The 4 spec thunks and `AFortPlayerController::ServerRequestAttributeSources`
      (`FGameplayAttribute` by value, copied inline) are exact.
    - `FKey`'s struct registration initializer lost its literal again (`.rdata` ripple).
    - `FAssetData` is used by the `UAssetRegistry` UFunctions, which are interface
      UFunctions (next point).
- **`FFortItemEntry`** (Fortnite-only) derives from 4.20's `FFastArraySerializerItem`.
  Its members, types and offsets are its reflected properties; its constructor and destructor
  are out of line in the reference, and the thunks call them. Their code confirms the layout:
  - the constructor (`0x00C3DB80`) sets the base's three `INDEX_NONE`, `Count` 1 and
    `Durability` 1.0f, zeroes the rest, and stores the three bools as bytes at 0x60-0x62
    (declaration order assumed);
  - the destructor (`0x0098E350`) frees the arrays and strings at their offsets. It also
    releases a non-thread-safe `TSharedPtr` in `FFortGiftingInfo`'s 16 unreflected bytes
    (after `HeroType`); its pointee type is not recovered.
  - A first version had a `char[16]` there, which gave the thunks a `/GS` cookie the
    reference does not have.
  - `FFortItemEntryStateValue`'s constructor (`0x00C3DC40`) zeroes `IntValue` and
    `NameValue` and stores its argument in `StateType`. The thunk passes 0, so it is modelled
    with a defaulted `EFortItemEntryState::Type` parameter. The enum is declared with the
    reference's enumerators.
  - Both storage-vault RPC thunks are exact (they corroborate each other's constructor and
    destructor). `ServerSetInventoryStateValue` is relocation-equivalent: only it calls the
    state value's constructor.
- **`FPointerEvent`.** The reference's is older than 4.20's: it has no `Force`
  (`docs/ENGINE_DIFFERENCES.md` #8).
  - The exec thunks inline its default constructor: the vtable, `FModifierKeysState`'s nine
    bitfields cleared one by one, the zeroed members, and `PressedButtons` bound to
    `FTouchKeySet::EmptySet`.
  - `TSet` is an empty stand-in. The reference binding only takes `EmptySet`'s address, and
    `FTouchKeySet` derives from `TSet<FKey>`.
  - The 3 `UDragDropOperation` events are exact. They corroborate each other's vtable and
    `EmptySet` addresses.
  - `FFortConversationSentence`'s constructor and destructor are out of line, as for
    `FFortItemEntry`. The 2 `IFortClientAnnouncement_ConversationCodeInterface` thunks that
    take one are exact.
  - `FKey`'s registrar is exact again (`.rdata` ripple).
- **`FGeometry`.** As 4.20. Its default constructor and assignment are out of line
  (`Geometry.cpp`), and the reference's thunks call the constructor; the destructor is
  trivial.
  - It holds no pointers and is larger than 8 bytes, so /GS treats it as a buffer: the
    thunks that construct one have a security cookie, as in the reference.
  - The 7 `UFortTouchControlRegion` touch and tick events (`OnMovePlayerRegionTouchStarted`
    and so on) are exact. They corroborate each other's constructor call.
- **`FSlateBrush`.** The reference's is 120 bytes, 4.20's 136: it has no `ResourceHandle`, and
  its second bitfield is reflected as `bHasUObject` (`docs/ENGINE_DIFFERENCES.md` #5).
  - The bitfields' `SetBit` functions write offset 112, straight after `ImageType`.
  - The exec thunks inline its default constructor: the vtable, a 32.0f image size,
    `FLinearColor::White`, `FVector2D::ZeroVector` for `UVRegion`, and `DrawAs` = `Image`.
    They also inline its destructor, which releases only `TintColor`'s shared pointer.
  - `FSlateColor` and `FBox2D` are as 4.20. `FLinearColor::White` and
    `FVector2D::ZeroVector` are declared; their definitions are not recovered.
  - `SetIcon` and both category getters (`GetSecondaryCategory`, `GetTertiaryCategory`,
    folded with `UFortWorker`'s) are exact.
  - `GetSmallPreviewImageBrush` is relocation-equivalent. It is the only caller of the
    out-of-line copy assignment (`0x0028AB50`), so nothing corroborates that address.
  - That copy assignment matches except for its call to `FSlateColor::operator=`
    (`0x0028ABE0`). Ours differs from the reference's only in register choice: the
    reference loads the vtable into `rdx`/`r8` and saves `rbx` at `[rsp+0x10]`.
  - Both forms occur in the reference: after a shared-pointer swap, 18 releases use
    `rdx` and 109 use `rax`. The cause is open, and neither function is a manifest entry yet.
- **Interfaces.** UHT 4.20 declares an interface's native functions, and their exec thunks,
  in the native `I<Name>` class (`typedef I<Name> ThisClass`), and registers
  `&I<Name>::exec<Fn>`. `UFunction::Invoke` passes the thunk the object's interface address
  as `Context`, so `P_THIS->Fn()` calls through the interface's own vtable.
  - Interfaces are the classes with `CLASS_Interface`: in `FClassParams::ClassFlags` (+0x14)
    for `uht_creators.py`, and in `StaticClassFlags` for `uht_classes.py`.
  - `I<Name>` is declared after `U<Name>`. GENERATED_IINTERFACE_BODY's destructor is slot 0
    and `_getUObject` slot 1; the slots the thunks call come from their call offsets
    (`analysis/native-implementations.json`). `IAssetRegistry::HasAssets` is at +0x10, the
    first slot after those two.
  - 27 interfaces, 67 slots declared by name, 63 thunk addresses. 62 are exact (8 leaf),
    `IFortTeamActorInterface::GetTeam` among them once its `TEnumAsByte` return was
    recovered (below). `IAssetRegistry::GetAssetByObjectPath` is relocation-equivalent: only
    it calls `FAssetData`'s move assignment out of line.
  - `FKey`'s struct registrar is exact again and `FFoliageTypeObject::StaticStruct` lost its
    literal, the `.rdata` ripple once more.
  - Adding these changed the `.rdata` order of `InputCore.1`, which gained no code. Its
    literal sections came out in another order with the previous `ContainersRecovered.h`
    and in a third without `<new>`. So literal section order, like file-static order,
    depends on everything parsed before it. `FKey`'s struct registration initializer lost
    its package-name literal, whose neighbours moved. The other 1,251 struct registrars
    and all literal-dependent functions elsewhere are unchanged.
  - Adding the last two left the `StaticEnum` and registration counts level (table above):
    the layout no longer moves with `Classes.gen.h`.
  - `FTransform` (`TransformRecovered.h`) is three `VectorRegister`s, as in
    `TransformVectorized.h`. Its default constructor reads `GlobalVectorConstants::FloatOne`
    and `XYZMask`.
    - These are per-unit, dynamically initialised statics from `UnrealMathVectorConstants.h`.
      Their initializers (`movaps xmm0, [K]; movaps [slot], xmm0; ret`) open each unit's
      `.CRT$XCU` entries; `FloatOne`'s is the unit marker of the layout model.
    - The reference unit of `AGameModeBase` holds only four: `FloatOne`, `XYZMask`, `Float360`
      and `Float180` (the last two are read by the rotator normalisation).
    - The local compiler keeps every constant a unit defines, used or not: a probe with four
      keeps all four, with or without `/Gw`. So each unit defines exactly the ones the
      reference unit has: "Per-unit vector constants" under "Module layout model".
    - In 13 of 14 reference units checked, the `StaticEnum` singletons come before the
      constants, so they are defined after the `StaticEnum` functions. A first version
      defined them in a header the top-of-unit `StaticEnum` fragments include, and they came
      first. That moved two boundary predictions (one `ReturnEnum` lost, one `Singleton`
      gained).
    - `TransformRecovered.h` is included after a unit's constants, where `FloatOne` and
      `XYZMask` are among them. That covers all five units with `FTransform` thunks.
      `Classes.gen.h` needs only the incomplete type, so `EngineStructsRecovered.h` declares
      it.
    - Of the 6 thunks that take `const FTransform&`, the constants resolve where another thunk
      of the unit reads them (corroboration: `AGameModeBase`'s and
      `UInstancedStaticMeshComponent`'s pairs). `UPaperGroupedSpriteComponent`'s is the only
      reader in its unit and has no observed neighbour there, so it stays
      relocation-equivalent. The 4 that return an `FTransform` read no constants.
- **`<intrin.h>`.** Including it for `_InterlockedDecrement` changed the order in which MSVC
  emitted other functions' static locals in every unit. That cost 36 `StaticEnum` and 27
  `FCompiledInDeferEnum` layout predictions, even in units without new thunks. Declaring the
  intrinsic as MSVC documents (`extern "C"` plus `#pragma intrinsic`) keeps the earlier
  order.
- **Chained fragments.** Returned texts release the temporary in a shrink-wrapped tail with
  its own `.pdata` entry. A thunk's range therefore follows contiguous chained fragments, as
  for `StaticStruct`. The matcher requires equal sizes, so no earlier thunk had been judged
  on a partial range; none was followed by a chained fragment.
- A byte enum (`TEnumAsByte` property) may be declared by the programmer as the raw enum
  or as `TEnumAsByte<E>`. The reflection data does not record which, and the thunk text is
  the same; only the native's declaration differs. `uht_exec.byte_enum_form` recovers it
  from the call, as `strings_by_reference` does for strings.
  - `TEnumAsByte` has a user-provided copy constructor. MSVC therefore passes a by-value
    one as the address of a byte copy, and returns one through a hidden pointer that the
    thunk reads back as `byte ptr [rax]`. A raw enum travels in a register.
  - Rule: between the last call before the native call (the `StepCompiledIn` calls) and that
    call, the stack bytes both stored and address-taken are the `TEnumAsByte` copies. After
    the call, the result is read either through `rax` or from `al`. Counts that fit neither
    form (some but not all parameters) leave the signature unsupported; none occurs.
  - Of the 73 thunk addresses with a by-value byte-enum parameter or return, 66 show the raw
    form. All 66 were already exact.
  - 7 show `TEnumAsByte` and were `partial`; all 7 are exact now. Independent evidence agrees:
    - the 4.20 headers declare `UPawnAction::Finish` and `URadialForceComponent`'s
      `Add`/`RemoveObjectTypeToAffect` with `TEnumAsByte`;
    - the natives at the classes' vtable slots read the parameter as `byte ptr [rdx]`
      (`AFortWeapon::PlayReloadFX`, `UPawnAction::Finish`) or write the return through
      `rdx` (`ABuildingSMActor::GetReplacementDestructionReason`,
      `AFortTimeOfDayManager::GetPreviousDayPhase`);
    - `IFortTeamActorInterface::GetTeam` has only the thunk's call to go on.
- Of the 1,661 virtual-native UFunctions, 1,600 have a supported signature and 1,569 have
  thunks (folded bodies counted per UFunction). For the other 31, a slot is not declared
  by name (a name already declared higher in the hierarchy, or an incomplete validate
  pair). The unsupported ones mostly use structs not modelled:
  - `TArray` of enums (3), and 3 whose struct is not identified;
  - 27 other types, mostly Fortnite-only structs, each the only blocker of 1 or 2.

### Native accessors (`tools/codegen/uht_accessors.py`)

A thunk whose native is called directly needs the native's address, and only the thunk
refers to it. The thunk is the only witness of that address, so the native must be
reconstructed and match first. The simplest natives can be: those whose whole body moves one
reflected member. They take these forms:
- scalar getter or setter: one load from `[this+N]` and `ret`, or one store of the argument
  to `[this+N]` and `ret`;
- struct getter by value: a copy of the struct at `[this+N]` to the hidden return pointer
  (`rdx`), then `mov rax, rdx`;
- struct getter through an out parameter: the same copy to the reference in `rdx`, with no
  return value (`Out = Member;`);
- struct setter: a copy from the reference in `rdx` to `[this+N]`;
- bitfield getter or setter: the storage unit at `[this+N]` shifted and masked to one bit, or
  that bit cleared and replaced by the argument's low bit;
- `TEnumAsByte` or `TSubclassOf` getter: the struct copy (1 or 8 bytes), since both class
  templates have user constructors and are returned through the hidden pointer;
- comparison: `cmp <width> ptr [this+N], imm; set<cc> al`, as `return Member <op> imm;`. The
  condition code decides the operator and its signedness. A pointer compares only with 0,
  as `!= nullptr` / `== nullptr`. Enums are left out, because the generated headers don't
  declare their enumerators.
- null-guarded getter: `mov rax, [this+N]; test rax, rax; je`, a load from `[rax+M]` and `ret`.
  The null path straight after is either a bare `ret` (rax is already zero) or one zeroing
  instruction. This is `return Ptr ? Ptr->Member : <zero>;`. A v140 probe gives exactly these
  bytes; it is also 4.20's `AActor::GetInstigatorController`.

Each form is accepted only when all of these agree:
- N is the offset of a reflected property of the native's class or a superclass.
  - A native bool is located through its `SetBit` function (`mov byte ptr [rcx+N], 1`).
  - A bitfield is located through its `or byte|dword ptr [rcx+N], mask`. That operand is the
    storage width, uint8 or uint32. `FBoolPropertyParams.ElementSize` is 1 for both.
- The property's C++ type is the UFunction's return type, its only parameter type, or its
  only out parameter's type.
- The copy covers exactly the struct's reflected size (`FStructParams`), or the instruction
  width fits the scalar type, or the bitfield's storage width is the access width.
- For a guarded getter, the pointer is a reflected object property, and the loaded member is
  a reflected property of that class at M.

The byte-enum form (`TEnumAsByte` or raw enum) is read from the thunk's call. For a direct
native, that is the first call after `P_FINISH`, when the thunk makes no virtual call.

The natives come from `analysis/native-implementations.json` (high-confidence, called
directly, by a thunk no other UFunction shares). Of 6,758 (before the 190 natives added by
the creator records below), 208 qualify:
- 4,940 are not a short body ending in `ret`;
- 1,076 are not high-confidence direct natives;
- 357 have another shape;
- 80 have no reflected member at the offset;
- 20 have no reflected struct member there, and 19 no reflected bitfield at the bit;
- 18 guarded getters go through a pointer or to a member that is not reflected;
- 14 have no recovered signature;
- 18 share a folded thunk;
- 8 disagree with the member's type or the signature.

Two more are skipped because the member is not in the owner's own bytes.

The 206 natives are:
- 140 scalar getters and setters;
- 37 bitfield getters and setters;
- 9 struct getters by value (`FVector`, `FVector2D`, `FLinearColor` and others);
- 6 struct out-parameter getters (`FMargin` and others);
- 4 `TEnumAsByte` getters;
- 6 comparisons;
- 4 null-guarded getters.

Getters of members that are not reflected are left out on purpose: only the getter's own
instruction would place the member, so its match would prove nothing beyond itself.

One bitfield getter compiles to `shr eax, 4; and al, 1` where the others mask `eax`. With
v140, `return b;`, `!= 0`, `!!b` and `(bool)b` all mask `eax` for a uint32 unit. Only
`return b ? true : false;` masks `al`, so that form is generated where the reference shows
it (`AFortWeaponRanged::UseFirstPersonTargeting`).

Reconstruction:
- The 166 members and 35 bitfield members are declared at their reflected offsets in
  `Classes.gen.h`. A bitfield unit names its reflected bits and leaves the others unnamed
  (`uint32 : 1;`). The rest of each class stays opaque.
- The natives are defined out of line, one translation unit per package
  (`Source/Generated/Natives/<Package>.natives.cpp`). The reference compiles them in the
  class's own `.cpp`, apart from the generated code, so its thunks call them rather than
  inline them.
- The thunks are UHT 4.20's `DECLARE_FUNCTION` bodies, as for virtual natives.
- The manifest symbol is the MSVC decoration of the native's signature: bool, the sized
  integers, float, double, class pointers, enums, and structs the shims define with `struct`
  (by value `U`, by reference `AEAU`/`AEBU`), and the class templates `TEnumAsByte` and
  `TSubclassOf`. A template-id `?$Name@<args>@` encodes its arguments with a fresh
  back-reference table (v140 probe). A returned enum, struct or template carries the `?A`
  prefix.

All 206 natives are exact, outside the denominator (leaf). Each thunk's call then resolves
through that exact match, and all 206 thunks are exact, in the denominator.

The larger `Classes.gen.h` moves MSVC's `$SG` literal numbering. InputCore.1's literal order
follows that numbering, so 2 of its registrars (`EControllerHand`, `FKey`) lose their
section-relative literal prediction. One class registrar in another unit gains one. This is
the known `.rdata` ripple (STATUS, "Known fragility"). `tools/matching/regressions.py`
reports both. With the second accessor batch the numbering moved again, and both are exact
once more.

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
| `FuncParams` (a static local, see "Data layout") | content: the only `FFunctionParams` record in `.data` whose `NameUTF8` names the function. Where the name is shared, the only one also matching the class's `OuterFunc`. That is the consensus outer of the class's uniquely named records (1,588 creators), or, for a class without one, the `Z_Construct_UClass_<Class>` its `FCompiledInDefer` initializer registers (446 creators). Where the name was unique (9,063 creators), the record agreed with each creator's `lea` in every case |
| `ConstructUFunction` | corroborated by the other creators |
| `ReturnFunction` (3 fields) | section-relative to sibling creators' observed slots. Each static local gets its own COMDAT `.bss` section, which the linker places in object order |

Ordering was established from the reference. A class's delegate signatures come first,
in header order (their creators' code addresses preserve it). Its functions follow,
sorted by name, which is also the `FClassFunctionLinkInfo` order. Some classes have
unreconstructed statics between the two blocks, which the majority rule tolerates.

Results:

| Count | State |
| --- | --- |
| 10,976 | exact against the decrypted image, 442 of them with the record identified through the class constructor (see above) |
| 121 | relocation-equivalent: only the `ReturnFunction` static in `.bss` is not predicted (a class with a single creator has no sibling to predict it from, or the slot sits across a layout gap) |

### Data layout: the `TClassCompiledInDefer` block and the parameter records

In the reference, a unit's `TClassCompiledInDefer` objects (`AutoInitialize<Class>`) form one
block, 0x28 bytes apart, ahead of its `FFunctionParams` and `FStructParams` records:
- 121 of 166 units have a single such run;
- the others split into a few runs, with blocks of records between them.

The 4.20 release's `_Statics` form, a file-scope member per record, compiles them interleaved
in source order. Our build did that, so only the `AutoInitialize` objects that happened to be
adjacent could be predicted.

v140 probes show the cause:
- A record whose initializer is not a constant expression is statically initialized in
  `.data`. The `(UObject*(*)())` cast and `EObjectFlags`' non-constexpr `operator|` make it so.
- As a file-scope object, such a record is emitted in the main `.data` in source order,
  between the `TClassCompiledInDefer` objects.
- As a static local of the creator, it gets a section of its own after the main `.data`.
  The main `.data` then holds only the `TClassCompiledInDefer` objects, in one block.
- The creator's 47 bytes are the same either way.

So the reference's generated code has `FuncParams` and `ReturnStructParams` as static locals
of their creators. That is the form before the 4.20 release; the enum creators' `EnumParams`
already were. With `Engine.22` rewritten this way, all 90 `.data` symbols that have reference
addresses come out in the reference's order, with no inversion.

The generators (`uht_creators.py`, `uht_packages.py`, `uht_structs.py`) now emit that form:
- `static const FFunctionParams FuncParams = {...};` in the creator's `if` block, and
  `ReturnStructParams` likewise.
- The evidence keys are the static locals' decorated names
  (`?FuncParams@?4??<Creator>@@YAPEAVUFunction@@XZ@4...`).
- `PropPointers` stays a declared `_Statics` member until properties are recovered.
- All 11,097 function records are defined, including the 446 identified through the class
  constructor.

Results:
- 3,103 of 3,283 `AutoInitialize` initializers (outside the denominator) are exact, up from
  1,248 before this model.
- 4 more were lost, in units with several runs (`FortniteGame.20` has 5); see below.
- Moving the records' name literals changes the `.rdata` string order of `Engine.26`.
  `AVolume`'s class registrar loses its section-relative package-literal prediction (the known
  ripple).

`ClassParams` (constant-initialized, in `.rdata`) is still a `_Statics` member.

**Units that span several objects.** A unit is cut at a vector-constant marker or a package
change (`tools/analysis/unity_order.py`). A unity file that uses no header vector constant
has no marker, so it was merged with the unit before it.

Such a unit shows several `TClassCompiledInDefer` runs, but so does one object whose data was
emitted in more than one batch. The string literals tell them apart: an object's literals
fill its own main `.rdata`.
- In `FortniteGame` unit 54 and `Engine` unit 129, each run's class-name literals occupy
  their own increasing range.
- In units 52 and 68 the runs' literals interleave: one object.

`split_objects` cuts a unit only when both measures agree:
- each run's classes are contiguous in `.CRT$XCU` order;
- their literal ranges are disjoint and increasing.

An item between two objects' classes goes with the object whose literal range holds its own
name literal; if neither holds it, the unit is not cut.

Of 47 units with several runs:
- 22 are cut into 64 objects;
- 22 stay whole (one object, literals interleave);
- 3 stay whole (an item between objects is not placed).

There are now 224 units, up from 182. The new objects have no vector constants, which is why
they had no marker. The cut makes 105 relocation-equivalent functions exact, adds 12 newly
located `StaticStruct`s, and causes no regressions:
- 17 class constructors, 12 struct and 11 class registrars, 12 struct-ops initializers;
- 8 creators and 14 `StaticStruct`s;
- 40 `AutoInitialize` initializers, outside the denominator.

The other 22 multi-run units are single objects. Why their data comes in several runs is not
modelled.

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

**Literal copies: 8-byte alignment (2026-11-24).** 147 struct functions waited on their name
literal. A struct's `TEXT("<S>")` typically has four copies in the reference:
- the `StaticStruct`'s;
- the `FCompiledInDeferStruct` initializer's;
- the pooled `??_C@` copy of the `StaticRegisterNatives` initializer's `FName`;
- a match inside a longer wide string, such as `L"AnimationState"` at the end of
  `L"BakedAnimationState"`.

The last passed the old test (preceded by a zero byte, 2-byte aligned) because a wide
character's high byte is zero. So two copies were left free and elimination declined.

MSVC places every string literal of 8 bytes or more on an 8-byte boundary:
- 3,244 of 3,244 such `$SG` literals in our objects;
- 22,943 of 22,946 `$SG` addresses observed in the reference. The other 3 are not string
  literals.

The tails of longer strings sit at other offsets. So `literal_hits` now requires 8-byte
alignment for such literals, and character-width alignment only for shorter ones.

Offline, all 29,633 literal relocations of exact entries still resolved to their observed
addresses, and 130 more entries resolved completely. The comparer made them exact, with no regressions:
- 42 `StaticStruct`s;
- 44 `FCompiledInDeferStruct` initializers;
- 44 `StaticRegisterNatives` initializers.

25 functions still wait on a literal with two or more plausible copies left:
- 9 `StaticRegisterNatives` on pooled literals;
- 8 `StaticStruct`s and struct registrations;
- 3 class registrations;
- 2 enum functions;
- 3 hand-reconstructed `FCommandLine` functions.

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

**Two blocks.** MSVC emits the statics of file-static functions first, as a block at the
start of each unity translation unit's `.bss`, where all `StaticEnum` singletons sit. Each
`ReturnEnum` sits elsewhere, in its header's COMDAT sequence, e.g.
`[ReturnEnum][creators…][OuterClass][PrivateStaticClass]`. The two slots are never
neighbours, unlike `Singleton`/`ReturnStruct` for structs.

**Order within the block.** 179 units hold two or more `StaticEnum`s:
- In the reference, the singletons of 139 of them follow the recovered source order.
- In the other 40 they are mostly rotated: the last ones first, or the first ones last.
- The block spans the whole original unity file, so runs can interleave. In `AIModule.1`,
  the singleton of `EAIOptionFlag`, the last enum of one run, sits between the first two of
  the next run. That is also what fills the 8- and 16-byte gaps in 42 units whose order is
  the source order.
- The `StaticEnum` code follows neither order: in all 179 units it is sorted by decorated
  name.

The order MSVC gives file-static functions here looks like a symbol index taken modulo a
table size:
- a rotation of the source order where the indices wrap once;
- several interleaved ascending runs where they wrap more than once (`Engine.9` in the
  reference).

This is a hypothesis about MSVC's internals, not verified. What was observed: in
`Paper2D.1`, file-static `StaticEnum`s come out as `[4,5,6,0,1,2,3]`. With 8 unused
declarations before them, they come out as `[3,4,5,6,0,1,2]`. Declaring them first in source
order doesn't change that. `inline` functions are deferred the same way.

**Slot elimination.** The order within the block is MSVC's and is not reproduced. Its
extent is: a unit's singletons fill one contiguous run of 8-byte slots. That holds in 128 of
the 137 units with two or more `StaticEnum`s; the other 9 have wide gaps.
- `uht_enums.py` writes each unit's singleton symbols, from the unity order, to
  `analysis/uht-bss-blocks.json`.
- When the section-relative prediction declines, `compare.py` resolves a singleton as the
  one slot its block-mates leave. Each of the other singletons must be observed exactly
  once, by entries other than the one under test.
- The slot is the single gap between them. When they are contiguous, it is the end slot whose
  outer neighbour is not already observed holding another symbol.
- Anything else (a wider gap, two gaps, both ends free) resolves nothing. The byte comparison
  checks every prediction.

This made 279 `StaticEnum`s exact, 653 of 1,089 in all, with no regressions.

**Lower end after another unit's `.bss`.** When the other members are contiguous and both end
slots are free, the block's start decides. A unit's block opens its object's `.bss`. In 97 of
137 units the slot just below it holds another unit's `PrivateStaticClass`, the last static of
that object. `compare.py` takes the lower end when, by other entries' observations:
- the slot below the lower candidate holds exactly one symbol;
- that symbol is a `PrivateStaticClass`;
- it is the last `.bss` static of its own object (the object of its `GetPrivateStaticClass`
  entry, in our layout);
- that object belongs to another unit.

An offline simulation gave 44 right and none wrong. Two weaker variants were rejected:
- any static of another object below the block: 2 wrong;
- the last static of its object of any kind: 1 wrong. After a `ReturnStruct` the reference
  can leave an 8-byte hole.

Two structural guesses failed outright: the block start is not 16-byte aligned (62 of 128
contiguous blocks are), and the unit's plain `.bss` alignment does not predict it either.

**Slot elimination first, and clusters (2026-11-24).** Two things left 286 singletons open.

- *The order of evidence.* The section-relative prediction ran first. Inside a block it
  follows our source order, which MSVC rotates in 40 of 179 units. There its wrong prediction
  came before slot elimination, so 103 singletons stayed open although they sat in the only
  gap of their block. Slot elimination now runs first for block members, and section-relative
  is the fallback. Against the last run's observations, slot elimination decides 781 of the
  795 exact singletons and agrees with all of them.
- *Clusters.* In 9 units the singletons sit in two to four places, 900 to 3,700 bytes apart.
  Each run (the `.s<k>` object of consecutive enums, numbered in source order) lies in one
  place. The places hold ascending ranges of runs, in all 9 units. Example, `FortniteUI.6`:
  - runs 1 and 2 open the unit's `.bss`;
  - runs 3 to 5 sit between `UFortGridPickerButton`'s `PrivateStaticClass` and
    `UFortGridPickerGrid`'s `OuterClass`.

  Whether these are separate original objects is not known.

`_slot_elimination` now works like this:
1. A single one-slot gap among the other members, which no other symbol is observed holding,
   is the symbol's slot, in whichever cluster. Members more than one slot apart start a new
   cluster.
2. Otherwise the symbol's cluster is the one holding its own run's other members, or the one
   holding the runs on both sides (both clusters if they differ). That needs every run in one
   cluster and the clusters in run order. Of those clusters' end slots no other symbol holds:
   - the lower end directly above an observed `PrivateStaticClass` is taken. A class's statics
     end with it, and a cluster above one starts directly after it: 76 of 76 measured,
     including 5 later clusters. This replaces the rule that required another unit's closing
     `PrivateStaticClass`;
   - otherwise the only one.
3. Two gaps, runs out of order, or two or more candidates resolve nothing.

Below other kinds of static both ends occur: after a `ReturnStruct`, 5 lower and 1 upper.

The real `_slot_elimination`, run offline on the dumped observations, settled 219 of the open
singletons and got none wrong. The comparer made 213 `StaticEnum`s exact (795 to 1,008), with
no regressions. The other 6 also wait on another relocation.

Of the 81 `StaticEnum`s still not exact:
- 47 have both block ends free, with no `PrivateStaticClass` observed below;
- 5 have a run outside the observed runs of a unit with several clusters;
- 23 are a unit's only `StaticEnum`;
- 6 also wait on another relocation.

What follows a block is not modelled. After a fully observed block, the next observed slot
follows directly in 42 blocks (34 times a generated static, 8 times a vector constant). In the
others it lies 8 bytes or more further on. In our objects the unit's 1-byte registration objects
(`FCompiledInDefer*`, struct `StaticRegisterNatives`) open the plain `.bss` in MSVC's own order,
with the vector constants among them.

**Vector-constant initializers.** Each unit's `GlobalVectorConstants` are written by leaf
initializers that open its `.CRT$XCU` range. `unity_order.py` records their addresses next
to the constants' names, and `unity.py` lists them in
`analysis/functions-vector-constants.json` (outside the denominator). This was meant to pin
the far end of singleton blocks.
- In the reference, the first constant lies 8 to 88 bytes after the block; it is adjacent in
  only 5 units. So the constants decide few block ends: one more `StaticEnum` (654).
- 136 of the 414 initializers are exact. The rest wait on their slot.
- A unit's constants sit in its plain `.bss`, after `UnityPrologue.h`. That stand-in is not
  the size of the engine headers' statics, so the constants' offsets to the unit's other
  statics are not modelled. They predict only each other's slots.
- Used as neighbours of `OuterClass`/`ReturnFunction` statics, they cost 10 class
  constructors and the registrars and creators depending on them. Their observations still
  count as occupied slots for slot elimination.

Of the `StaticEnum`s not exact:
- 267 are blocked only at an end of their block, with both outer neighbours unobserved;
- 125 wait on a literal copy;
- 23 are a unit's only `StaticEnum`.

**Layout used.** `StaticEnum` is generated with external linkage. Each unit defines its
`StaticEnum` functions first, in source order, before the prologue:
- `Enums/<Pkg>/<E>.staticenum.gen.cpp`: the function. The code is the same; only its
  linkage deviates from UHT.
- `Enums/<Pkg>/<E>.defer.gen.cpp`: the `FCompiledInDeferEnum` object, at the enum's place.

External functions and their statics are emitted in definition order. So the block keeps its
place before the plain `.bss`, and its order is the source order whatever else the unit
contains; `tools/matching/selftest.py` checks both on a small probe. The order comes only from
`.CRT$XCU` (the unity order). The reference's `Singleton` addresses are never used to
arrange it: they are the fields being checked.

The cost is in `.rdata`. String literals are emitted in parse order. In the reference, each
`StaticEnum`'s `TEXT("<E>")` directly precedes the registration object's copy, as UHT's
in-place, file-static definition gives. Defined at the top, the `StaticEnum` literals form
a block of their own. Literal elimination still resolves most of them, so 5 fewer
`StaticEnum` literals resolve than before (128 unresolved, against 123).

Against the earlier layout this is 19 exact functions fewer (28,262 to 28,243):
- in the `<unit>.s<k>` units the source order breaks even (315 to 314). There, the earlier
  compiler order matched some rotated reference blocks by chance and missed others;
- the main units lose 7 `StaticEnum`s, and one `StaticStruct` and one struct registration
  initializer each lose a literal neighbour;
- 9 registration initializers follow their `StaticEnum`.

Every alternative tried gives up one of the two:
- external functions defined in place: their singletons follow the plain `.bss`, between
  the registration objects;
- function and registration object kept together at the top: the first registration
  object opens the plain `.bss` between the singletons;
- `inline` functions: the same rotations, and literals no longer in parse order.

**Source order from `.data`.** UHT parameter records (`FEnumParams`, `FStructParams`,
`FFunctionParams`) are emitted to `.data` in definition order. For 967 of 1,094 enums, the
item whose record follows the enum's record also owns the next COMDAT `.bss` slot. This
statistic only supported the design and is never used as evidence. The generator groups
enums whose records are consecutive, with no other UHT record between, into runs, and never
reads a `.bss` address to do so.

Each run gets two translation units that reproduce the two blocks:
- the constructors (`<E>.gen.cpp`), whose `ReturnEnum`s anchor each other;
- the `StaticEnum` functions and registration objects (`<E>.staticenum.gen.cpp`,
  `<E>.defer.gen.cpp`), whose `Singleton`s anchor each other.

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
- 373 `StaticEnum`s are exact. Others lack a `Singleton` neighbour (a single enum, or the
  reference block departs from source order), an exact constructor, or a unique literal.
- The 824 registration initializers are relocation-equivalent, because of the package-name
  literal.

Enumerator values are emitted as the integers stored in the reference. The C++ enum
declarations, including their underlying types, are not recovered.

## Module layout model (`tools/analysis/unity_order.py`)

UBT compiles a module's generated code as unity files (`Module.<Name>.gen.N.cpp`) that
include the `.gen.cpp` files one after another. The `.bss` slots of every UHT singleton
follow that order. Rebuilding it lets every item be compiled next to its true neighbours.

**Source of the order.** MSVC records a translation unit's dynamic initializers in
`.CRT$XCU` in definition order, and the linker concatenates the units' arrays. The
reference's table (28,355 entries at `0x02E29A40`) therefore lists every UHT registration
object in source order:

| Item | Initializers |
| --- | --- |
| class | the leaf `TClassCompiledInDefer` initializer (CRC, `TEXT("C")`, `sizeof`), then the 58-byte `FCompiledInDefer` one (`Z_Construct_UClass_C`, `C::StaticClass`) |
| struct | `FCompiledInDeferStruct` (66 bytes), then `StaticRegisterNatives` (92 bytes) |
| enum | `FCompiledInDeferEnum` (66 bytes) |

Units are delimited as follows:
- Each unity file opens with the leaf initializer of a header constant (`movaps` from
  `0x02E624F0`; 299 occurrences).
- Because a unity file never spans two modules, a package change also starts a unit. Some
  small plugin modules' units lack that header.

The table yields 161 units holding all 3,333 classes, 2,110 structs (all but the 66
noexport ones) and 1,094 enums. No `.bss` address is read.

**Check (diagnostic, not evidence).** The model expands each item into predicted COMDAT
`.bss` slots: enum `ReturnEnum`; struct `Singleton`, `ReturnStruct`; class creators,
`OuterClass`, `PrivateStaticClass`. Of 22,976 consecutive predicted pairs with known
reference addresses, 22,296 (97 %) are adjacent. The 680 gaps sit at unit boundaries and
at items not yet modelled, such as package-scope delegates.

### Building the units

**Class declarations (`tools/codegen/uht_classes.py`).** `IMPLEMENT_CLASS` passes everything
`DECLARE_CLASS` defines to `GetPrivateStaticClassBody`. The decoder follows each class's
`GetPrivateStaticClass` instruction stream to that call, reached through the `StaticClass`
thunk that its `FCompiledInDefer` initializer names. It checks the common 151- and 162-byte
forms against byte templates, and decodes 3,326 of 3,333 classes. The other seven are
CoreUObject intrinsics that construct their `UClass` directly.

The decoded values give:
- the class hierarchy: every superclass resolves to a known class;
- the declaration values: flags, cast flags, package, config name and `sizeof`, which
  agrees with the `TClassCompiledInDefer` value for all 3,283 classes that have one;
- `AddReferencedObjects` ownership: a class declares its own where its pointer differs from
  its superclass's.

`Generated/UHT/Classes.gen.h` declares every class this way, superclasses first, with real
inheritance and an opaque member that only fixes `sizeof`. Each class fragment then holds
the `IMPLEMENT_CLASS` body, plus `Z_Construct_UClass_*` for the 2,045 classes without
UFunctions. Their `ClassParams` is the only `FClassParams`-shaped record naming the class's
`StaticClass`. The `StaticClass` address also appears in property metadata, because
`/OPT:ICF` folded `Z_Construct_UClass_<C>_NoRegister` into it; the record-shape checks
exclude those.

**Units (`tools/codegen/unity.py`).** One file per recovered unit `#include`s the items'
fragments in table order. Only these files are compiled, and manifest objects are the unity
objects. Three modelling points:
- **Prologue.** The original units begin with engine headers whose namespace-scope objects
  create the plain `.bss` section ahead of all COMDAT statics. `UnityPrologue.h` stands in for
  them. Without it, the first struct's registration objects would put that section in the
  middle of the COMDAT sequence.
- **`StaticEnum`.** MSVC places file-static functions' statics in a block of their own.
  Consecutive enums are adjacent in it. Each run of consecutive enums' `StaticEnum`
  functions is therefore compiled as a unit of its own (`<unit>.s<k>`). Every unit defines
  its `StaticEnum`s first, before the prologue, in source order, with external linkage.
  UHT makes them file-static, and MSVC's order for those is unstable.
- **Per-unit vector constants.** The engine headers define `GlobalVectorConstants`
  (`UnrealMathVectorConstants.h`) in every original unity file. The reference keeps only those
  a unit uses, and their leaf initializers open the unit's `.CRT$XCU` entries: `FloatOne`
  (the unit marker), then the rest in header order. `FloatZero`'s loads nothing (`xorps xmm0,
  xmm0; movaps [slot], xmm0; ret`). `unity_order.py` records them, by value,
  for each of the 131 units that open at a marker. `unity.py` defines exactly those, with the
  header's definitions, after the `StaticEnum` functions (`VectorRecovered.h` for the
  helpers).
  - Most common sets: `FloatOne, XYZMask` (67 units), plus `SignMask, Float360, Float180`
    (22), plus `Float360, Float180` (14).
  - Units that continue an original unity file, `<unit>.s<k>` units and package units define
    none.
  - Two values are ambiguous. `{1,1,1,1}` is also `RotationSignificantThreshold` (defined
    last), but header order fixes it as `FloatOne` wherever something follows. `SignMask`'s
    bits are also `IntSignMask`'s (same form, `movdqa`), and the first-defined name is taken.
  - Against the same two constants in every unit, the count is level: `EConstraintType`'s
    `StaticEnum` (with its registration) resolves and `ETwoPlayerSplitScreenType`'s no
    longer does. `EngineSettings.1` has no constants in the reference, and its match had
    depended on the 32 bytes every unit used to get.

**Package-scope delegates (`tools/codegen/uht_packages.py`).** UHT emits a header's
package-scope delegates first, before its enums, structs and classes. They have no
`.CRT$XCU` entry. Each package's `SingletonFuncArray` lists them, together with class-scope
delegates and noexport structs, and those whose `OuterFunc` is the package are package-scope
(632). `unity_order.py` places each one between the namespace-scope `.data` records around
it (`FFunctionParams`, `FStructParams`). `EnumParams` is function-local, so it is no anchor:
- if an enum lies between the anchors, the delegate goes right before it;
- if classes without UFunctions lie between, `FClassParams` and the delegate's
  `PropPointers` (both `.rdata` definitions) order them.

**Package singletons and `init.gen.cpp`.** Each package constructor is generated from its
`FPackageParams` and `SingletonFuncArray`. `PackageParams` is resolved by content, as the
only `FPackageParams`-shaped record naming the package. Its position comes from the code:
- A `StaticStruct`/`StaticEnum` compiled where the package constructor is defined inlines it
  (587 structs, 270 enums); one in another translation unit calls it.
- MSVC inlines a function defined later in the same unit too. The first build of this model
  inlined it into 21 Engine structs that the reference shows calling it. So
  `init.gen.cpp` opens a unity file of its own, and no calling item shares its unit.
- UBT orders a unity file's `.gen.cpp` files alphabetically, so `init.gen.cpp` sits between
  the last calling and the first inlining item. Inside that window the alphabetical rule
  places it, and the unit is split there (23 splits).

The position is recovered for 68 modules. Two are inconsistent, and in 16 no item inlines.
Their package constructors are compiled alone.

**Results against per-item units.** After these additions:

| Category | Per-item units | Unity units |
| --- | --- | --- |
| Class constructors | 1,034 | 3,227 |
| UFunction creators, including 551 package-scope delegates | 10,556 | 11,085 |
| Struct constructors | 1,514 | 2,097 |
| `StaticStruct` | 1,426 | 1,859 |
| `NewStructOps` | 1,294 | 1,782 |
| Struct-ops registrars | 1,427 | 1,888 |
| Enum constructors | 726 | 1,071 |
| `StaticEnum` | 301 | 370 |
| Package constructors | — | 68 |

63 entries that were exact in per-item units are not, mostly next to the remaining
unmodelled items: creators of function tables not attributed to a class, and the 7
intrinsic classes. One enum registration initializer is `partial`. Its name literal shares a
copy with another use in this build, so literal elimination predicted the wrong copy, and
the byte comparison reports it.

**Registration initializers.** Each class fragment also holds `IMPLEMENT_CLASS`'s
`TClassCompiledInDefer<C> AutoInitialize<C>` and UHT's `FCompiledInDefer` object, as the
initializer table lists them. Their initializers compile to the reference shapes:
- the 58-byte `FCompiledInDefer` one, in the denominator;
- the 31-byte leaf `AutoInitialize` one, outside it.

The `AutoInitialize` object is statically initialized in `.data`. Its initializer only
tail-calls `UClassCompiledInDefer`.

Every registration initializer (class, struct, enum) passes `TEXT("/Script/<Package>")`, one
copy per use. Every `GetPrivateStaticClass` shares one more, pooled through the inline
`StaticPackage()`. For 67 of 86 packages, the copies number exactly the registration objects
plus that pooled copy. Once every registrar of a package is reconstructed, elimination
assigns each its copy. Enum registrars are therefore taken from the initializer table for
all 1,094 enums, whatever form their `StaticEnum` takes; a missing one blocked a whole
package.

Results:
- class registrars: 2,211 of 3,283 exact;
- struct registrars: 1,283 of 2,110;
- enum registrars: 598 of 1,094;
- class auto-initializers (outside the denominator): 3,103 of 3,283 (see "Data layout").

**Registered function addresses.** A registrar passes `&C::StaticClass`,
`<E>_StaticEnum` or `F<S>::StaticStruct`. Where nothing else refers to that function, the
registrar itself was the only witness of its address. That is the case for a leaf class's
`StaticClass`, or a `StaticEnum` that is not exact. The address is circular evidence for that
same registrar, so the relocation stayed unresolved. Each is now located without the
registrar, from a function identified by its own content:

| Symbol | Evidence (`analysis/uht-*-symbols.json` code) | Located |
| --- | --- | --- |
| `C::StaticClass` | the only 5-byte `jmp`, at a 16-byte slot outside `.pdata`, to `C`'s `GetPrivateStaticClass`, which is identified by its `TEXT("C")` (`static-class-jmp`) | 3,303 of 3,333 (23 not unique, 7 bodies not decoded) |
| `<E>_StaticEnum` | the only primary function that loads `Z_Construct_UEnum_<E>` (named by its `FEnumParams`) into `rcx` just before calling `GetStaticEnum` (`static-enum-call`) | 1,088 of 1,094 |
| `F<S>::StaticStruct` | the only function (chained fragments count as their primary) that loads `Z_Construct_UScriptStruct_F<S>` (named by its `FStructParams`) into `rcx`, with no call in between, before calling `GetStaticStruct` (`static-struct-call`) | 2,102 of 2,110 |

- `/OPT:ICF` folds identical functions, such as `Z_Construct_UClass_C_NoRegister` into the
  `StaticClass` thunk, so a second candidate means a different function. The class is then
  dropped, not guessed.
- Every located address agrees with the one the registrar names. That comparison is a check
  only, not the evidence.
- This made 1,022 class, 355 enum and 31 struct registrars exact, with no other state change.

**Package-name literal copies.** In Engine (7 extra copies), CoreUObject (4), MovieScene and
others, hand-written code uses `TEXT("/Script/<Package>")` too. Literal elimination
therefore found two or more free copies for 2,329 registrars. The claims above settle them:
- Hand-written code references most extra copies with a single `lea`.
- Four Engine copies have no reference at all: dead per-use literals that stay in their
  object's `.rdata` after `/OPT:REF` drops the code that used them. They sit with that
  object's `OnTimeline*__DelegateSignature` literals. Other units' observed literals lie
  between them and every registrar's own block.
- An earlier rule also counted `lea` sites inside the function under test. It claimed that
  function's own copy and made 270 predictions wrong. Masking the function's range, and
  ignoring copies referenced from several places, removed every one of them.

This made 2,685 functions exact (2,655 in the denominator), with no regressions:
- 1,017 class, 488 enum and 767 struct registrars;
- 131 `StaticStruct`, 94 `StaticEnum` and 157 struct `StaticRegisterNatives`;
- 30 `AutoInitialize` initializers.

What remains:
- 157 functions wait on string literals: 53 struct `StaticRegisterNatives` on pooled
  `??_C@` literals, and about 100 more on `$SG` copies (`analysis/match-queue.json`).
- 180 `AutoInitialize` objects are not predicted, mostly in units that span several of the
  reference's objects (see "Data layout").

### `GetPrivateStaticClass` fields

`GetPrivateStaticClassBody` receives three functions that nothing else references. Each needs
its own evidence.

**`InternalVTableHelperCtorCaller<C>`.** Without `WITH_HOT_RELOAD` it returns `nullptr`, so
ICF folds every instance into one function (`33 C0 C3`, RVA 0x0032B970 for 3,282 classes).
- `UHTRecovered.h` now defines the template, and every unit emits the 3-byte COMDAT.
- The ICF-folded body evidence resolves each instance from the other classes' observations.
- `UObject` passes a different function and is declared as an explicit specialization.

**Empty `StaticRegisterNatives`.** v140 compiles an empty function to `ret 0` (`C2 00 00`),
the bytes of the shared copy at RVA 0x01ABAAB0. The same evidence applies, but only where the
empty body is right: an observation of a class whose real function registers natives would
conflict.
- `uht_classes.py` now emits the empty body only for classes whose unique `FClassParams`
  has no function table, or whose UFunctions all lack `FUNC_Native`. It reads
  `FunctionFlags` (`+0x20`) from each creator's `FFunctionParams` record
  (`uht-creator-symbols.json`).
- 31 classes have native UFunctions whose table is not located. Their function stays
  declared only.

**`InternalConstructor<C>`.** It runs `new((EInternal*)X.GetObj())C(X)`
(DEFINE_DEFAULT_OBJECT_INITIALIZER_CONSTRUCTOR_CALL) or `...C` (the default-constructor
form). The reference compiles these to a 20-byte and a 13-byte conditional tail call of the
constructor:
- 2,866 classes use the first form and 133 the second;
- in 327 the constructor is inlined, so the instance is declared only.

`Classes.gen.h` declares each class's constructor and `__DefaultConstructor`. `UHTRecovered.h`
adds a minimal `FObjectInitializer` (its first member is `Obj`) and the placement `operator
new`. All 2,994 compiled instances equal the reference outside the constructor relocation.

The address comes from the code layout, as data does from the data layout. Two layouts were
compared:
- In general the two compilers emit a unit's functions in different orders. Only 8,004 of
  22,970 consecutive exact pairs have the reference spacing.
- Template instances are emitted in first use order in both builds, which is the order of the
  object's `GetPrivateStaticClass` sections (all 224 units). Consecutive instances have the
  reference spacing in 2,253 of 2,799 pairs.

`compare.py` predicts an instance from its unit's run: one member per
`GetPrivateStaticClass`, in section order. Every member's address comes from other entries'
observations (each class's own body observes its instance):
- A member's slot is its compiled size. An instance declared only (an inlined constructor) is
  still a member; its slot is the extent of the reference function at its observed address.
  These were most of the gaps between compiled instances: one `.pdata` function of 41 or 47
  bytes.
- A member is folded when another instance is observed at its address (ICF folds identical
  constructors' instances into one copy). Its slot here is occupied only if that address is
  exactly where the walk has arrived.
- Each side walks from its nearest unfolded member to the instance. With both sides, the
  predictions must agree. With one side only (a run end, or the other side blocked), the
  reference at the prediction must hold this instance's compiled body outside its relocation,
  and no other symbol may be observed there.

The first version used only adjacent compiled instances, needed both sides and declined at a
folded neighbour.
- Without the folded-neighbour rule, 4 of 1,899 predictions were wrong. Twice the sides
  agreed on a slot that belonged to a folded instance, and once a vanished slot on one side
  cancelled an extra function on the other. The byte comparison reported each as `partial`.
- Ordering the run by unity class order instead was wrong 20 times. That order differs from
  the object's in 114 units.

An offline simulation over all classes gave 2,735 correct predictions and none wrong with the
rules above:
- 2,289 two-sided;
- 294 one-sided;
- 152 for declared-only instances.
The first version gave 1,833.

This made 2,621 `GetPrivateStaticClass` bodies exact, and 33 more `StaticClass` thunks that
jump to them, with no regressions. Of the 662 bodies left:
- 519 wait only on `InternalConstructor<C>`: the walk is blocked (an unobserved or unsized
  member, sides that disagree), or one side's shape or free-slot check fails;
- 63 wait only on `PrivateStaticClass`, 23 on `AddReferencedObjects`, and the rest on
  several fields or a `StaticRegisterNatives` with natives.

**Interleaved runs and inlined constructors (2026-11-24).** 540 bodies were left that wait
only on `InternalConstructor<C>`. In the reference, 374 of these instances sit at an address
where another class's instance is also observed. ICF merged them because the two constructors
are identical: the same superclass constructor call and the same vtable. The constructor
behind RVA 0x00544ED0 stores one vtable for all its classes, so their vtables were folded too.
Nothing independent of the field under test says which classes these are:
- `analysis/vtables.json` was derived through `InternalConstructor<C>` itself;
- grouping by superclass and form gets the fold address wrong 27 times. For example, 84
  `UInterface` children fold to RVA 0x00544ED0 and 4 fold elsewhere;
- taking a subclass's constructor's first call as the superclass constructor is right 5
  times and wrong 17 times.

These stay open. Two changes help the 166 unfolded instances:
- *Interleaved runs.* In some units the reference run also holds instances from a
  neighbouring unit, one original object compiled here as two. Example:
  `OnlineSubsystemUtils.1`'s `UAchievementQueryCallbackProxy` … `UEndTurnCallbackProxy`
  sit between `.2`'s `ATestBeaconHost` and `UFindSessionsCallbackProxy`. The far side then
  predicts a slot where such an instance is observed. When the sides disagree and exactly one
  side's prediction is held by another symbol, that side is dropped, and the other is
  checked as a one-sided prediction.
  - Dropping a held side even when the two sides agree lost 32 exact matches. In those, both
    sides arrive at a folded neighbour's copy, which is right.
- *Declared-only instances* (inlined constructors) may now be one-sided. At the prediction,
  the reference must start a `.pdata` function whose prologue loads `X.GetObj()` from
  `[rcx]` and tests it for null, or hold a `jmp` to such a function (some instances are
  5-byte jumps). Without a left side, such an instance is sized by the reference function that ends,
  16-byte aligned, where the right walk arrived (only an end no other function shares).

Run offline on the dumped observations, the real `_internal_constructor_run` made 94 more
predictions, 88 of them for bodies waiting only on the instance. None was wrong, and all
2,684 exact bodies kept theirs. The comparer made 88 `GetPrivateStaticClass` bodies and 2
`StaticClass` thunks exact, with no regressions.

Of the 452 bodies still waiting only on `InternalConstructor<C>`:
- 374 are folded;
- 35 have no other member of their run observed unfolded;
- in 35 the sides disagree and neither prediction is held;
- in 8 a single side's prediction fails its body or shape check.

### `.bss` statics: creator order and rigid pairs

The remaining `.bss` statics were studied offline from `compare.py --dump-observations`: the
final leave-one-out observations, written as JSON. Usually one side of the section-relative
prediction was right and the other side wrong. The rule that compares runs of agreeing
neighbours then tied or chose the wrong side.

**Creator order.** A creator's `FFunctionParams` record (`.data`) and its `ReturnFunction`
static (`.bss`) are both function-local statics, emitted in definition order. In the reference
the records' order equals the statics' order in all 168 units with creators. The name order
matches in only 50 of them.
- The old order took class-scope delegate signatures by code address, then functions by name.
  The delegates are not in code-address order.
- `uht_creators.py` now emits each class's creators in record order. It reads only the
  `.data` record addresses, located by name; no `.bss` address. 19 classes changed order.

**Rigid pairs.** Over all consecutive layout items both observed, by kind:

| Pair (in our layout) | Same distance in the reference |
| --- | --- |
| `OuterClass<C>` then `PrivateStaticClass<C>` | 3,283 of 3,283 |
| last creator of C then `OuterClass<C>` | 1,238 of 1,238 |
| creator then creator, same class | 9,765 of 9,859 |
| `Singleton<S>` then `ReturnStruct<S>` | 2,064 of 2,089 |
| `StaticEnum` singleton then singleton | 352 of 629 |

The first two have a structural reason. `Z_Construct_UClass_C` directly precedes C's
`IMPLEMENT_CLASS`, and the class's creators directly precede its class constructor. When the
two sides disagree, a side whose neighbour is the symbol's rigid partner, directly next to it,
decides (`rigid_successor`). In simulation this was 126 right and none wrong.

The weaker pairs were rejected:
- Same-class creators as a tie-break: 90 wrong against 24 right on the unresolved fields. Those
  are exactly the creators whose order differs.
- The struct pair before the run rule: 22 right predictions lost against 20 gained.

**Results.** 253 functions became exact:
- 74 creators;
- 63 `GetPrivateStaticClass` bodies;
- 39 class constructors (all 2,045 function-less ones are exact now);
- 39 `StaticEnum`s;
- 38 class registration initializers.

That change cost 4 functions at first. `FInterpControlPoint` and `FFortPartySuggestion` lost
their constructor and, through it, their `StaticStruct`. In the reference, their classes'
delegate signatures come before the header's enum and struct statics; our class fragment
placed them after. Reordered, the delegates formed a 5-slot run that outvoted the struct's
2-slot run.

**Delegate placement.** UHT emits a header's delegate signatures before its enums and structs.
A class's delegate creators therefore belong either before items that precede the class in
the unit, or directly before the class.
- `uht_creators.py` writes them to a fragment of their own, `ClassDelegates/<Class>.gen.cpp`
  (54 classes). The class fragment keeps declarations.
- `unity.py` includes that fragment before the first item since the previous class whose
  parameter record follows the delegates' first record. Records are `FEnumParams`,
  `FStructParams`, or a function creator's or package delegate's `FFunctionParams`, located by
  name (`analysis/uht-*-symbols.json`). Otherwise the fragment goes directly before the class.
  Only `.data` addresses are read.
- Record order agrees with the reference's `.bss` in every classifiable case: 16 classes whose
  delegates precede their header's items are moved, and the 2 whose delegates follow them stay.

This made 42 more functions exact, with no regressions, and it recovered the 4 above:
- 19 creators;
- 7 enum constructors;
- 7 `StaticStruct`s;
- 5 struct constructors;
- 3 `StaticEnum`s;
- 1 package delegate.

**Record-bracketed slots.** 79 package-scope delegates still missed their `ReturnFunction`.
`unity_order.py` places them between their record-order anchors. Classes without UFunctions
lie in the same stretches, and nothing in the image orders the two:
- Their `FClassParams` is a function-local static. It comes after every delegate's
  `PropPointers` in all 1,091 measured pairs, so it says nothing.
- Name literals are emitted at code generation. Their order agrees with the `.bss` order no
  better than chance (897 of 1,698 pairs).
- Delegate properties and UFunction parameters of the classes do not link a delegate to its
  header.
- Putting such classes before the delegates would be right in 60 of 72 stretches, against 42
  now. But it would break some of the 7 stretches whose delegates belong to a following
  class's header.

So `compare.py` no longer depends on that order for creators. A creator's record and its static
are emitted together, so their orders agree (168 of 168 units). A creator's `ReturnFunction`
therefore lies strictly between the statics of the creators whose records directly precede and
follow its own in its object. Other entries observe those two statics and every other slot
between them. When exactly one 8-byte slot there is held by no observed symbol, it is this
creator's (`_record_bracket`).
- It runs where the section-relative prediction declines, before the tie-breaks.
- Records come from `uht-creator-symbols.json` and `uht-package-symbols.json`, located by
  name. No `.bss` address of the creator is read.
- In simulation it settled 82 of the 100 unresolved creator statics, none wrong. The rest sit
  at an end of their object's run or have two or more free slots.

This made 79 functions exact (66 package delegates, 13 creators), with no regressions.

**All three record kinds.** Enum constructors (`FEnumParams` and `ReturnEnum`) and struct
constructors (`FStructParams` and `ReturnStruct`) pair a record with a static the same way. One
order over all three kinds of record agrees with the `.bss` order of their statics in all 203
units. So the bracket now uses that merged order: a static's neighbours can be of any kind,
and the bracket is then tighter. In simulation this settled 20 more, none wrong:
- 9 enum constructors;
- 7 package delegates;
- 3 creators;
- 1 struct constructor.

The comparer made 23 functions exact, with no regressions. The 3 beyond the simulation are
`StaticEnum`s whose enum constructor became an exact call target.

What it cannot settle:
- a static at either end of its object's run of records;
- a bracket holding statics the model has none of. Examples are 2 unknown slots between a
  struct's `Singleton` and `ReturnStruct`, or a slot after a class's `PrivateStaticClass`.
  The bracket then has two or more free slots.

**Taken slots (2026-11-24).** Of the 25 `StaticStruct` singletons left, most were predicted,
but wrongly. For example, `FProfileUpdateNotification`:
- in our layout its `Singleton` follows `FMcpAddItemRequest`'s `ReturnStruct`;
- in the reference, the package's `ReturnPackage` sits between the two. So the left side
  predicted the `ReturnPackage`'s slot, which other entries observe;
- the longer run chose that side.

A `.bss` or `.data` slot cannot hold two statics (writable data is not folded). So in those
sections `compare.py` no longer predicts a slot that other entries observe holding another
symbol:
- a one-sided or agreed local prediction onto such a slot is dropped;
- when the sides disagree and exactly one lands on such a slot, the other decides.

Rerun offline over all 44,241 observed `.bss`/`.data` relocations, all 43,074 in exact entries
still resolved to their observed addresses. 57 relocations in other entries went from wrong or unresolved to
right. The comparer made 23 functions exact in the denominator, with no regressions:
- 8 `StaticEnum`s;
- 6 `StaticStruct`s;
- 4 package delegates;
- 2 creators;
- 2 struct constructors;
- 1 enum constructor.

Outside the denominator it made 34 vector-constant initializers and 1 `AutoInitialize`
initializer exact.

Two patterns hold most of the 21 `StaticStruct` singletons still open:
- *After the enum block.* 10 sit directly after their unit's `StaticEnum` singletons, away
  from their own `ReturnStruct`. Their `StaticStruct` functions are where name order puts
  them, and no other code references the singleton. Nothing found so far says which
  struct of a unit this is.
- *After `ReturnPackage`, before a gap.* Several follow their package's `ReturnPackage`,
  with one or two unknown slots before their `ReturnStruct`. `ReturnPackage` is not a rigid
  predecessor: of 30 struct singletons that follow it in our layout, 11 follow it in the
  reference.

**Package statics (2026-11-24).** 17 package constructors waited on their `ReturnPackage`.
Their `<Module>.init.gen.cpp` was never placed in a unit. `unity_order.py` places it by the
structs and enums that inline the package constructor. 16 of these modules have none, and
one has inconsistent forms. So each is compiled in a unit of its own, where its static has no
neighbours.

Three models of where the static lies were measured against the dump:
- *Name order.* `init.gen.cpp` sorted by name among the module's items. This fails: header
  names are not class names, and large modules have several unity files.
- *Code layout.* Package constructors sit at the end of their module's code, which says
  nothing about the source position.
- *`.rdata` record order.* `FPackageParams` and `FClassParams` are both constant UHT records
  in `.rdata`. In all 84 packages measured, `ReturnPackage` lies between the statics of the
  classes whose records directly precede and follow the package's record.

The record bracket is rarely tight. In 57 of the 84 it holds three or more free slots, and
no end is reliable: `ReturnPackage` follows the earlier class directly 29 times, precedes
the later class directly 21 times, and sits inside 34 times.

`_package_bracket` takes the slot only when exactly one is free between the earlier class's
`PrivateStaticClass` and the later class's `OuterClass`. That resolved 2 of the 17,
`FortniteGame` and `SocialDefaults`, with none wrong. The comparer made both exact, with no
regressions. The other 15 have two or more free slots.

## Naming confidence

`confirmed` needs direct evidence such as an exported symbol, reflection string or
debug data. Names inferred from engine source plus unique structural agreement are
`high-confidence inferred`. Shape-only agreement is `low-confidence inferred`.
