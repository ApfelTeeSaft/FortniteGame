# Status

Stage 1 (exact-match client decompilation): **in progress**. A validated decrypted image of
the reference build now supplies plaintext function bodies. Stages 2–4 have not started.

| Item | State (verified 2026-11-24) |
| --- | --- |
| Reference | `FortniteClient-Win64-Shipping.exe`, 82,298,304 bytes, SHA-256 `9731a6b5…eb449102`, linked 2018-02-14, `++Fortnite+Release-2.5-CL-3889387`, version resource `4.20.0-3889387` |
| Decrypted reference | Owner-supplied PE dump, SHA-256 `c81fe58a…2f97370`, local only. After un-rebasing all 788,029 DIR64 sites it is byte-identical to the original over 23.5 MB of linker-produced plaintext. Prologues verify for 157,439 of 157,632 primary functions with unwind codes (99.88 %). See `analysis/decrypted-reference.json` |
| Compiler evidence | Rich header: Utc1900 C/C++ build 24215, Linker 14.00.24215, no LTCG product ids. The local v140 `cl.exe` is 19.00.24215.1 and its objects carry `@comp.id` prodid 261, build 24215 |
| VS2019 solution | `FortniteGameCode.sln` `ClientShipping\|x64` (toolset v140) builds with 0 errors and 0 warnings |
| Exact functions | **37,216 / 157,719** primary `.pdata` functions (23.60 %, 2,582,887 bytes):
- 2 matching on-disk plaintext (SEH filter funclets);
- 169 hand-reconstructed functions matching the decrypted image;
- 53 generated GameplayAbilities attribute getters (`tools/codegen/attribute_getters.py`);
- 36,992 generated UHT functions:
  - classes: 11,095 UFunction creators, 3,283 `Z_Construct_UClass_*`, 2,796 `GetPrivateStaticClass`,
    1,180 `StaticRegisterNatives*`, 3,277 `FCompiledInDefer` initializers and 1,322 exec thunks
    (1,114 of virtual natives, 208 of native accessors);
  - packages: 626 package-scope delegate creators and 71 `Z_Construct_UPackage_*`;
  - USTRUCTs: 2,104 `Z_Construct_UScriptStruct_*`, 2,058 `StaticStruct`, 1,782 `NewStructOps`,
    2,101 `StaticRegisterNatives` and 2,106 `FCompiledInDeferStruct` initializers;
  - UENUMs: 1,088 `Z_Construct_UEnum_*`, 1,016 `<Enum>_StaticEnum` and 1,087 `FCompiledInDeferEnum` initializers.

Generated code is compiled in 224 unity units in the reference's recovered source order (`docs/REVERSE_ENGINEERING.md`, "Module layout model"). Every relocation is resolved from independent or leave-one-out evidence. Also exact, outside the denominator: 1,216 `StaticClass` thunks, 3,174 `AutoInitialize` initializers, 212 leaf exec thunks, 208 native accessors, 170 vector-constant initializers, `FCommandLine::IsInitialized`, 49 hand-written leaves without `.pdata` (Kismet math, Core date and colour helpers, `FmodReportError`) and 41 dynamic initializers of the Kismet and UnrealMath units |
| Pipeline stages | Tracked apart (`python tools/progress/generate.py`, `pipeline`): 157,719 identified; 37,913 reconstructed and compiled; 37,216 exact; 697 needing investigation, queued by cause in `analysis/match-queue.json` (`tools/matching/match_queue.py`). `tools/matching/regressions.py` reports exact matches lost against `HEAD` |
| Relocation-equivalent | 691 in the denominator, mostly:
- 487 `GetPrivateStaticClass` bodies, 453 of them waiting only on `InternalConstructor<C>`;
- 25 registrars and `StaticStruct`s waiting on string-literal copies;
- statics next to items not modelled yet.

