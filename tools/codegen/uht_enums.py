"""Generate UHT-shaped UENUM registration code from the reference's own reflection data.

UnrealHeaderTool 4.20 (CodeGenerator.cpp, ExportGeneratedEnumInitCode) emits per enum:

  static UEnum* <Enum>_StaticEnum()                file-static; static Singleton, GetStaticEnum(...)
  static FCompiledInDeferEnum Z_CompiledInDeferEnum_UEnum_<Enum>(...)
  uint32 Get_Z_Construct_UEnum_<Pkg>_<Enum>_CRC()  unreferenced without hot reload
  UEnum* Z_Construct_UEnum_<Pkg>_<Enum>()           static ReturnEnum, local Enumerators[] and EnumParams

and a .gen.cpp lists its enums before its structs, delegates and classes.

Layout. ReturnEnum is a COMDAT .bss static, laid out in source order with the rest of its
header. MSVC compiles file-static functions first, so the Singletons of all <Enum>_StaticEnum
functions form a separate block at the start of the unity translation unit's .bss, far from
the ReturnEnums. Within that block the order of file-static functions depends on the whole
translation unit: unrelated declarations elsewhere in it reorder them. The reference's block
mostly follows the recovered source order.

So each enum has three fragments:
  <Enum>.gen.cpp             the constructor, included at the enum's recovered position;
  <Enum>.staticenum.gen.cpp  <Enum>_StaticEnum with external linkage (UHT: static), which
                             tools/codegen/unity.py includes at the top of the unit, in source
                             order, before the prologue. MSVC emits external functions and their
                             statics in definition order, so this reproduces the block's position
                             and keeps its order stable. The code is the same;
  <Enum>.defer.gen.cpp       the FCompiledInDeferEnum object, at the enum's position.

Identification uses no bytes of the function each fact is checked against:

* Z_Construct_UEnum_*: a 47-byte UHT singleton whose callee is ConstructUEnum, i.e. the callee
  shared by the singletons that StaticEnum functions register.
* EnumParams: the only FEnumParams record in .data with this NameUTF8 and package OuterFunc.
* <Enum>_StaticEnum: 55-byte shape (package singleton called out of line). LEA-loads the
  constructor and TEXT("<Enum>"). Its 85-byte form inlines the package singleton and is
  left out, as for structs.
* FCompiledInDeferEnum initializer: the only 66-byte registration initializer LEA-loading it.

Get_..._CRC is not emitted: nothing references it in a shipping build, /OPT:REF removed it,
and its constant is therefore not in the image.

Outputs: FortniteGameCode/Source/Generated/UHT/Enums/<Package>/<Enum>.*.gen.cpp (fragments),
analysis/functions-uht-enums.json, analysis/functions-uht-staticenum.json,
analysis/functions-uht-enum-defer.json and analysis/uht-enum-symbols.json.

Usage: python tools/codegen/uht_enums.py
"""
from __future__ import annotations

import bisect
import json
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "matching"))
sys.path.insert(0, str(ROOT / "tools" / "codegen"))
from compare import load_decrypted  # noqa: E402
from unity import UNIT_OBJECT, static_in_unity, static_unit_of, unit_of  # noqa: E402
from genio import sync_tree  # noqa: E402
from manifest_io import dump_compact  # noqa: E402
from pe import PEImage  # noqa: E402
from uht_creators import CREATOR_SIZE, MASK, TEMPLATE  # noqa: E402
from uht_structs import CID_FIELDS, CID_TEMPLATE, cstr, shape, wstr  # noqa: E402
from unwind import UNW_FLAG_CHAININFO, parse_unwind  # noqa: E402

GEN_DIR = ROOT / "FortniteGameCode" / "Source" / "Generated" / "UHT" / "Enums"
CTOR_MANIFEST = ROOT / "analysis" / "functions-uht-enums.json"
SE_MANIFEST = ROOT / "analysis" / "functions-uht-staticenum.json"
DEFER_MANIFEST = ROOT / "analysis" / "functions-uht-enum-defer.json"
SYMBOLS = ROOT / "analysis" / "uht-enum-symbols.json"
SE_TEMPLATE = bytes.fromhex(
    "4883ec28488b05000000004885c07522e800000000488bd04c8d0500000000488d0d00000000e800000000"
    "488905000000004883c428c3")
