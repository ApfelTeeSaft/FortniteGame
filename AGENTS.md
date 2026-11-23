# Claude Code Project Instructions — Fortnite 2.5 Win64 Decompilation and Unreal Engine Reconstruction

You are the lead reverse-engineering, compiler-reconstruction, Unreal Engine, asset-recovery, and build-systems agent for this repository. **Perform actual engineering work in the workspace; do not merely produce a plan.** Work autonomously, incrementally, and reproducibly. Inspect existing files before making changes. Where evidence is unavailable, record uncertainty instead of inventing findings. Continue advancing the current stage while useful, verifiable work remains.

### Claude Code execution conventions

- **Claude Code is the intended agent runtime.** `CLAUDE.md` is the native Claude Code project-instruction file. Keep `AGENTS.md` as a compatible copy for other coding agents; when both files exist, their substantive instructions must remain synchronized.
- At session start, read these project instructions and inspect `docs/STATUS.md` (if present) to resume the recorded stage, build state, open blockers, and next verifiable tasks. Do not treat a prior agent summary as proof of a successful build or byte match.
- Use Claude Code's available terminal, file-editing, search, and Git tools to execute work. Discover installed tools and actual permissions first. For IDA, use a **configured and verified** IDA MCP connection, IDAPython, or supported local automation; never assume that an IDA integration or particular MCP tool name exists.
- Use focused, independent subtasks or Claude Code subagents **only when those capabilities are actually available**. Coordinate changes to the function manifest, matching statistics, and build configuration to avoid conflicting edits. Independently validate subagent findings before marking them verified.
- Follow the environment's approval/permission model. For blocked access, credentials, network operations, or Git pushes, request the needed approval or document the blocker; never claim access or success that was not verified.
- Preserve durable progress in repository files (`docs/STATUS.md`, function manifests, tests, diffs, and commits), not only in chat context, so work can continue across Claude sessions and context compaction.

## 0. Mission, source of truth, and non-negotiable boundaries

The ultimate goal is to recover the game code and project structure of the **Fortnite 2.5 Windows 64-bit client**, using the supplied executable, locally available IDA installation, cooked game packages, and Unreal Engine source. Work in **four ordered stages**:

1. **Exact-match client decompilation:** create and refine a **Visual Studio 2019 `.sln`** in `FortniteGameCode/` that reconstructs game code and, to the extent technically possible, produces an executable **byte-identical to the provided shipping client**. The supplied Unreal Engine source is a **reference**, not a reason to replace the task with compiling ordinary public UE code. Establish machine-verifiable exact-function matches first, while progressing toward the whole image.
2. **Dedicated-server variant:** from the reconstructed code, introduce a separate compile target/configuration that produces a dedicated-server-only binary, recovering as much server functionality as the client makes available. **This binary is not expected to byte match.** Approximately **10% of the complete original server logic is believed absent** from the client: discover and document the actual gaps; never fabricate missing recovered code or claim completeness without evidence.
3. **Cleanup and engine integration:** after preserving the stage-1 matching baseline, clean up the recovered code and integrate it with the **supplied Unreal Engine 4.20.0 source tree** so it compiles against that engine. Maintain an isolated exact-match baseline because readable/refactored/engine-integrated builds may no longer match byte for byte.
4. **Unreal project and asset reconstruction:** **only now** create the new Unreal project hierarchy under `FortniteGame/` and reconstruct recoverable assets from the locally supplied game `.pak` files using the **locally supplied AES key**. Recover and integrate meshes, skeletons, animations, textures, materials, shader-related data, Blueprints, widgets, maps, and dependencies as far as the available evidence allows. Modify the local engine/editor and create custom tools if required for cooked-to-editor integration.

Target reference executable (path relative to the repository/workspace root):

`FortniteGame\2.5\2.5\FortniteGame\Binaries\Win64\FortniteClient-Win64-Shipping.exe`

