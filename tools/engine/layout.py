"""Class layouts of Fortnite's engine fork where public UE4.20.0 declares them differently.

Each entry of PATCHES replaces whole lines of an engine file, one line for one, so that every
other line keeps its number (__LINE__, analysis/engine-lines.json). An original line is named
by a hash of its stripped text, so the engine's text stays in the local tree, and a patch
whose line has moved or changed stops the build instead of applying elsewhere. A replacement
is literal text (placeholders, emptied macros), DEVIRTUALIZE (the original line without its
first `virtual `), or a tuple of original line numbers and literals, joined by spaces (moving
a declaration: the text comes from the local tree too). Every entry records its evidence
(docs/ENGINE_DIFFERENCES.md has the measurements).

Headers are patched through a mirror. Every file of an include root that holds a patched
header is copied to the mirror (MIRROR, below: local-output/, as long as the reference's root), and the response
file's /I of the root and the force-included wrappers' absolute includes point at the copy.
The whole root is copied because MSVC looks up a quote include in the including file's
physical directory and those of the files that included it before the /I paths: a single
copied file would still find its neighbours, and they theirs, in the original tree. build.py
passes /showIncludes and fails a unit that opens an original file of a mirrored root.

The copies carry no #line directive. A copied header's __FILE__ is therefore its path in the
mirror (it reaches objects only through PURE_VIRTUAL stubs and the like, whose literal the
reference holds under D:\\Build\\++FN25\\Sync anyway). A #line naming the original instead
changes the order in which MSVC 19.00 allocates a unit's static data, also for definitions in
.cpp files: with the files unchanged, a #line in the mirrored headers alone moved Slate's
EditorLayoutsSectionName (LayoutService.cpp) to the front of its .data; with the patches, it
moved eight of Engine unit 14's first statics (FExternalTextureRegistry::Get depends on their
order), where without it two adjacent ints swap. Without #line and without patches the mirror
leaves objects as they were.
Lambda and anonymous-namespace names follow the translation unit, not the header's path.
Patched .cpp files are compiled through tools/engine/overlay.py's overlays. The engine tree
itself is never modified.

    python tools/engine/layout.py            # check every patch against the local engine tree
"""
from __future__ import annotations

import hashlib
import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ue_target as T  # noqa: E402

REFERENCE_SOURCE_ROOT = r"D:\Build\++FN25\Sync\Engine\Source"


def _mirror_dir() -> Path:
    """Where the mirror lives: a directory whose absolute path is exactly as long as the
    reference's Engine/Source root, so that a mirrored header's __FILE__ (the root, then the
    path below it) has the reference's length and its literal the reference's size. Under the
    ignored local-output/ when that fits, else in the build directory (lengths then differ)."""
    base = T.ROOT / "local-output"
    n = len(REFERENCE_SOURCE_ROOT) - len(str(base)) - 1
    if n >= 1:
        return base / ("mirror" + "_" * max(0, n - 6))[:n]
    return T.BUILD_DIR / "overlay" / "include"


MIRROR = _mirror_dir()
HEADER_SUFFIXES = {".h", ".inl", ".hpp"}
MIRROR_FORMAT = 2          # what a mirrored file holds besides its patches (2: nothing)

DEVIRTUALIZE = "-virtual"

