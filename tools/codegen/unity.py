"""Assemble unity translation units from per-item fragments, in recovered source order.

UBT compiles a module's generated code as unity files that #include the .gen.cpp files one
after another. tools/analysis/unity_order.py recovers that order and the unit boundaries
from the CRT initializer table. This writes one FortniteGameCode/Source/Generated/UHT/Unity/
<Package>.<n>.gen.cpp per recovered unit, including each item's fragments in order:

  class   <Class>.gen.cpp                 (StaticRegisterNatives, UFunction creators, constructor)
          Classes/<Pkg>/<Class>.gen.cpp   (IMPLEMENT_CLASS; constructor of a class without UFunctions)
  struct  Structs/<Pkg>/F<Struct>.gen.cpp
  enum    Enums/<Pkg>/<Enum>.gen.cpp           (constructor)

The enums' StaticEnum functions and FCompiledInDeferEnum objects are the exception. UHT makes
StaticEnum file-static, and MSVC compiles file-static functions first, placing their statics in
a block of its own at the start of the unit's .bss. Consecutive enums are adjacent in that
block. Each run of consecutive enum items is therefore compiled as a unit of its own,
<unit>.s<k>.gen.cpp, from Enums/<Pkg>/<Enum>.defer.gen.cpp (the FCompiledInDeferEnum object).

Within the block, MSVC orders file-static functions in a way that depends on the whole unit;
unrelated declarations elsewhere reorder it. So StaticEnum is generated with external linkage
(Enums/<Pkg>/<Enum>.staticenum.gen.cpp). Each unit includes those fragments first, in source
order, before the prologue. External functions and their statics are emitted in definition
order, so this reproduces the block's position, and its order no longer changes with the rest
of the unit. An enum whose StaticEnum inlines the package singleton (static_in_unity) has both
fragments in its unity unit instead.

Only the unity files are compiled. The generators name each manifest entry's unit (unit_of)
so its object is the unity object, like the original build's.

Usage: python tools/codegen/unity.py   (after all generators)
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "codegen"))
from genio import sync_tree  # noqa: E402

GEN = ROOT / "FortniteGameCode" / "Source" / "Generated" / "UHT"
UNITY_DIR = GEN / "Unity"
UNITY_ORDER = ROOT / "analysis" / "unity-order.json"
UNIT_SOURCE = "FortniteGameCode/Source/Generated/UHT/Unity/{unit}.gen.cpp"
UNIT_OBJECT = "Source/Generated/UHT/Unity/{unit}.gen.obj"


def units() -> list[tuple[str, dict]]:
    """[(unit name, unit record)] in table order; names are <Package>.<n>, numbered per package."""
    order = json.loads(UNITY_ORDER.read_text(encoding="utf-8"))
    seen, out = Counter(), []
    for u in order["units"]:
        short = u["package"].rsplit("/", 1)[1]
        seen[short] += 1
        out.append((f"{short}.{seen[short]}", u))
    return out


def item_key(it: dict) -> tuple[str, str]:
    """Lookup key of a unity item. Package-scope delegate names repeat across packages."""
    return (it["kind"], f"{it['package']}:{it['name']}" if it["kind"] == "delegate" else it["name"])


def unit_of() -> dict[tuple[str, str], str]:
    """item_key -> unit name, for kind in class/struct/enum/delegate. A package singleton
    (("package", "/Script/<Pkg>")) whose init.gen.cpp position is not modelled has a unit of its
    own, Packages.<Pkg>."""
    out = {item_key(it): name for name, u in units() for it in u["items"]}
    for name, u in units():
        if "package_init_before" in u:
            out[("package", u["package"])] = name
    for _, u in units():
        out.setdefault(("package", u["package"]), f"Packages.{u['package'].rsplit('/', 1)[1]}")
    return out


def package_init_located() -> set[str]:
    """Packages whose init.gen.cpp position is recovered (tools/analysis/unity_order.py)."""
    return {u["package"] for _, u in units() if "package_init_before" in u}


def static_runs() -> list[tuple[str, list[dict]]]:
    """[(static unit name, enum items)]: runs of consecutive enum items within each unit."""
    out = []
    for name, u in units():
        runs, cur = [], []
        for it in u["items"]:
            if it["kind"] == "enum" and not static_in_unity(it):
                cur.append(it)
            elif cur:
                runs.append(cur)
                cur = []
        if cur:
            runs.append(cur)
        out += [(f"{name}.s{k}", run) for k, run in enumerate(runs, 1)]
    return out


def static_in_unity(it: dict) -> bool:
    """An enum whose StaticEnum inlines the package singleton is compiled in its unity unit,
    after init.gen.cpp, when that position is recovered."""
    return bool(it.get("static_inlined")) and it["package"] in _located()


_LOCATED: set[str] | None = None


def _located() -> set[str]:
    global _LOCATED
    if _LOCATED is None:
        _LOCATED = package_init_located()
    return _LOCATED


def static_unit_of() -> dict[str, str]:
    """Enum name -> the unit its StaticEnum fragment is compiled in."""
    return {it["name"]: name for name, run in static_runs() for it in run}


def fragments(it: dict) -> list[Path]:
    short = it["package"].rsplit("/", 1)[1]
    if it["kind"] == "class":
        return [GEN / f"{it['name']}.gen.cpp", GEN / "Classes" / short / f"{it['name']}.gen.cpp"]
    if it["kind"] == "struct":
        return [GEN / "Structs" / short / f"F{it['name']}.gen.cpp"]
    if it["kind"] == "delegate":
        return [GEN / "Delegates" / short / f"{it['name']}.gen.cpp"]
    if static_in_unity(it):
        return [GEN / "Enums" / short / f"{it['name']}.defer.gen.cpp", GEN / "Enums" / short / f"{it['name']}.gen.cpp"]
    return [GEN / "Enums" / short / f"{it['name']}.gen.cpp"]


def staticenum_fragment(it: dict) -> Path:
    return GEN / "Enums" / it["package"].rsplit("/", 1)[1] / f"{it['name']}.staticenum.gen.cpp"


def head_includes(frags: list[Path], used: set[Path]) -> str:
    """The StaticEnum functions, defined before the prologue in source order (see the module docstring)."""
    frags = [f for f in frags if f.exists()]
    used.update(f.resolve() for f in frags)
    if not frags:
        return ""
    return ("// StaticEnum functions first, with external linkage, in source order: MSVC compiles UHT's\n"
            "// file-static ones first (see tools/codegen/unity.py).\n"
            + "".join(f'#include "../{f.relative_to(GEN).as_posix()}"\n' for f in frags) + "\n")


def main() -> int:
    outputs, used, stats = {}, set(), Counter()
    for name, u in units():
        incs, top = [], []
        init = GEN / "Packages" / f"{u['package'].rsplit('/', 1)[1]}.init.gen.cpp"
        for k, it in enumerate(u["items"]):
            if u.get("package_init_before") == k and init.exists():
                incs.append(f'#include "../{init.relative_to(GEN).as_posix()}"  // init.gen.cpp position recovered')
                used.add(init.resolve())
            for frag in fragments(it):
                if frag.exists():
                    incs.append(f'#include "../{frag.relative_to(GEN).as_posix()}"')
                    used.add(frag.resolve())
            if it["kind"] == "enum" and static_in_unity(it):
                top.append(staticenum_fragment(it))
        if not incs:
            continue
        outputs[UNITY_DIR / f"{name}.gen.cpp"] = (
            "// Generated by tools/codegen/unity.py. Do not edit by hand.\n"
            f"// Unity translation unit {name} of {u['package']}: the fragments of {len(u['items'])} UHT items in the\n"
            f"// source order recovered from .CRT$XCU entries {u['table_range'][0]}..{u['table_range'][1] - 1}"
            " (analysis/unity-order.json).\n\n"
            + head_includes(top, used) +
            "// Stand-in for the engine headers every unity file starts with (creates the plain .bss first).\n"
            '#include "FortniteGameCode/UnityPrologue.h"\n\n' + "\n".join(incs) + "\n")
        stats["units"] += 1
        stats["fragments"] += len(incs)
    for name, run in static_runs():
        incs = []
        for it in run:
            frag = GEN / "Enums" / it["package"].rsplit("/", 1)[1] / f"{it['name']}.defer.gen.cpp"
            if frag.exists():
                incs.append(f'#include "../{frag.relative_to(GEN).as_posix()}"')
                used.add(frag.resolve())
        if incs:
            outputs[UNITY_DIR / f"{name}.gen.cpp"] = (
                "// Generated by tools/codegen/unity.py. Do not edit by hand.\n"
                f"// StaticEnum unit {name}: the StaticEnum functions and registration objects of {len(run)}\n"
                "// consecutive enum(s), compiled apart from their unity unit (see tools/codegen/unity.py).\n\n"
                + head_includes([staticenum_fragment(it) for it in run], used) +
                '#include "FortniteGameCode/UnityPrologue.h"\n\n' + "\n".join(incs) + "\n")
            stats["static_units"] += 1
    # Package singletons whose init.gen.cpp position is not modelled: a unit each.
    for frag in sorted((GEN / "Packages").glob("*.init.gen.cpp")):
        short = frag.name[:-len(".init.gen.cpp")]
        if frag.resolve() in used:
            continue
        outputs[UNITY_DIR / f"Packages.{short}.gen.cpp"] = (
            "// Generated by tools/codegen/unity.py. Do not edit by hand.\n"
            f"// Package singleton of /Script/{short}; its init.gen.cpp position in the module's unity files is\n"
            "// not modelled, so it is compiled on its own.\n\n"
            '#include "FortniteGameCode/UnityPrologue.h"\n\n'
            f'#include "../{frag.relative_to(GEN).as_posix()}"\n')
        used.add(frag.resolve())
        stats["package_units"] += 1
    # Every generated fragment must belong to a unit; anything else would silently not compile.
    loose = [p for d in (GEN, GEN / "Classes", GEN / "Structs", GEN / "Enums", GEN / "Delegates", GEN / "Packages")
             if d.exists()
             for p in (d.glob("*.gen.cpp") if d == GEN else d.rglob("*.gen.cpp")) if p.resolve() not in used]
    stats["files_written"], stats["files_removed"] = sync_tree(UNITY_DIR, outputs)
    print(dict(stats), "fragments outside any unit:", len(loose), [p.name for p in loose[:5]])
    return 1 if loose else 0


if __name__ == "__main__":
    raise SystemExit(main())