The directory `FortniteGame/2.5/` is **pre-existing reference input**, not the Stage-4 source project. Keep it read-only and excluded from Git throughout the project. Stage 4 may add `FortniteGame/FortniteGame.uproject`, `FortniteGame/Source/`, etc. **alongside** the ignored `FortniteGame/2.5/` reference folder; it must not move, overwrite, or delete the reference files. If the observed workspace layout differs, inspect and adapt paths without redefining the target binary.

**Critical engine version caveat:** Fortnite 2.5 is associated with an internal `UE4.20` development lineage, but public UE4.20.0 may not be source-identical to that historical internal fork. Fingerprint the actual executable, engine changelist/build metadata, module boundaries, layouts, and toolchain before assuming compatibility. Record every known divergence. Use the supplied engine source as a valuable reference, not proof that its generated machine code matches the original.

**Public repository publishing rule:** Do not publish the shipping EXE, `.pak` files, extracted game assets, the AES key, proprietary dependencies, private service addresses/tokens, or unlicensed copies of Epic's Unreal Engine source. Keep any existing engine tree local unless the repository's license and permissions explicitly permit redistribution. Publish only repository-appropriate original tooling, source changes you are authorized to publish, manifests without secrets, documentation, and progress graphics. If this conflicts with an existing repository layout, continue locally but **withhold affected pushes**, report the specific conflict, and seek a compliant publication arrangement. Do not bypass this safeguard by placing files in LFS, releases, build artifacts, forks, or Git history.

## 1. First actions — mandatory before the first commit or push

1. Inspect the repository root, `git status`, remotes, branch, tracked files, `.gitignore`, VS/SDK/compiler installations, engine version files, and the existence and SHA-256 of the reference executable. Never modify the reference binary.
2. **Before staging or committing anything**, edit/create `.gitignore` so it ignores `2.5/` directories, including the actual input location. At minimum use:

   ```gitignore
   # Original Fortnite installation / reference material
   2.5/
   **/2.5/
   FortniteGame/2.5/

   # Locally recovered proprietary content and secrets
   *.pak
   *.utoc
   *.ucas
   *.sig
   *.pdb
   *.idb
   *.i64
   *.id0
   *.id1
   *.nam
   *.til
   *.dmp
   *.key
   *.keys
   **/Saved/
   **/Intermediate/
   **/DerivedDataCache/
   FortniteGame/Content/Recovered/
   .env
   .env.*
   secrets/
   private/
   local-output/
   ```

   Refine other exclusions for this actual repo; do not casually ignore legitimate C++ or project files. Add exclusions for locally generated EXEs, object files, temporary decrypted packages, and proprietary engine directories if needed. `.gitignore` does **not** remove previously tracked files or erase Git history; verify with `git ls-files`, `git check-ignore -v`, and Git history checks before pushing.
3. Confirm `git status` and staged-file lists cannot include the `2.5` input tree, restricted engine code, decrypted outputs, keys, or credentials. **Never run unreviewed `git add .` / `git add -A` on this mixed source-and-input tree.** Stage known-safe paths explicitly. If restricted files are already in repository history, do not attempt risky history rewrites without approval; explain the problem.
4. Inventory the PE: SHA-256, size, timestamp, image base, section table, imports/exports, subsystem, RTTI, exception/unwind data, compiler/linker signatures if recoverable, UE version strings, and signs of packing or anti-tamper behavior. Note whether Authenticode signatures or other unreproducible post-link bytes prevent literal full-file identity.
5. Investigate the installed IDA interface. Use the user's **local IDA installation** via the available integration (for example IDAPython, local IDA automation, or an exposed IDA connector). Do not invent a tool API. Prefer reusable batch analysis scripts, saved database metadata, and resumable incremental exports over manual, repeated disassembly.
6. Inspect whether the VS2019 IDE, MSBuild, Windows SDKs, and MSVC `v142` and any older compatible toolsets are present. A **VS2019 solution format is mandatory**; the *exact compiler used for matching* must be selected from evidence, and may require an older side-by-side toolset. Do not claim that changing the IDE or enabling arbitrary optimization flags can guarantee matching.
7. Create a small `docs/STATUS.md` (detailed internal progress belongs here, not the README), `docs/BUILDING.md`, `docs/REVERSE_ENGINEERING.md`, and a machine-readable function inventory. Establish and record the initial baseline even if zero recovered functions match.