# path relative to Engine/Source -> {line: (hash of the original stripped line, replacement)}
PATCHES: dict[str, dict[int, tuple[str, object]]] = {
    # UObject has no Serialize(FStructuredArchive::FRecord) overload: in the reference, every
    # UObject-derived vtable slot from Serialize(FArchive&) on is one slot (8 bytes) earlier
    # than ours, and every slot before it at the same place (ENGINE_DIFFERENCES #14). The
    # overload is the one at our slot 0xA0, between FinishDestroy and Serialize(FArchive&).
    # It is made non-virtual rather than removed, and so are UHT's per-class overrides of it
    # (324 generated classes, and UTextBuffer): the functions stay declared and defined, only
    # their vtable slots go. Removing the declarations as well changed the order in which MSVC
    # emits other units' vtables and literals (FMediaAssetsModule's vtables moved from before
    # the MEDIA literal, where the reference has them, to after LogMediaAssets) and cost the
    # functions that neighbours placed there.
    "Runtime/CoreUObject/Public/UObject/Object.h": {
        261: ("d1b6089d5612", DEVIRTUALIZE),
    },
    "Runtime/CoreUObject/Public/UObject/ObjectMacros.h": {
        1386: ("415ec74840c2", "#define DECLARE_FSTRUCTUREDARCHIVE_SERIALIZER( TClass, API ) "
                               "API void Serialize(FStructuredArchive::FRecord Record);"),
    },
    # IAssetRegistry has no such overload either: in the reference's IAssetRegistry vtable of
    # UAssetRegistryImpl, Tick is followed by one Serialize adjustor thunk, then
    # GetAllocatedSize; ours has a thunk for each overload. (A pure virtual cannot be made
    # non-virtual; UAssetRegistryImpl keeps its non-virtual one from the macro.)
    "Runtime/AssetRegistry/Public/IAssetRegistry.h": {
        350: ("4595bc70f16c", ""),
    },

    # FArchive has the interface from before structured archives (ENGINE_DIFFERENCES #19). The
    # 50 reference vtables derived from it end after 44 slots, ours after 57: no IsProxyOf
    # (Precache follows DetachBulkData), an empty function where GetCacheableArchive is, after
    # ResetCustomVersions one that sets its bool& to false and returns true (UE3's
    # IsCloseComplete), virtual IsFilterEditorOnly and IsSaveGame (their bodies test bits 23 and
    # 24 of the flags), and no Push/PopSerializedProperty, Reset or the 12 Set* setters. Its
    # members end 8 bytes earlier: FArchive::FArchive (0x011D0DA0) stores every member ours
    # stores except SerializedPropertyChain, at 0x80.
    "Runtime/Core/Public/Serialization/Archive.h": {
        681: ("ea345fd103a1", DEVIRTUALIZE),                       # IsProxyOf
        895: ("b5dde4eea16f", DEVIRTUALIZE),                       # GetCacheableArchive
        899: ("da39a3ee5e6b", "\tvirtual void FNLayout_AfterGetArchetypeFromLoader() {}"),
        1074: ("da39a3ee5e6b", "\tvirtual bool FNLayout_IsCloseComplete(bool& bHasError) { bHasError = false; return true; }"),
        1122: ("3e04ff877320", ("virtual", 1122)),                 # IsFilterEditorOnly
        1142: ("334e9e568a83", ("virtual", 1142)),                 # IsSaveGame
        1239: ("1a02973ec602", "\t\treturn nullptr;"),            # GetSerializedPropertyChain: no chain
        1253: ("99c0456eebad", DEVIRTUALIZE),                      # PushSerializedProperty
        1261: ("8460e2d0d499", DEVIRTUALIZE),                      # PopSerializedProperty
        1290: ("531dad3515eb", DEVIRTUALIZE),                      # Reset
        1468: ("05eb072e90cf", DEVIRTUALIZE), 1475: ("787026ff5949", DEVIRTUALIZE),
        1482: ("7607c84712e9", DEVIRTUALIZE), 1489: ("d0984275ed4c", DEVIRTUALIZE),
        1496: ("f597214c10e6", DEVIRTUALIZE), 1504: ("ed5b0eb9e634", DEVIRTUALIZE),
        1511: ("be07f80f8056", DEVIRTUALIZE), 1519: ("e71899f77ccb", DEVIRTUALIZE),
        1527: ("6149853d85b8", DEVIRTUALIZE), 1535: ("f33c32e1143c", DEVIRTUALIZE),
        1540: ("c1d1028fc0de", DEVIRTUALIZE), 1545: ("08d12960f55f", DEVIRTUALIZE),
        1646: ("d8d4c49a6d59", ""),                                # SerializedPropertyChain
    },
    "Runtime/Core/Public/Serialization/ArchiveProxy.h": {
        241: ("df0a6ee7578a", DEVIRTUALIZE), 246: ("1fd0232db145", DEVIRTUALIZE),
        258: ("a216a65d8c7b", DEVIRTUALIZE), 263: ("5a9389eeb338", DEVIRTUALIZE),
    },
    "Runtime/Core/Public/Serialization/ArchiveFromStructuredArchive.h": {
        33: ("5a9389eeb338", DEVIRTUALIZE),
    },
    "Runtime/Core/Public/Serialization/BitWriter.h": {
        160: ("89d3f28e8eb2", "\tvoid Reset();"),               # overrode FArchive::Reset
    },
    # The chain's uses: a local null chain in the four functions that keep it (their chain
    # branches become dead), nothing elsewhere.
    "Runtime/Core/Private/Serialization/Archive.cpp": {
        40: ("ac1d64ca1443", ""), 60: ("ac1d64ca1443", ""), 61: ("33018eb129b0", ""),
        85: ("33018eb129b0", ""), 115: ("6afb71a8cdda", ""), 168: ("6afb71a8cdda", ""),
        169: ("ac1d64ca1443", ""),
        241: ("60ba4b2daa4e", "{ const FArchiveSerializedPropertyChain* SerializedPropertyChain = nullptr;"),
        255: ("60ba4b2daa4e", "{ FArchiveSerializedPropertyChain* SerializedPropertyChain = nullptr;"),
        285: ("60ba4b2daa4e", "{ FArchiveSerializedPropertyChain* SerializedPropertyChain = nullptr;"),
        301: ("60ba4b2daa4e", "{ FArchiveSerializedPropertyChain* SerializedPropertyChain = nullptr;"),
    },

    # Classes derived from UObject whose own virtuals differ (ENGINE_DIFFERENCES #16-#18). Each was
    # aligned slot by slot against reference vtables of the class, by the bodies the slots hold.
    # A virtual the reference lacks is made non-virtual (its callers still compile); a slot the
    # reference has and public 4.20 does not is declared where the reference has it. Where no
    # name is known it is a placeholder, FNLayout_*, with the body the reference's slot holds
    # when that body is trivial.

    # USceneComponent::UpdateBounds is not virtual: the reference's slots after CalcBounds hold
    # CalcBoundingCylinder (it squares the bounds' extents), ShouldCollideWhenPlacing
    # (return false, overridden by 13 of 95 scene-component vtables) and UpdatePhysicsVolume.
    # UPrimitiveComponent's override goes with it: its own virtuals are all one slot earlier.
    "Runtime/Engine/Classes/Components/SceneComponent.h": {
        1059: ("d3d4f87e4fb0", DEVIRTUALIZE),
    },
    "Runtime/Engine/Classes/Components/PrimitiveComponent.h": {
        807: ("33bb4619d110", DEVIRTUALIZE),
    },
    # UActorComponent::OnRep_IsActive is not virtual: the reference's execOnRep_IsActive
    # (0x023C9B90) jumps to it directly, and Activate is the class's first slot.
    "Runtime/Engine/Classes/Components/ActorComponent.h": {
        282: ("57d798cba573", DEVIRTUALIZE),
    },
    # AActor has no virtual RewindForReplay: in all 376 reference AActor vtables
    # PreReplicationForReplay (overridden by ACharacter) is followed by OnRep_Instigator, which
    # AActor::execOnRep_Instigator (0x023F9910) calls at that slot.
    "Runtime/Engine/Classes/GameFramework/Actor.h": {
        507: ("f9505f2e6d84", DEVIRTUALIZE),
    },
    # AController declares InitNavigationControl and UpdateNavigationComponents after
    # FailedToSpawnPawn, with bodies (FindComponentByClass, then a virtual call on the
    # component); public 4.20 moved them, deprecated and empty, to the end of the class.
    "Runtime/Engine/Classes/GameFramework/Controller.h": {
        290: ("06c7fc1d55e2", (290, 361, 369)),
        360: ("a3b5841e4c54", ""),
        361: ("19b16de64c29", ""),
        368: ("a33dad9df3cf", ""),
        369: ("1262a37a1392", ""),
    },
    # UPathFollowingComponent has three virtuals of its own after OnActorBump (an empty one, one
    # clearing a flag bit, an empty one: the agent callbacks OnMoveBlockedBy, OnStartedFalling and
    # OnLanded, which public 4.20 declares in IPathFollowingAgentInterface), and OnNewPawn is
    # not virtual (Reset is followed by ShouldCheckPathOnResume).
    "Runtime/AIModule/Classes/Navigation/PathFollowingComponent.h": {
        385: ("829fac108be4", "virtual void FNLayout_OnMoveBlockedBy() {} virtual void FNLayout_OnStartedFalling() {} "
                              "virtual void FNLayout_OnLanded() {}"),
        602: ("7a835ccd9fd4", DEVIRTUALIZE),
    },
    # UEngine: two virtuals after ShouldThrottleCPUUsage (a function testing globals, then an
    # empty one; every following slot up to GetSpriteCategoryIndex then holds the same trivial
    # body as ours), and InitializeEyeTrackingDevice, HandleServerTravelCommand and
    # HandleSayCommand are not virtual (InitializeHMDDevice is followed by RecordHMDAnalytics,
    # HandleStreamMapCommand by HandleDisconnectCommand).
    "Runtime/Engine/Classes/Engine/Engine.h": {
        2076: ("583dd3c7e3c9", (2076, "virtual void FNLayout_AfterShouldThrottleCPUUsage1() {} "
                                     "virtual void FNLayout_AfterShouldThrottleCPUUsage2() {}")),
        2598: ("b61b5685a270", DEVIRTUALIZE),
        2790: ("bb4de198c1f4", DEVIRTUALIZE),
        2793: ("aeadfb0317b3", DEVIRTUALIZE),
    },
    # ANavigationData: ProjectPoint is a virtual of the class itself, after
    # GetRandomPointInNavigableRadius (the reference's slot holds ARecastNavMesh::ProjectPoint:
    # 430 bytes, 6 differing outside relocations); public 4.20 declares it in
    # INavigationDataInterface as well, so the override goes to that interface's vtable. A
    # placeholder takes the slot. CalcPathLength precedes CalcPathCost: the reference's
    # UNavigationSystemV1::GetPathLength calls slot 0x6D8 and GetPathCost 0x6E0.
    "Runtime/NavigationSystem/Public/NavigationData.h": {
        800: ("da39a3ee5e6b", "virtual bool FNLayout_ProjectPoint() const { return false; }"),
        812: ("9c1a6bdbe3a6", (817,)),
        817: ("6e4ebb867ec5", (812,)),
    },
    # UMovieSceneTrack: a virtual returning false after SupportsMultipleRows, overridden by none
    # of the 37 reference track vtables.
    "Runtime/MovieScene/Public/MovieSceneTrack.h": {
        247: ("da39a3ee5e6b", "virtual bool FNLayout_AfterSupportsMultipleRows() const { return false; }"),
    },
}