SE_FIELDS = {"singleton": (0x07, "rel"), "package": (0x11, "rel"), "name": (0x1B, "rel"),
             "ctor": (0x22, "rel"), "get_static_enum": (0x27, "rel"), "store": (0x2E, "rel")}
OBJECT_FLAGS = {0x45: "RF_Public|RF_Transient|RF_MarkAsNative", 0x41: "RF_Public|RF_Transient"}
CPP_FORM = {0: "UEnum::ECppForm::Regular", 1: "UEnum::ECppForm::Namespaced", 2: "UEnum::ECppForm::EnumClass"}
PARAMS_SIZE = 0x48


def main() -> int:
    assert len(SE_TEMPLATE) == 55
    img = PEImage()
    dimg = load_decrypted(img)
    if dimg is None:
        print("needs the validated decrypted image", file=sys.stderr)
        return 1
    base = img.image_base
    text = img.sections[0]
    allrf = {rf.begin: rf for rf in img.runtime_functions()}
    primary = sorted(b for b, rf in allrf.items() if text.contains_rva(b)
                     and not parse_unwind(img, rf.unwind).flags & UNW_FLAG_CHAININFO)
    stats = Counter()

    def read(rva: int, n: int) -> bytes | None:
        try:
            return dimg.read(rva, n)
        except ValueError:
            return None

    # Every 47-byte UHT singleton: (ReturnX slot, params record, callee).
    singletons = {}
    for p in primary:
        if allrf[p].end - p != CREATOR_SIZE:
            continue
        b = read(p, CREATOR_SIZE)
        if b is None or any(b[i] != TEMPLATE[i] for i in range(CREATOR_SIZE) if i not in MASK):
            continue
        singletons[p] = tuple(p + nxt + struct.unpack_from("<i", b, at)[0]
                              for at, nxt in ((7, 0xB), (0x13, 0x17), (0x1F, 0x23)))

    static_enums, defer_by_target = {}, defaultdict(list)
    for p in primary:
        n = allrf[p].end - p
        if n == len(SE_TEMPLATE):
            f = shape(read(p, n), p, SE_TEMPLATE, SE_FIELDS)
            if f and f["store"] == f["singleton"] and f["ctor"] in singletons:
                static_enums[f["ctor"]] = dict(f, rva=p)
        elif n == len(CID_TEMPLATE):
            f = shape(read(p, n), p, CID_TEMPLATE, CID_FIELDS)
            if f:
                defer_by_target[f["staticstruct"]].append(p)
    gse = Counter(f["get_static_enum"] for f in static_enums.values()).most_common(1)[0][0]
    static_enums = {k: v for k, v in static_enums.items() if v["get_static_enum"] == gse}
    construct_enum = Counter(singletons[c][2] for c in static_enums).most_common(1)[0][0]

    # Package singletons: the call targets of plain StaticEnums, named by FPackageParams.
    construct_package = Counter(singletons[f["package"]][2] for f in static_enums.values()
                                if f["package"] in singletons).most_common(1)[0][0]
    packages = {}
    for rva, (_, rec, callee) in singletons.items():
        if callee == construct_package:
            name = cstr(img, struct.unpack("<Q", img.read(rec, 8))[0] - base)
            if name and name.startswith("/Script/"):
                packages[rva] = name

    # FEnumParams candidates in .data by (NameUTF8, OuterFunc).
    ds = next(s for s in img.sections if s.name == ".data")
    data = img.read(ds.rva, ds.rawsize)
    records = defaultdict(list)
    for off in range(0, len(data) - PARAMS_SIZE, 8):
        outer, dyn, nameptr, oflags = struct.unpack_from("<QQQI", data, off)
        if outer - base in packages and dyn == 0 and oflags in OBJECT_FLAGS and base <= nameptr < base + img.size_of_image:
            n = cstr(img, nameptr - base)
            if n:
                records[(n, outer - base)].append(ds.rva + off)

    registered_defer = {}
    inlined_static = {}
    for u in json.loads((ROOT / "analysis" / "unity-order.json").read_text(encoding="utf-8"))["units"]:
        for it in u["items"]:
            if it["kind"] == "enum":
                registered_defer[it["name"]] = int(it["compiled_in_defer"], 16)
            if it["kind"] == "enum" and static_in_unity(it):
                p = int(it["static_enum"], 16)
                try:
                    b = dimg.read(p, 0x60)
                except ValueError:
                    continue
                # the constructor is the LEA rcx target just before the GetStaticEnum call
                for i in range(len(b) - 7, -1, -1):
                    if b[i:i + 3] == b"\x48\x8d\x0d":
                        inlined_static[p + i + 7 + struct.unpack_from("<i", b, i + 3)[0]] = p
                        break
    enums = []
    for ctor, (rf, rec, callee) in singletons.items():
        if callee != construct_enum:
            continue
        stats["enum_constructors"] += 1
        outer, dyn, nameptr, oflags, disp, form, cpptype, enumerators, num = struct.unpack(
            "<QI4xQI4xQB7xQQi4x", img.read(rec, PARAMS_SIZE))
        name = cstr(img, nameptr - base)
        pkg = outer - base
        if name is None or pkg not in packages or len(records.get((name, pkg), [])) != 1:
            stats["record_not_unique"] += 1
            continue
        values = []
        for i in range(num):
            np_, val = struct.unpack("<Qq", img.read(enumerators - base + 16 * i, 16))
            values.append((cstr(img, np_ - base), val))
        if any(v[0] is None for v in values):
            stats["enumerator_names_unreadable"] += 1
            continue
        se = static_enums.get(ctor)
        if se is None and ctor in inlined_static:
            # 85-byte StaticEnum that inlines the package singleton; compiled after init.gen.cpp in
            # its unity unit when that position is recovered. Located through its
            # FCompiledInDeferEnum initializer (analysis/unity-order.json).
            p = inlined_static[ctor]
            se = {"rva": p, "end": allrf[p].end, "name": None, "package": pkg, "inlined": True}
        if se is not None and not se.get("inlined") and wstr(img, se["name"]) != name:
            se = None
        if se is not None and not se.get("inlined") and se["package"] != pkg:
            se = None
        # The FCompiledInDeferEnum initializer of every enum is in the CRT table (unity order),
        # whatever form its StaticEnum takes.
        defer = [registered_defer[name]] if name in registered_defer else (
            defer_by_target.get(se["rva"], []) if se else [])
        enums.append(dict(ctor=ctor, ctor_end=allrf[ctor].end, rec=rec, name=name, pkg=pkg,
                          pkg_name=packages[pkg], oflags=oflags, disp=disp - base if disp else 0,
                          form=form, cpptype=cstr(img, cpptype - base), values=values,
                          enumerators=enumerators - base, se=se,
                          defer=defer[0] if len(defer) == 1 else None))

    outputs: dict[Path, str] = {}
    ctor_entries, se_entries, defer_entries, symbols = [], [], [], {}
    for pkg_rva, pname in packages.items():
        symbols[f"?Z_Construct_UPackage_{pname.replace('/', '_')}@@YAPEAVUPackage@@XZ"] = [
            f"0x{pkg_rva:08X}", "package-params"]
    units, static_units = unit_of(), static_unit_of()
    for e in sorted(enums, key=lambda e: e["ctor"]):
        short = e["pkg_name"].rsplit("/", 1)[1]
        pkg_fn = f"Z_Construct_UPackage_{e['pkg_name'].replace('/', '_')}"
        name, zc = e["name"], f"Z_Construct_UEnum_{short}_{e['name']}"
        unit = units.get(("enum", name))
        if unit is None:
            stats["enum_not_in_unity_order"] += 1
            continue
        se, cid = e["se"], e["defer"]
        disp_expr, disp_decl = "nullptr", ""
        if e["disp"]:
            disp_expr = f"Unrecovered_EnumDisplayNameFn_0x{e['disp']:08X}"
            disp_decl = f"FText {disp_expr}(int32);  // RVA 0x{e['disp']:08X}\n"
        se_note = (f"\t// Original FortniteClient-Win64-Shipping.exe: RVA 0x{se['rva']:08X} (end 0x{se.get('end', se['rva'] + len(SE_TEMPLATE)):08X})\n"
                   f"\t// Recovery: confirmed (TEXT(\"{name}\"), {zc}) | Matching: see analysis/functions-uht-staticenum.json\n"
                   if se else "\t// StaticEnum: not the plain 55-byte form in the reference (package singleton inlined)\n")
        cid_note = f"\t// Original dynamic initializer: RVA 0x{cid:08X}\n" if cid else ""
        enumerators = "".join(f"\t\t\t\t{{ \"{n}\", {v} }},\n" for n, v in e["values"])
        cpptype = f"\"{e['cpptype']}\"" if e["cpptype"] is not None else "nullptr"
        head_text = (
            "// Generated by tools/codegen/uht_enums.py from the reflection data of\n"
            "// FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387). Do not edit by hand.\n")
        refs = f"// Cross Module References\n\tUPackage* {pkg_fn}();  // RVA 0x{e['pkg']:08X}\n\tUEnum* {zc}();\n"
        static_unit = unit if se and se.get("inlined") else static_units.get(name, unit)
        outputs[GEN_DIR / short / f"{name}.staticenum.gen.cpp"] = (
            head_text +
            f"// UENUM {name} of {e['pkg_name']}: its StaticEnum function, defined at the top of unit {static_unit}\n"
            "// (see tools/codegen/unity.py). Deviation: UHT declares it static. External linkage makes MSVC\n"
            "// emit it, and its Singleton, in definition order; the code is the same.\n\n"
            '#include "FortniteGameCode/UHTRecovered.h"\n\n' + refs +
            f"{se_note}"
            f"\tUEnum* {name}_StaticEnum()\n\t{{\n\t\tstatic UEnum* Singleton = nullptr;\n"
            f"\t\tif (!Singleton)\n\t\t{{\n"
            f"\t\t\tSingleton = GetStaticEnum({zc}, {pkg_fn}(), TEXT(\"{name}\"));\n\t\t}}\n"
            f"\t\treturn Singleton;\n\t}}\n")
        outputs[GEN_DIR / short / f"{name}.defer.gen.cpp"] = (
            head_text +
            f"// UENUM {name} of {e['pkg_name']}: its FCompiledInDeferEnum object, compiled in unit {static_unit}\n"
            f"// (see tools/codegen/unity.py). {name}_StaticEnum is defined in {name}.staticenum.gen.cpp.\n\n"
            '#include "FortniteGameCode/UHTRecovered.h"\n\n'
            f"\tUEnum* {name}_StaticEnum();\n"
            f"{cid_note}"
            f"\tstatic FCompiledInDeferEnum Z_CompiledInDeferEnum_UEnum_{name}({name}_StaticEnum, "
            f"TEXT(\"{e['pkg_name']}\"), TEXT(\"{name}\"), false, nullptr, nullptr);\n")
        outputs[GEN_DIR / short / f"{name}.gen.cpp"] = (
            head_text +
            f"// UENUM {name} of {e['pkg_name']}: constructor, compiled in unity unit {unit}. StaticEnum is in\n"
            f"// {name}.staticenum.gen.cpp; Get_..._CRC() is not emitted (unreferenced in shipping, removed by /OPT:REF).\n\n"
            '#include "FortniteGameCode/UHTRecovered.h"\n\n' + refs +
            f"{disp_decl}"
            f"\t// Original FortniteClient-Win64-Shipping.exe: RVA 0x{e['ctor']:08X} (end 0x{e['ctor_end']:08X})\n"
            f"\t// Original VA: 0x{base + e['ctor']:016X} | File offset: 0x{img.rva_to_off(e['ctor']):08X}\n"
            f"\t// Recovery: confirmed (FEnumParams 0x{e['rec']:08X}, Enumerators 0x{e['enumerators']:08X}; "
            f"values as in the reference) | Matching: see analysis/functions-uht-enums.json\n"
            f"\tUEnum* {zc}()\n\t{{\n\t\tstatic UEnum* ReturnEnum = nullptr;\n\t\tif (!ReturnEnum)\n\t\t{{\n"
            f"\t\t\tstatic const UE4CodeGen_Private::FEnumeratorParam Enumerators[] = {{\n{enumerators}\t\t\t}};\n"
            f"\t\t\tstatic const UE4CodeGen_Private::FEnumParams EnumParams = {{\n"
            f"\t\t\t\t(UObject*(*)()){pkg_fn},\n"
            f"\t\t\t\tUE4CodeGen_Private::EDynamicType::NotDynamic,\n"
            f"\t\t\t\t\"{name}\",\n\t\t\t\t{OBJECT_FLAGS[e['oflags']]},\n\t\t\t\t{disp_expr},\n"
            f"\t\t\t\t(uint8){CPP_FORM.get(e['form'], e['form'])},\n\t\t\t\t{cpptype},\n"
            f"\t\t\t\tEnumerators,\n\t\t\t\tsizeof(Enumerators) / sizeof(Enumerators[0]),\n\t\t\t}};\n"
            f"\t\t\tUE4CodeGen_Private::ConstructUEnum(ReturnEnum, EnumParams);\n\t\t}}\n"
            f"\t\treturn ReturnEnum;\n\t}}\n")
        common = {"package": short, "enum": name, "unit": unit}
        ctor_entries.append({"start_rva": f"0x{e['ctor']:08X}", "end_rva": f"0x{e['ctor_end']:08X}",
                             "name": zc, **common})
        symbols[f"?EnumParams@?4??{zc}@@YAPEAVUEnum@@XZ@4UFEnumParams@UE4CodeGen_Private@@B"] = [
            f"0x{e['rec']:08X}", "name+package"]
        if se:
            se_entries.append({"start_rva": f"0x{se['rva']:08X}", "end_rva": f"0x{se.get('end', se['rva'] + len(SE_TEMPLATE)):08X}",
                               "name": f"{name}_StaticEnum", **common,
                               "unit": unit if se.get("inlined") else static_units[name]})
            stats["staticenum_plain"] += 1
        if cid:
            defer_entries.append({"start_rva": f"0x{cid:08X}", "end_rva": f"0x{cid + len(CID_TEMPLATE):08X}",
                                  "name": f"dynamic initializer for Z_CompiledInDeferEnum_UEnum_{name}", **common,
                                  "unit": static_units.get(name, unit)})   # where the .defer fragment compiles
            stats["defer_initializers"] += 1
        stats["enums_emitted"] += 1

    stats["files_written"], stats["files_removed"] = sync_tree(GEN_DIR, outputs)
    head = {"schema_version": 1, "generated_by": "tools/codegen/uht_enums.py"}
    src_tpl = "FortniteGameCode/Source/Generated/UHT/Enums/{package}/{enum}.gen.cpp"
    se_src_tpl = "FortniteGameCode/Source/Generated/UHT/Enums/{package}/{enum}.staticenum.gen.cpp"
    defer_src_tpl = "FortniteGameCode/Source/Generated/UHT/Enums/{package}/{enum}.defer.gen.cpp"
    obj_tpl = UNIT_OBJECT
    dump_compact(CTOR_MANIFEST, {**head,
        "evidence": ("Z_Construct_UEnum_<Pkg>_<Enum>: 47-byte UHT singleton calling ConstructUEnum; EnumParams by "
                     "content. Translation units group enums whose FEnumParams records are consecutive in .data. "
                     "See docs/REVERSE_ENGINEERING.md."),
        "entry_defaults": {"category": "uht-enum-constructor", "source": src_tpl, "object": obj_tpl,
                           "symbol": "?{name}@@YAPEAVUEnum@@XZ", "name_confidence": "confirmed", "compact": True},
        "functions": ctor_entries})
    dump_compact(SE_MANIFEST, {**head,
        "evidence": ("<Enum>_StaticEnum: 55-byte UHT shape passing Z_Construct_UEnum_* and TEXT(\"<Enum>\") to "
                     "GetStaticEnum. UHT makes it file-static; it is defined with external linkage at the top of its unit, "
                     "in recovered source order, so its Singleton is in the block before the plain .bss as in the "
                     "reference. See docs/REVERSE_ENGINEERING.md."),
        "entry_defaults": {"category": "uht-staticenum", "source": se_src_tpl, "object": obj_tpl,
                           "symbol": "?{enum}_StaticEnum@@YAPEAVUEnum@@XZ", "name_confidence": "confirmed",
                           "compact": True},
        "functions": se_entries})
    dump_compact(DEFER_MANIFEST, {**head,
        "evidence": ("Dynamic initializer of Z_CompiledInDeferEnum_UEnum_<Enum>: the only 66-byte registration "
                     "initializer that LEA-loads the enum's StaticEnum."),
        "entry_defaults": {"category": "uht-enum-compiledindefer", "source": defer_src_tpl, "object": obj_tpl,
                           "symbol": "??__EZ_CompiledInDeferEnum_UEnum_{enum}@@YAXXZ", "name_confidence": "confirmed",
                           "compact": True},
        "functions": defer_entries})
    # <Enum>_StaticEnum, found without the FCompiledInDeferEnum initializer that names it (whose
    # relocation it resolves): the only primary .pdata function that loads the enum's constructor
    # (identified by its FEnumParams name) into rcx just before calling GetStaticEnum. Holds for
    # both forms; the located StaticEnum must agree, as a check only.
    code = dimg.read(text.rva, text.vsize)
    starts = sorted(allrf)
    primary_set = set(primary)
    loaders = defaultdict(set)
    i = code.find(b"\x48\x8d\x0d")
    while i >= 0:
        target = text.rva + i + 7 + struct.unpack_from("<i", code, i + 3)[0]
        for j in range(i + 7, min(i + 7 + 16, len(code) - 5)):
            if code[j] == 0xE8 and text.rva + j + 5 + struct.unpack_from("<i", code, j + 1)[0] == gse:
                k = bisect.bisect_right(starts, text.rva + i) - 1
                f = starts[k] if k >= 0 and text.rva + i < allrf[starts[k]].end else None
                loaders[target].add(f if f in primary_set else None)
                break
        i = code.find(b"\x48\x8d\x0d", i + 1)
    for e in enums:
        hits = loaders.get(e["ctor"], set())
        if not e["se"] or len(hits) != 1 or None in hits:
            stats["static_enum_call: not unique"] += 1
            continue
        if next(iter(hits)) != e["se"]["rva"]:
            stats["static_enum_call: disagrees"] += 1
            continue
        symbols[f"?{e['name']}_StaticEnum@@YAPEAVUEnum@@XZ"] = [f"0x{e['se']['rva']:08X}", "static-enum-call"]
        stats["static_enum_call: resolved"] += 1
    SYMBOLS.write_text(json.dumps({
        "schema_version": 2,
        "generated_by": "tools/codegen/uht_enums.py",
        "evidence_codes": {
            "static-enum-call": "the only function that loads the enum's constructor (named by its FEnumParams) into rcx just before calling GetStaticEnum",
            "package-params": "the 47-byte UHT singleton calling ConstructUPackage whose FPackageParams NameUTF8 is this package",
            "name+package": "the only FEnumParams record in .data whose NameUTF8 is the enum name and whose OuterFunc is its package singleton",
        },
        "symbols": symbols,
    }, separators=(",", ":")).replace('],"', '],\n"') + "\n", encoding="utf-8")
    print(dict(stats), f"GetStaticEnum 0x{gse:08X}", f"ConstructUEnum 0x{construct_enum:08X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