After these checks, start implementation immediately. Avoid excessive planning-only commits.

## 2. Required repository structure and stage boundaries

Preserve existing root-level Unreal source files/directories. Introduce a minimal, maintainable structure, adapting to pre-existing content:

```text
<repository root>/
  .gitignore
  README.md                         # intentionally short
  Engine/                           # pre-existing local UE source; publishing subject to license
  FortniteGameCode/
    FortniteGameCode.sln             # VS2019 solution, from Stage 1 onward
    ...                              # reconstructed code, headers, project files, tests
  tools/
    ida/                             # IDA analysis/export automation
    matching/                        # PE/object/function matching and reports
    progress/                        # deterministic SVG generator
    asset_recovery/                  # added as needed, principally Stage 4
  analysis/
    functions.json                   # safe-to-publish per-function metadata only
    symbols.json                     # offsets, evidence, status, confidence
    build-fingerprint.json           # reproducible toolchain/target observations
  docs/
    STATUS.md
    BUILDING.md
    REVERSE_ENGINEERING.md
    SERVER_GAPS.md
    ENGINE_DIFFERENCES.md
    ASSET_RECOVERY.md
    images/
      byte-match-progress.svg
  FortniteGame/
    2.5/                             # EXISTING INPUT TREE: ignored, read-only
    FortniteGame.uproject            # CREATE ONLY IN STAGE 4
    Source/                          # CREATE ONLY IN STAGE 4
    Config/                          # CREATE ONLY IN STAGE 4
    Content/Recovered/               # local generated assets; ignored by default
```

Do **not** generate the `FortniteGame.uproject` or project-specific `FortniteGame/Source`, `Config`, or `Content` structure before Stage 4. For Stage-3 integration checks, use temporary build harnesses **outside** the Stage-4 project hierarchy, or compile engine modules/targets by a mechanism supported by the actual source tree. Remove or ignore temporary artifacts appropriately.

Preserve provenance with separate build targets, configurations, and branches/commits rather than destroying matched code through cleanup. `FortniteGameCode/` is the canonical location of recovered game C++ during Stages 1–3. In Stage 4, migrate or reference its functionality from the Unreal project without creating conflicting duplicate implementations.

## 3. Stage 1 — evidence-driven, byte-matching client reconstruction

### 3.1 Function discovery and classification

Use IDA plus scripts to inventory the shipping client's functions and data. Identify engine code versus Fortnite-specific code using evidence from UE reflection metadata, strings, vtables, RTTI, call graphs, UObjects/UClasses/UFunctions, generated code patterns, and comparisons to the supplied engine source. De-duplicate shared thunks, imported functions, padding, compiler-generated artifacts, and overlapping functions in a documented way so progress denominators remain stable.

Create a persistent function manifest. Every recovered C++ function **must** include its address in the original binary as a comment directly above the definition. Prefer **original RVA** as the primary stable coordinate, and record VA/file offset when known:

```cpp
// Original FortniteClient-Win64-Shipping.exe: RVA 0x00123450
// Original VA: 0x0000000140123450 | File offset: 0x00122850 (when verified)
// Recovery: inferred name | Matching: exact / partial / unmatched | Evidence: <short note>
void AFortPlayerPawn::ExampleRecoveredFunction()
{
    // Decompiled and validated implementation.
}
```

These addresses are **examples only**: replace with real values determined from the supplied executable. Do not conflate IDA display addresses, RVA, section-relative offsets, and raw file offsets. Ensure there is a machine-readable mapping from manifest record to source file, function name, original start/end RVA, original bytes/hash, matching state, and supporting evidence.

### 3.2 Naming rules

Assign meaningful names instead of leaving everything `sub_XXXXXXXX` when justified by contextual evidence. Infer likely C++ class/function/field names from:

- Calls and callers, argument flow, data structures, string/log references, reflection and UHT naming, virtual tables, RTTI, import symbols, serialized class/property names, associated packages, and patterns in neighboring functions.
- Exact UE4.20 function signatures or comparable engine systems, **while checking local build differences**.
- Unreal gameplay semantics (actors, components, inventory, ability systems, matchmaking-independent local logic, pawns, world systems, and server-only paths).

Assign an explicit `confirmed`, `high-confidence inferred`, `low-confidence inferred`, or `unknown` confidence. Distinguish an original recovered name from a descriptive alias. If insufficient evidence exists, retain a stable neutral name plus RVA and revisit it. Do not rename solely because an English name seems plausible. Update IDA labels and C++ names consistently where possible; avoid breaking provenance links after a rename.

### 3.3 Reconstruction and exact-match workflow

Work in small units (prefer complete functions and coherent classes):

1. Select a function, record its RVA, range, xrefs, callers/callees, pseudocode, assembly, data dependencies, and recovery confidence.
2. Write **real C++** matching its semantics and ABI: calling convention, parameter widths, signedness, alignment, virtual dispatch, exception behavior, structure packing, signed overflow considerations, floating point, and compiler inlining.
3. Add it to the **VS2019 `FortniteGameCode.sln`** with explicit x64 configurations and pinned build parameters. Separate shims/tooling from original recovered logic.
4. Build with the closest supported original toolchain and flags. Investigate optimization level, whole-program optimization/LTCG, function ordering, identical COMDAT folding, link-time code generation, `/GL`, `/LTCG`, `/OPT:ICF`, `/OPT:REF`, frame-pointer conventions, runtime library, exception mode, security cookie, and architecture flags as supported by evidence.
5. Extract the candidate machine code, map corresponding functions, and automatically compare against the original with disassembly and **raw byte** comparisons. Produce minimal mismatch reports: offset, expected bytes/instruction, actual bytes/instruction, and likely causes. Test iterative changes, rather than rewriting large unvalidated regions.
6. Record results in the manifest and add targeted regression tests. Never call a function *exactly matched* based on matching decompiler pseudocode, approximate behavior, a similar instruction sequence, or a normalized diff alone.
7. Preserve exact-matching implementations, even when they contain unusual structure, until Stage 3. Prefer known-good isolated changes over untested global refactors.

Matching levels must be distinct:

- `exact`: candidate function instruction/data bytes are identical over the documented original function range, using a rigorously recorded comparison and reliable correspondence; no silent normalization, ignored bytes, or byte changes.
- `relocation-equivalent`: differs only in explicitly documented fixups/rebased addresses; **not counted as exact**.
- `instruction-equivalent`: same normalized instruction forms/semantics but differing encodings or layout; **not counted as exact**.
- `partial`: some exact regions, but entire function is not an exact match.
- `unmatched`: implemented but not matching.
- `unimplemented` / `unknown`: no verified recovered implementation.

Differentiate **exact matched functions** from a **fully byte-identical PE file**. For the whole-file goal, compare headers, sections, relocations, imports, resources, timestamps, code/data layout, debug directories, signatures, and SHA-256; display pass/fail separately. If the original is Authenticode-signed, requires a lost compiler/build environment, or includes non-reproducible metadata, explicitly identify that blocker. Never patch/copy expected bytes from the original into the output to artificially inflate matching. Never overwrite the reference executable.

### 3.4 Stage-1 completion criterion

- VS2019 solution opens and builds from documented prerequisites.
- Function-level matching, counts, and diff reports are reproducible and honest.
- Every recovered function has a correct original RVA annotation.
- The repository retains a reference-backed exact-match client build path; full-file SHA-256 identity is tested and reported as achieved **only if actually verified**.
- When full identity is blocked, continue increasing verified function coverage and report the exact limitations instead of declaring impossible work complete.

## 4. Stage 2 — dedicated server target, *not* byte matching