def line_hash(line: str) -> str:
    return hashlib.sha1(line.strip().encode("utf-8", errors="surrogateescape")).hexdigest()[:12]


def patch_text(rel: str, text: str) -> str:
    """text (an engine file's decoded contents) with its patches applied."""
    patches = PATCHES.get(rel)
    if not patches:
        return text
    lines = text.split("\n")
    original = list(lines)
    for n, (h, new) in sorted(patches.items()):
        if n > len(lines) or line_hash(lines[n - 1]) != h:
            raise SystemExit(f"layout patch {rel}:{n} does not match the engine tree "
                             f"({line_hash(lines[n - 1]) if n <= len(lines) else 'past the end'} != {h})")
        lines[n - 1] = replacement(original, n, new) + ("\r" if lines[n - 1].endswith("\r") else "")
    return "\n".join(lines)


def replacement(original: list[str], n: int, new) -> str:
    """The text that replaces line n (1-based) of original."""
    if new == DEVIRTUALIZE:
        line = original[n - 1].rstrip("\r")
        if "virtual " not in line:
            raise SystemExit(f"layout patch line {n} has no virtual to remove")
        return line.replace("virtual ", "", 1).replace(" override", "", 1)   # nothing to override
    if isinstance(new, tuple):
        return " ".join(original[x - 1].strip() if isinstance(x, int) else x for x in new)
    return new


