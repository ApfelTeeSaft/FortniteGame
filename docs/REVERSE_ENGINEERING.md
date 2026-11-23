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
    copy. All copies of the content are enumerated (fewer than 4,096). If every copy but one is
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
    linker places one object's contributions. Local first: on each side, the run of
    observed neighbours nearest the symbol that agree with each other gives a prediction.
    The prediction is used if the two sides agree, or if only one side has observed
    neighbours. A layout gap elsewhere in a large unit therefore cannot outvote the
    symbol's immediate neighbours. If the two sides disagree (a gap next to the symbol),
    each side's run of agreeing observed neighbours is counted, and the strictly longer run
    decides; equal runs resolve nothing. A prediction that then fails to reproduce the
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

## Reflection registration data (`tools/analysis/reflection.py`)

UHT-generated tables in plaintext `.rdata` name functions directly. The output is
`analysis/reflection-natives.json`, with names and RVAs only.

| Table | Layout | Found |
| --- | --- | --- |
| `FNameNativePtrPair[]` (per class, in `StaticRegisterNatives<Class>`) | {name, exec thunk} | 1,155 class arrays, 9,902 entries, 9,193 distinct exec thunks (some ICF-folded) |
| `FClassFunctionLinkInfo[]` (per class, in `FClassParams`) | {`Z_Construct_UFunction_*`, name} | 1,243 arrays, 11,102 entries |

The two layouts interleave the same pointer kinds, so a run read at the wrong 8-byte
alignment looks like the other table with one entry fewer. A run is kept only when it is
longer than every run of the other kind that overlaps its shifted reading.

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
loads `TEXT("<Class>") + 1`, i.e. a wide string + 2. This attributes 1,155 of 1,171 arrays.
No class, registrar or `GetPrivateStaticClass` is shared between attributions. In total
21,231 denominator functions now carry reflection-derived names. Names from these tables
count as `confirmed`; class attribution as `high-confidence inferred`. With the corrected
arrays, all 1,155 `StaticRegisterNatives<Class>` match exactly.

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
| direct natives named | 6,758, 6,654 high-confidence (5,104 in the denominator, 1,654 leaf) |
| virtual natives, located by vtable offset | 1,880 (429 of them through folded thunks) |
| unresolved (per UFunction) | 1,492: inlined or shared natives 821, flags unknown 396, folded thunk with a direct target 171, other call counts 68, no P_FINISH store 25, member call without Context 10, target already a generated function 1 |

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
| UFunction thunks defined | 1,759, at 1,507 addresses (132 bodies shared by folded UFunctions; one manifest entry each); 935 read parameters |
| of which call a native accessor (below) | 190, all exact |
| exact | 1,497: 1,287 in the denominator, 210 leaf (no `.pdata`) |
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
  that bit cleared and replaced by the argument's low bit.

Each form is accepted only when all of these agree:
- N is the offset of a reflected property of the native's class or a superclass.
  - A native bool is located through its `SetBit` function (`mov byte ptr [rcx+N], 1`).
  - A bitfield is located through its `or byte|dword ptr [rcx+N], mask`. That operand is the
    storage width, uint8 or uint32. `FBoolPropertyParams.ElementSize` is 1 for both.
- The property's C++ type is the UFunction's return type, its only parameter type, or its
  only out parameter's type.
- The copy covers exactly the struct's reflected size (`FStructParams`), or the instruction
  width fits the scalar type, or the bitfield's storage width is the access width.

The natives come from `analysis/native-implementations.json` (high-confidence, called
directly, by a thunk no other UFunction shares). Of 6,758, 192 qualify:
- 4,940 are not a short body ending in `ret`;
- 1,076 are not high-confidence direct natives;
- 399 have another shape;
- 71 have no reflected member at the offset;
- 20 have no reflected struct member there, and 19 no reflected bitfield at the bit;
- 20 have no recovered signature;
- 18 share a folded thunk;
- 3 disagree with the signature.

Two more are skipped because the member is not in the owner's own bytes.

The 190 natives are:
- 138 scalar getters and setters;
- 37 bitfield getters and setters;
- 9 struct getters by value (`FVector`, `FVector2D`, `FLinearColor` and others);
- 6 struct out-parameter getters (`FMargin` and others).

One bitfield getter compiles to `shr eax, 4; and al, 1` where the others mask `eax`. With
v140, `return b;`, `!= 0`, `!!b` and `(bool)b` all mask `eax` for a uint32 unit. Only
`return b ? true : false;` masks `al`, so that form is generated where the reference shows
it (`AFortWeaponRanged::UseFirstPersonTargeting`).

Reconstruction:
- The 149 members and 35 bitfield members are declared at their reflected offsets in
  `Classes.gen.h`. A bitfield unit names its reflected bits and leaves the others unnamed
  (`uint32 : 1;`). The rest of each class stays opaque.
- The natives are defined out of line, one translation unit per package
  (`Source/Generated/Natives/<Package>.natives.cpp`). The reference compiles them in the
  class's own `.cpp`, apart from the generated code, so its thunks call them rather than
  inline them.
- The thunks are UHT 4.20's `DECLARE_FUNCTION` bodies, as for virtual natives.
- The manifest symbol is the MSVC decoration of the native's signature: bool, the sized
  integers, float, double, class pointers, enums, and structs the shims define with `struct`
  (by value `U`, by reference `AEAU`/`AEBU`). A returned enum or struct carries the `?A`
  prefix. `TEnumAsByte` signatures are left out.

All 190 natives are exact, outside the denominator (leaf). Each thunk's call then resolves
through that exact match, and all 190 thunks are exact, in the denominator.

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
  (the unit marker), then the rest in header order. `unity_order.py` records them, by value,
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
- class registrars: 2,212 of 3,283 exact;
- struct registrars: 1,283 of 2,110;
- enum registrars: 598 of 1,094;
- class auto-initializers (outside the denominator): 1,248 of 3,283.

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

What remains:
- In Engine (7 extra copies), CoreUObject (4), MovieScene and others, hand-written code uses
  the package-name literal too. 2,329 registrars wait only on these copies
  (`analysis/match-queue.json`).
- `AutoInitialize` objects are not predicted: MSVC emits these vtable-bearing `.data` objects
  out of source order.

The 3,283 `GetPrivateStaticClass` bodies are relocation-equivalent. Fields not yet resolved
include `InternalConstructor<C>`, `InternalVTableHelperCtorCaller<C>`, the package and
config literals, and the empty `StaticRegisterNatives` that ICF folds for classes without
natives.

## Naming confidence

`confirmed` needs direct evidence such as an exported symbol, reflection string or
debug data. Names inferred from engine source plus unique structural agreement are
`high-confidence inferred`. Shape-only agreement is `low-confidence inferred`.