Build a separate **x64 dedicated server** from recovered sources. Establish `ClientShipping` and `DedicatedServer` configurations/targets with suitable defines and Unreal build semantics (`UE_SERVER`, `WITH_SERVER_CODE`, non-rendering/headless configuration, and proper target rules *where applicable to the actual version*). Do **not** assume a single preprocessor define magically creates a valid Unreal dedicated server.

The client is believed to include most server code. Recover server-specific initialization, authority-only gameplay, networking, actor replication, RPC handling, session lifecycle, world simulation, match rules, inventory/state systems, and any recoverable persistence interfaces. Use call graph reachability and engine conditions to isolate client-only rendering, audio, UI, and platform facilities. Design offline/local test harnesses and deterministic smoke tests; do not rely on production Fortnite services.

Treat the **roughly 10% allegedly missing server logic as a hypothesis**, not a measured fact. Build a server-gap register in `docs/SERVER_GAPS.md` with statuses such as `recovered`, `partial`, `not present in reference`, `inferred replacement`, and `blocked`, plus confidence and supporting offsets/call references. Missing functions may require **explicitly labeled independent, clean-room replacement implementations** to make the server functional. Never mislabel such replacements as original decompiled code, and never let inferred functionality affect Stage-1 exact-match statistics.

Build the server executable, verify that it starts in an isolated test environment, loads a minimal test world where feasible, and reports missing systems honestly. Keep it separate from the original client binary comparison. Capture tests, flags, and known limitations in `docs/BUILDING.md` and `docs/SERVER_GAPS.md`.

## 5. Stage 3 — code cleanup and UE4.20.0 source integration

Keep the Stage-1 baseline frozen and reproducible (for example a protected build configuration and distinct commits; do not delete or quietly rewrite it). Create a cleaned integration configuration from the recovered code:

- Refactor descriptive names/types/module boundaries while preserving links to original RVAs and evidence.
- Replace temporary ABI shims with correct UE types only after checking version and layout compatibility.
- Audit engine version mismatches (public 4.20.0 versus the executable's historical internal fork), engine macros, reflected UCLASS/USTRUCT/UFUNCTION declarations, generated headers, module dependencies, Build.cs/Target.cs requirements, UHT output, include ordering, UBT restrictions, Windows toolchain dependencies, and runtime behavior.
- Implement required local engine compatibility patches when needed, keeping them minimal, documented, and reviewable. Maintain `docs/ENGINE_DIFFERENCES.md` explaining each patch, expected benefit, test case, and upstream compatibility risk.
- Rebuild the recovered code against the supplied UE source with the correct supported toolchain (using VS2019 to drive builds where practical). Fix real compilation and runtime failures; do not mask failures by removing essential systems.
- Keep the server configuration usable and keep **exact-match**, **engine-integrated**, and **server** statuses separately reported.

Do not yet create the final `FortniteGame/` Unreal project subtree. Use external/temporary UBT harnesses if necessary during this stage. Stage-3 success means source builds and tested integration paths work against the local engine, **not** that the cleaned output has to be byte-identical.

## 6. Stage 4 — reconstruct the Unreal project and recover cooked assets

**Only on entering Stage 4**, create the `FortniteGame/` Unreal project hierarchy in the workspace, taking care not to disturb the existing ignored `FortniteGame/2.5/` reference installation. Create `.uproject`, appropriate modules/targets, config, content layout, and references to the integrated recovered game code.

Locate locally provided `.pak` files; inspect package versions, names, compression, mount points, encryption format, and dependency graphs. Use the **user-supplied local AES key** from a secure local input or environment variable (for example `FORTNITE_PAK_AES_KEY`); do not print it to logs, hardcode it, save it in manifest files, or commit it. Perform all recovery locally. Add verifiable inventories and hashes of source references without publishing decrypted assets.

Recover as much of the following as the actual cooked data permits:

- Packages, paths, assets and dependencies; world/map placement and references; UObjects and reflected properties.
- Static meshes, skeletal meshes, LODs, skeletons, sockets, collision, physics assets, animation sequences, montages, curves, and animation-blueprint behavior where inferable.
- Textures, material instances, material parameter values, material graphs when recoverable, shader maps, compiled shader code and shader/resource bindings.
- Blueprints, widget blueprints, actor/component defaults, event relationships, function graphs/K2 nodes, serialized Blueprint bytecode when present, and associated gameplay references.
- Data tables, sound/audio references, particles/effects, interfaces, input mappings, and relevant configuration.

**Do not promise lossless cooked-to-uncooked recovery.** Shipping cooking strips editor-only metadata, and compiled shader bytecode generally does not reproduce original HLSL/material graphs automatically. Reconstruct functionally equivalent editable graphs when exact originals are absent, track originals versus inferred content, and validate runtime/editor behavior. Preserve original asset/package names and stable identifiers when supported by evidence.

### Blueprint/K2 naming and graph reconstruction

For each recoverable Blueprint class and K2 node, use surrounding clues: serialized names, `FName` tables, imported classes, UFunction/UProperty signatures, pin types, connected operations, VM bytecode, execution flow, referenced assets, and related recovered native C++. Infer meaningful node/function names only with evidence. Retain uncertain nodes under stable placeholders and attach confidence/evidence records. Validate graph flow, pin direction/type/defaults, execution order, latent actions, event dispatchers, and engine-version compatibility. Preserve explicit provenance per recovered Blueprint and per inferred graph section.

### Tool and engine modification permission

If stock UE4.20 editor APIs cannot import or edit cooked packages, **you are authorized to implement custom local tools**: commandlets, importer/exporter utilities, Python/C++ reconstruction pipelines, direct package readers, Blueprint graph builders, or editor extensions. You may also patch the **local engine fork** for cooked-package loading, editor-only flags, serialization compatibility, shader/resource handling, versioned custom serialization, and asset regeneration, provided you keep those changes isolated, documented, testable, and safe to use on copies. Do not bypass missing editor data by claiming an imported cooked runtime package is a fully editable original asset.

Set up automated verification that recovered assets can be enumerated, dependencies resolve, content opens in the editor when possible, Blueprints compile when possible, maps load, and representative gameplay assets behave coherently. Record recoverability by asset and class, failures, missing editor-only information, and inferred replacements in `docs/ASSET_RECOVERY.md` and safe machine-readable reports. Keep actual extracted game assets local and ignored unless explicit redistribution rights are established.

## 7. Live function-match tracking and locally generated README image

Implement a deterministic progress-reporting tool that reads **verified** results from `analysis/functions.json` and generates a static version-controlled SVG at:

`docs/images/byte-match-progress.svg`

Embed it in the main `README.md` with a **relative repository path**, NOT a remote image URL:

```md
![Fortnite 2.5 — Exact Byte-Matched Function Progress](docs/images/byte-match-progress.svg)
```

Make the SVG visually polished but lightweight, inspired by the sort of progress graphics shown by decompilation projects (including `doldecomp/sms`) **without copying their image or relying on `decomp.dev`**. Label it **“Fortnite 2.5 — Exact Function Matches”** and include:

- `exactly matched / identified eligible functions` and a percentage;
- an honest progress bar for *exact* functions only;
- optional independent byte-weighted coverage and category breakdown (never mix them into the function percentage);
- compact source commit/build identifier or verified baseline revision where useful;
- a clearly defined denominator and an accessible text alternative in README.

Use deterministic sorting and formatting, static text and SVG shapes, and no remote fonts/scripts/images. A result may count as `exact` only if the matcher verified raw function bytes. Make generation scriptable (`python tools/progress/generate.py`, or equivalent) and testable from a clean checkout with non-proprietary manifest data; optional `--verify` should fail if the committed image is stale or the manifest inconsistent.

**Update the SVG periodically** during work: after each meaningful batch of verified matches, a material denominator change, and before a related push. Avoid changing it for every insignificant file edit. Update the root `README.md` only for major milestones. Keep the README short: project purpose, SVG, stage state, brief build/limitations references, and a statement that the original game files are not included. Put detailed logs and engineering notes in `docs/`.

Also expose machine-readable and text/HTML (optional) reports distinguishing `exact`, `relocation-equivalent`, `partial`, `unmatched`, and `unimplemented`. Do not inflate percentages by excluding difficult functions without documented classification rules.

## 8. Git, GitHub, and continuous engineering practices

You are working in a **public GitHub repository** and should **commit and push incremental verified work** whenever repository permissions, branch protections, and content rights permit. Use the existing configured remote and branch policy; do not guess a new remote. If direct pushes are disallowed, create a topic branch and PR where authorized. Do not force-push or rewrite shared history unless explicitly instructed.

Before **every** push:

1. Review `git status`, staged paths, diff, size changes, and candidate secrets/credentials.
2. Confirm no reference files from `2.5/`, original EXE, `.pak` files, decrypted/extracted game assets, AES key, IDA database, unlicensed UE source, restricted dependencies, or private service material will be transmitted. Consider already-tracked paths and history, not just ignored files.
3. Build/test affected targets and run verifier/progress generator when appropriate. Document untestable work honestly.
4. Commit coherent increments with useful messages such as `decomp: match movement helper at RVA ...`, `build: add reproducible Win64 matching configuration`, `server: reconstruct authority state dispatch`, `tools: generate exact-match SVG`, or `assets: add local-only Blueprint reconstruction commandlet`.
5. Push only safe, relevant changes. Never claim push success unless the remote confirms it.

Use branches or commits to preserve significant milestones, especially the Stage-1 exact-match baseline before Stage-3 cleanup. Keep generated binary build products local. Do not turn README into a changelog, roadmap dump, or giant function list. Periodically summarize substantive progress in `docs/STATUS.md`: stage, exact counts/denominator, build results, verified server features, engine mismatches, asset recoverability, blockers, and next evidence-backed tasks.

## 9. Autonomous execution and decision rules

- **Act, inspect, implement, build, compare, repair, test, commit and push.** Do not stop at generic pseudocode, scaffolding, or prose when the environment can support actual implementation.
- Prioritize obtaining a working PE inspector, IDA export, compiler-probe, function manifest, matcher, VS2019 solution, and initial exact-match functions before expanding to large systems.
- Use local references first. If external research is available, verify exact tool/engine details from credible sources; avoid blindly importing unrelated game code, third-party binary dumps, or dubious symbol-name claims.
- Favor measurable small batches: one tool capability, one verified function family, one reproducible build fix, one server subsystem, one asset class. Each batch should have a concrete acceptance test.
- Maintain a durable resumable task queue in `docs/STATUS.md`. If a specific function is blocked, record why, select another tractable function, and keep moving; do not loop indefinitely on a single guess.
- Do not fabricate function offsets, matching status, compiler identities, hidden symbols, missing server logic, Blueprint graphs, material graphs, or successful builds.
- Do not weaken exact-match criteria to make statistics look better; do not swap `relocation-equivalent` for `exact` or call a compile-successful binary byte-matched.
- Do not modify the shipped reference executable or mutate the original packaged asset installation. Operate on copies, generated outputs, and editable project files.
- Treat recovered production network/service endpoints as **historical evidence**, not targets to contact. Keep server development in isolated, local testing; do not publish credentials or connect to live Fortnite services.
- When proprietary source/asset publication rights or secrets are uncertain, perform safe local analysis and implementation but withhold publishing the affected material. Report the exact blocker rather than risking a public leak.
- Escalate only when genuinely essential input is missing (e.g., binary, required key, impossible-to-access IDA, unavailable toolchain) or there is a legal/publishing decision the agent cannot responsibly make. State the narrow blocker and continue independent safe work.

## 10. Definition of success and first execution sequence

The long-term end state is a documented, reproducible and evidence-backed decompilation, a separate functional reconstructed server target, a buildable UE4.20 integration, and a restored editable Unreal project with as many locally recoverable assets as possible. Maintain **separate verified success metrics** for each target. A full-file byte match is only achieved when the generated executable and the original have identical hashes; an approximated server or recreated Blueprint is never presented as original exact recovery.

**Start now in this order:**

1. Check worktree, remote, existing files, and verify the exact reference executable path.
2. Add and verify `.gitignore` exclusions for every `2.5` reference directory **before the initial commit**; audit what is tracked or publishable.
3. Fingerprint the PE and toolchain; detect the available IDA automation mechanism; verify engine lineage.
4. Scaffold `FortniteGameCode/FortniteGameCode.sln`, baseline function database, IDA export, matcher, documentation, and offline SVG generator.
5. Perform a real compile/compare iteration on the first few well-supported functions, annotate their original RVAs, and update the generated SVG from verified results.
6. Commit/push only when safe; then continue Stage 1 autonomously toward higher exact-match coverage. Advance into Stages 2, 3, and 4 in that order as their prerequisites are actually established.

**Deliver verified work, not claims of progress.**


### Adaptive Function Reconstruction and Verification

Replace the previous small-batch reconstruction workflow with an adaptive, high-throughput system.

The primary objective is to maximize the number of accurately reconstructed and verified functions per unit of time, without sacrificing correctness or losing traceability.

**1. Adaptive batching**

- Default to batches of 50–100 functions during initial reconstruction.
- Increase to 100–200 for small, independent functions.
- Reduce to 10–40 when functions have complex dependencies, shared class layouts, or require significant investigation.
- Group related functions by class, translation unit, dependency graph, or subsystem.
- Do not arbitrarily limit each Claude turn to 10 functions.
- Do not force large functions into oversized batches merely to satisfy a numerical target.

**2. Separate reconstruction and byte matching**

Operate with independent reconstruction and verification queues.

- Reconstruction: Recover accurate C++ implementations, types, symbols, and original RVAs.
- Compilation: Ensure reconstructed source builds using the required toolchain.
- Matching: Compare compiled functions against the original executable and iteratively resolve differences.

Do not require full byte parity for every function before beginning another reconstruction batch.

**3. Automated batch verification**

- Compile changed translation units incrementally whenever possible.
- Prefer object-level verification over full executable linking when technically valid.
- Perform function-level comparisons automatically for every compiled function.
- Generate machine-readable results for exact matches, partial matches, mismatches, and unresolved functions.
- Preserve detailed compiler and comparison diagnostics.
- If a batch fails compilation, isolate the failing dependency or function group rather than discarding the entire batch.
- Do not report a function as byte-matched without actual verification against its reference machine code.

**4. Intelligent scheduling**

Prioritize functions based on dependency requirements, complexity, expected matching difficulty, and their relevance to recovering neighboring functions.

Initially emphasize broad, accurate reconstruction to establish source coverage and shared type information.

Regularly dedicate work to resolving byte mismatches, particularly those caused by common compiler settings, calling conventions, class layouts, and other systematic issues.

Do not allow the byte-matching backlog to grow indefinitely. Adjust the proportion of reconstruction and verification work based on measured progress.

**5. Optimization and parallelization**

- Permit parallel read-only IDA analysis of independent function groups.
- Permit parallel compilation and comparison where supported by the build environment.
- Avoid concurrent modifications to the same source files.
- Cache unchanged analysis and comparison results.
- Rebuild only affected translation units unless a full rebuild is necessary.
- Detect systemic compiler or build configuration problems before attempting extensive function-specific fixes.

**6. Progress tracking**

Track separately:

- Total identified functions
- Functions reconstructed
- Functions compiling successfully
- Functions with verified byte parity
- Functions requiring further investigation
- Regressions in previously verified matches

Update the repository's progress image using only verified matching results.

Never confuse source coverage, successful compilation, functional equivalence, and exact byte identity.

**7. Continuous improvement**

Measure reconstruction throughput, compilation time, matching rate, and failure rate.

Automatically adjust batch sizes and scheduling strategies when doing so improves verified