Six are `partial`: one enum registration initializer (shared literal copy), three exec thunks
whose virtual natives were misidentified (inlined natives; see `docs/REVERSE_ENGINEERING.md`, "Exec
thunk parameters"), `MinimumAreaRectangle` (8 bytes of protector-written alignment padding) and
the `ConvexHull2D` copy it calls (register allocation; "Eleventh family"). The per-manifest counts are in `analysis/functions-uht-*.json` |
| Named functions | 28,028 denominator functions (17.77 %):
- from UHT reflection tables: 7,886 exec thunks, 11,102 `Z_Construct_UFunction_*` creators, and
  registrar/`GetPrivateStaticClass` pairs for 1,180 attributed classes (`analysis/reflection-natives.json`);
- 5,273 native implementations called by their exec thunks, 5,232 of them high-confidence
  (`analysis/native-implementations.json`);
- 1,407 more virtual-function implementations from class vtables (`analysis/vtables.json`).

Outside the denominator: 1,374 leaf exec thunks and 1,731 leaf natives. Class vtables: 3,299 located,
1,797 slots named from 1,995 virtual natives |
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

Work follows `CLAUDE.md`'s adaptive workflow:
- Batches are sized by dependency: 50–200 functions where a systematic cause applies, fewer
  where layouts must be investigated.
- Reconstruction continues while non-exact functions wait in `analysis/match-queue.json`. The
  largest groups get systematic fixes before function-specific ones.
- `tools/matching/regressions.py` gates each commit.

Largest queue groups (2026-11-24):
- Hand-written code: 145 primary callers of `FParse::Param` and `FCommandLine::Get`, 101 named
  by their switch literal in the 4.20 tree (`docs/REVERSE_ENGINEERING.md`, "Fourth family").
  Thread-safe statics resolve only within reconstructed clusters of neighbouring functions
  ("Thread-safe statics"); most remaining checks need their neighbours or class members.
- Kismet math: 16 of the 149 `UKismetMathLibrary` native targets remain (13 with `.pdata`):
  `MakeDateTime` (relocation-equivalent: `FString::PrintfImpl`), `MinimumAreaRectangle`
  (partial: protector-written padding), the five `From*` timespan natives (`FText::Format`),
  `FDateTime::Parse`, `FTimespan::Parse`, the four `.inl` copies in the generated Engine.18 unit
  (they need that unit's vector constants), and three CRT thunks (`logf`, `expf`, `powf`) the
  natives list names after UFunctions (`docs/REVERSE_ENGINEERING.md`, "Eleventh family").
- 25 attribute getters waiting on their static: their reference run follows an object's first
  use, not declaration order ("Attribute getters").
- 453 `GetPrivateStaticClass` bodies waiting only on `InternalConstructor<C>`. 374 of the
  instances are ICF-folded into another class's identical copy. No evidence independent of
  the field says which classes' constructors and vtables are identical. Of the 79 others,
  most have no other member of their run observed unfolded, or sides that disagree with
  neither prediction held.
- 15 package constructors compiled in units of their own: the `.rdata` record bracket of
  their `ReturnPackage` holds two or more free slots.
- 8 creators and package delegates and 6 enum constructors whose static is not predicted:
  at an end of their object's record run, or with several free slots between their record
  neighbours.
- 25 functions waiting on string literals, with two or more plausible copies left: 9 struct
  `StaticRegisterNatives` on pooled `??_C@` literals, the rest on `$SG` copies.
- 66 `StaticEnum` singletons. Their block has both ends free with no `PrivateStaticClass`
  below, their run lies outside a split unit's observed runs, or they are a unit's only enum
  (23). Pinning block ends needs a model of what follows a block: the unit's 1-byte
  registration objects and header statics, in MSVC's own order.
- 22 units hold several `TClassCompiledInDefer` runs while their literals interleave. These
  are single objects whose data comes in batches; that is not modelled.

Done (2026-11-25):
- Transforms and the minimum-area rectangle: 18 hand-written functions, 15 exact, among them
  `FTransform::GetRelativeTransform` (`ConvertTransformToRelative`) and its matrix fallback,
  `FMatrix::Inverse`/`InverseFast`/`RemoveScaling`, `CalcTangents` and the TArray growth copies.
  `TransformVectorized.cpp` compiles through `UnrealMath.cpp` (one Core unity unit).
  `MinimumAreaRectangle` stays partial: 8 padding bytes the protector wrote. No regressions.

Done (2026-11-24):
- Dates, times, colours and rotator helpers: 68 hand-written functions in five units (new:
  `DateTime.cpp`, `Timespan.cpp`, `WindowsPlatformTime.cpp`, `Color.cpp`), 65 exact. Found with
  the new `tools/matching/locate.py`. Data blocks of 64+ bytes may resolve in `.data`. Two
  engine differences (#10 `RotateVector`, #11 `FromMinutes`). No regressions.
- FTransform natives: 9 hand-written functions, all exact. Among them `TLerp` (2,364 bytes),
  `TEase`, `TInterpTo`, `Transform_Determinant`, `IsPointInBoxWithTransform` and
  `GetAzimuthAndElevation`, with `FDualQuat::operator*` and `FMatrix::Determinant`. The
  pooled-constant rule now covers 16-byte `__xmm@` constants by packed loads. No regressions.
- UnrealMath's 24 `GlobalVectorConstants`, defined in header order with their initializers as
  entries (13 exact). With them, 7 more functions are exact: `FRotator::Quaternion`,
  `FMath::RInterpTo`/`RInterpConstantTo`, `FQuat::FindBetweenNormals`/`FindBetweenVectors`,
  `FQuat::SlerpFullPath_NotNormalized` and `FQuat::Squad`. No regressions.
- `FQuat`/`FRotationMatrix`: 23 hand-written functions, all exact. Among them the Core quaternion
  and matrix code, the nine `FRotationMatrix::MakeFrom*` and eight Kismet rotator natives.
  The Kismet unit's 25 dynamic initializers, recovered as entries, resolve its
  `GlobalVectorConstants` and warning-id slots. 11 of them are exact, and the three
  `ReportError_*` leaves are now exact. No regressions.
- Kismet math natives and their Core helpers: 75 hand-written functions, 72 exact (45 in the
  denominator, 27 leaves). `MathDecls.h` is now shared with the UHT world; new evidence for
  `__ImageBase` and a function's own jump-table labels. Engine difference #9
  (`GetRangePct`). No regressions.
- More Core math (`FRotator::Vector`, `FMath::VRand`) and the Kismet wrappers that call them
  (`UKismetMathLibrary::GetForwardVector`, `RandomUnitVector`): 4 exact. Pooled `__real@`
  constants with several scalar-loaded copies now resolve when one copy dominates. Two
  attribute getters also became exact, cause not established (`docs/REVERSE_ENGINEERING.md`,
  "Fifth family"). No regressions.
- Core vector math (`FGenericPlatformMath::Atan2`, `FVector::ToOrientationRotator`,
  `FVector::Rotation`) exact, with new evidence for pooled `__real@` float constants; no
  regressions.
- GameplayAbilities attribute getters generated from their shape (78 of 84; one class's
  `FClassParams` not located): 51 exact, 27 relocation-equivalent, no regressions.
- Thread-safe statics: `SECREL` fields, and three clusters of command-line checks reconstructed
  whole (`FStats`, two D3D12RHI units): 7 exact, 2 singles relocation-equivalent, no regressions.
- First hand-written batch, command-line switch checks: 5 exact (two RHI adapter-vendor
  preferences, `AllowThreadHeartBeat`, two Fortnite switches) and 2 relocation-equivalent on
  pooled literals, no regressions.
- Package statics bracketed by the classes whose `FClassParams` records surround the
  package's `FPackageParams` in `.rdata`: 2 package constructors exact, no regressions.
- 25 native arrays the scanner had dropped (a tie with their shifted reading) are recovered:
  their registrars, 24 `GetPrivateStaticClass` bodies and 2 exec thunks exact, plus 25
  `StaticClass` thunks and 1 accessor outside the denominator, no regressions.
- Section-relative predictions never land on a `.bss`/`.data` slot another symbol is observed
  at: 23 functions exact (8 `StaticEnum`, 6 `StaticStruct`, 9 creators and constructors),
  35 outside the denominator, no regressions.
- Literal copies of 8 bytes or more must be 8-byte aligned, which drops the tails of longer
  wide strings: 130 struct functions exact (`StaticStruct`, registration and
  `StaticRegisterNatives` initializers), no regressions.
- `InternalConstructor<C>` runs: a side whose prediction another unit's instance holds is
  dropped when the sides disagree, and declared-only instances are checked by their inlined
  prologue: 88 `GetPrivateStaticClass` bodies exact, no regressions.
- `StaticEnum` singletons: slot elimination before section-relative, gaps across a unit's
  clusters, and the lower end after any `PrivateStaticClass`: 213 more exact, no regressions.

Done (2026-11-23):
- Record brackets over all three record kinds (creators, enums, structs in one order):
  23 more exact, no regressions.
- Record-bracketed slots for creator statics (the one free slot between the statics of
  the record neighbours): 66 package delegates and 13 creators exact, no regressions.
- Class delegate creators placed in definition order (`ClassDelegates/<Class>.gen.cpp`, by
  `.data` record order): 42 more exact, and the 4 regressions of the batch below recovered.
- 249 more exact from `.bss` statics: creators in `FFunctionParams` record order, rigid
  pairs (`OuterClass`/`PrivateStaticClass`, last creator/`OuterClass`) as tie-breaks, and a
  singleton block's lower end after another unit's closing `PrivateStaticClass`. 4
  regressions (two structs), recovered by the delegate placement above.
- 845 more `GetPrivateStaticClass` bodies: the `InternalConstructor` run follows the
  object's `GetPrivateStaticClass` order, sizes declared-only instances from the reference,
  walks through folded members and accepts checked one-sided predictions (no regressions).
- 1,776 `GetPrivateStaticClass` bodies: ICF-folded `return nullptr` and empty-function
  bodies, and `InternalConstructor<C>` from its class-ordered code run (no regressions).
- 2,329 registrars that waited on package-name literal copies: other code's copies are
  claimed by code references and object layout (2,685 functions exact, no regressions).
- 279 `StaticEnum`s resolved by slot elimination in their unit's singleton block.
- 414 vector-constant initializers added (136 exact, outside the denominator).
- 22 units that span several of the reference's objects are cut into 64 (224 units in all).
  105 functions became exact, with no regressions.
- The 442 creators that waited on `FFunctionParams` records are exact.
- The records are function-local statics, as in the reference. 3,103 `AutoInitialize`
  initializers are exact (`docs/REVERSE_ENGINEERING.md`, "Data layout").

The numbered tasks below predate this queue.

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
   - Module layout model, in place: 224 unity units built from per-item fragments in the
     order recovered from `.CRT$XCU`. They contain all classes (`Classes.gen.h`,
     `IMPLEMENT_CLASS`), structs, enums, package-scope delegates, and package constructors at
     their `init.gen.cpp` position, which opens a unity file. Remaining:
     - the creators of the 11 function tables not attributed to a class;
     - the 7 intrinsic classes;
     - `InternalConstructor<C>` where its code run is blocked.
   - The remaining class constructors and 662 `GetPrivateStaticClass` bodies.
   - Exec thunks (9,193; `docs/REVERSE_ENGINEERING.md`, "Native implementations" and
     "Class vtables"). A thunk with a direct native depends on the native's address, which
     has no evidence independent of the thunk. Thunks of virtual natives can match: 377 do.
     Next:
     - Parameters are decoded (`tools/codegen/uht_props.py`), including `FString`, `TArray`
       of any modelled element type (`ContainersRecovered.h`), `FText` and `TSubclassOf`
       (`TextRecovered.h`) and 17 structs from the 4.20 headers
       (`EngineStructsRecovered.h`), including `FGameplayTagContainer` and
       `FGameplayCueParameters`, `FViewTargetTransitionParams`,
       `FGameplayAbilityActivationInfo`, `FGameplayEventData`, `FPartyReservation`,
       `FAthenaQuickChatActiveEntry` (Fortnite-only, from reflection),
       `FGameplayEffectSpecForRPC`, `FAssetData`, `FTransform` (`TransformRecovered.h`) and
       soft object pointers. Interfaces' thunks are `I<Name>` members (27 native
       interfaces), `FFortItemEntry` and `FFortConversationSentence` (Fortnite-only, from
       reflection and their out-of-line constructors and destructors), `FPointerEvent`
       (the reference's, without `Force`), `FGeometry` and `FSlateBrush` (the reference's,
       without `ResourceHandle`). Byte enums declared as `TEnumAsByte` are recovered from
       the call. 1,569 of the 1,661 virtual-native UFunctions have thunks, and 1,307 of
       their 1,317 addresses match.
     - Direct natives: 206 accessors are reconstructed out of line, with their members
       declared at the reflected offsets (`tools/codegen/uht_accessors.py`). They are:
       - scalar, struct (by value or out parameter), bitfield, `TEnumAsByte` and
         `TSubclassOf` getters and setters;
       - comparisons;
       - null-guarded getters.

       All 206 and their thunks are exact. Out of reach of this method:
       - members that are not reflected (no evidence for their offsets apart from the getter);
       - pointers to Slate (non-UObject) types;
       - enum comparisons (enumerators not declared).

       Larger natives need real reconstruction.
     - Next: `TArray` of enums (3 UFunctions), the 3 thunks whose natives are inlined from
       headers, and `FSlateColor::operator=` (`0x0028ABE0`; register choice differs), which
       would let `GetSmallPreviewImageBrush` and the brush's copy assignment match.
     - Known fragility: a unit's `.rdata` section order changes with header content, so a
       few literal predictions come and go with shim changes (`FKey`'s registrar,
       `FFoliageTypeObject::StaticStruct`).
     - Each unit defines its own `GlobalVectorConstants`, those its `.CRT$XCU`
       initializers name in the reference (131 units; `docs/REVERSE_ENGINEERING.md`,
       "Per-unit vector constants"). The count is level with defining two in every unit.
     - `StaticEnum` layout is stable. It is defined with external linkage, first in its
       unit, in source order. The block's position and order no longer change with
       unrelated code. That cost 19 exact functions, matches the earlier, unstable order
       made by chance or literals it kept in parse order (`docs/REVERSE_ENGINEERING.md`,
       "Enum constructors and `StaticEnum`").
4. Run the IDA export on the decrypted image for call graphs and cross-references.

## Reproduce

```
python tools/matching/fingerprint.py                    # analysis/build-fingerprint.json
python tools/matching/survey.py                         # analysis/plaintext-survey.json
python tools/matching/ingest_dump.py --dump <dump>      # local decrypted image + analysis/decrypted-reference.json
python tools/matching/selftest.py                       # build, compare --check, progress --verify
```