def engine_rel(path: Path) -> str | None:
    """path relative to Engine/Source, posix-style, or None outside it."""
    try:
        return Path(os.path.normpath(path)).relative_to(Path(os.path.normpath(T.ENGINE_SOURCE))).as_posix()
    except ValueError:
        return None


def roots() -> list[str]:
    """The include roots that hold a patched header (their module's Public or Classes
    directory)."""
    out = []
    for rel in PATCHES:
        if Path(rel).suffix in HEADER_SUFFIXES:
            parts = rel.split("/")
            at = next(i for i, p in enumerate(parts) if p in ("Public", "Classes"))
            root = "/".join(parts[:at + 1])
            if root not in out:
                out.append(root)
    return sorted(out)


def mirrored_root(path: str | Path) -> str | None:
    """The mirrored root an include directory or file (absolute, or relative to Engine/Source)
    lies in, or None."""
    p = Path(path)
    if not p.is_absolute():
        p = T.ENGINE_SOURCE / p
    rel = engine_rel(p)
    if rel is None:
        return None
    low = rel.lower()
    for r in roots():
        if low == r.lower() or low.startswith(r.lower() + "/"):
            return r
    return None


def holds_mirrored_root(path: str | Path) -> bool:
    """Whether an include directory (absolute, or relative to Engine/Source) is an ancestor of
    a mirrored root, so that "<rest of the root>/..." includes through it reach the root."""
    p = Path(path)
    if not p.is_absolute():
        p = T.ENGINE_SOURCE / p
    rel = engine_rel(p)
    if rel is None:
        return False
    low = "" if rel == "." else rel.lower()
    return any(low == "" or r.lower().startswith(low + "/") for r in roots())


def mirror_path(path: str | Path) -> Path:
    """Where an include directory or file of a mirrored root is in the mirror."""
    p = Path(path)
    if not p.is_absolute():
        p = T.ENGINE_SOURCE / p
    return MIRROR / engine_rel(p)


def _encode(raw: bytes) -> tuple[bytes, str]:
    """(byte order mark, decoded text) of an engine file."""
    if raw.startswith(b"\xff\xfe"):
        return raw[:2], raw[2:].decode("utf-16-le")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[:3], raw[3:].decode("utf-8", errors="surrogateescape")
    return b"", raw.decode("utf-8", errors="surrogateescape")


def mirrored_file(src: Path) -> bytes:
    """The mirror's copy of one file of a mirrored root: the file itself, with its patches."""
    raw = src.read_bytes()
    rel = engine_rel(src)
    if src.suffix.lower() not in HEADER_SUFFIXES or rel not in PATCHES:
        return raw
    bom, text = _encode(raw)
    text = patch_text(rel, text)
    if bom == b"\xff\xfe":
        return bom + text.encode("utf-16-le")
    return bom + text.encode("utf-8", errors="surrogateescape")


_LOCK = threading.Lock()
_STAMP_LOCK = threading.Lock()
_PREPARED = False
_STAMP: Path | None = None


def stamp() -> Path:
    """A file whose contents name the patches and roots: rewritten only when they change, so
    that build.py recompiles the units that search a mirror exactly then."""
    global _STAMP
    with _STAMP_LOCK:
        if _STAMP is None:
            path = MIRROR / ".patches"
            text = repr((MIRROR_FORMAT, roots(), sorted((k, sorted(v.items())) for k, v in PATCHES.items())))
            digest = hashlib.sha1(text.encode()).hexdigest() + "\n"
            if not path.exists() or path.read_text() != digest:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(digest)
            _STAMP = path
    return _STAMP


def prepare() -> list[Path]:
    """Write the mirrors (only files that changed). The mirrored root directories."""
    global _PREPARED
    with _LOCK:
        if not _PREPARED:
            stamp()
            for r in roots():
                base = T.ENGINE_SOURCE / r
                for dirpath, _, names in os.walk(base):
                    for n in names:
                        src = Path(dirpath) / n
                        dst = mirror_path(src)
                        data = mirrored_file(src)
                        if not dst.exists() or dst.read_bytes() != data:
                            dst.parent.mkdir(parents=True, exist_ok=True)
                            dst.write_bytes(data)
            _PREPARED = True
    return [MIRROR / r for r in roots()]


def check() -> int:
    """Check every patch against the engine tree; print what each changes."""
    bad = 0
    for rel, patches in sorted(PATCHES.items()):
        src = T.ENGINE_SOURCE / rel
        _, text = _encode(src.read_bytes())
        lines = text.split("\n")
        for n, (h, new) in sorted(patches.items()):
            got = line_hash(lines[n - 1]) if n <= len(lines) else None
            ok = got == h
            bad += not ok
            print(f"{'ok ' if ok else 'BAD'} {rel}:{n} -> {new!r}")
    print("mirrored roots:", ", ".join(roots()))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(check())
