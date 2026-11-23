"""Generate UHT-shaped UFunction creators from the reference's reflection data.

For every class whose FClassFunctionLinkInfo array consists only of creators with the
standard 47-byte UHT shape, this writes FortniteGameCode/Source/Generated/UHT/<Class>.gen.cpp,
matching UnrealHeaderTool 4.20 output (CodeGenerator.cpp): a <Creator>_Statics struct, a
const FFunctionParams definition, and the creator with its static ReturnFunction. Creators
appear in table order, which is also their order in the image.

FFunctionParams values come from the binary's own record (.data, plaintext on disk). The
record is located by content alone: its NameUTF8 must point at the function's name, and its
OuterFunc must be the class's consensus outer, or, for a class none of whose functions has a
uniquely named record, the Z_Construct_UClass_<Class> its FCompiledInDefer initializer registers.
The creator's code is never read for this.
These addresses go to analysis/uht-creator-symbols.json with that evidence. PropPointers are
declared but not defined: property-parameter recovery is a separate, pending data task.

Outputs: generated sources, analysis/functions-uht-creators.json (manifest entries),
analysis/uht-creator-symbols.json (FuncParams addresses with evidence).

Usage: python tools/codegen/uht_creators.py
"""
from __future__ import annotations

import json
import re
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "matching"))
from compare import load_decrypted  # noqa: E402
from unity import UNIT_OBJECT, unit_of  # noqa: E402
from genio import sync_tree  # noqa: E402
from manifest_io import dump_compact  # noqa: E402
from pe import PEImage  # noqa: E402

GEN_DIR = ROOT / "FortniteGameCode" / "Source" / "Generated" / "UHT"
MANIFEST = ROOT / "analysis" / "functions-uht-creators.json"
CLASS_MANIFEST = ROOT / "analysis" / "functions-uht-classes.json"
NATIVES_MANIFEST = ROOT / "analysis" / "functions-uht-natives.json"
THUNK_MANIFEST = ROOT / "analysis" / "functions-uht-staticclass.json"
# StaticRegisterNatives<Class>: call GetPrivateStaticClass; mov r8d, N; lea rdx, Funcs; mov rcx, rax; jmp.
SRN_TEMPLATE = bytes.fromhex("4883ec28e80000000041b800000000488d1500000000488bc84883c428e900000000")
SRN_MASK = set(range(5, 9)) | set(range(11, 15)) | set(range(18, 22)) | set(range(30, 34))
SYMBOLS = ROOT / "analysis" / "uht-creator-symbols.json"
CREATOR_SIZE = 47
# Relocated displacement bytes of the standard creator (RF x3, FuncParams, call).
MASK = set(range(7, 11)) | set(range(0x13, 0x17)) | set(range(0x1A, 0x1E)) | set(range(0x1F, 0x23)) | set(range(0x26, 0x2A))
TEMPLATE = bytes.fromhex("4883ec28488b05000000004885c0751a488d1500000000488d0d00000000e800000000488b05000000004883c428c3")
IDENT = re.compile(rb"[A-Za-z_][A-Za-z0-9_]{0,250}\x00")
OBJECT_FLAGS = {0x45: "RF_Public|RF_Transient|RF_MarkAsNative", 0x41: "RF_Public|RF_Transient"}


def creator_name(cls: str, fn: str) -> str:
    kind = "UDelegateFunction" if fn.endswith("__DelegateSignature") else "UFunction"
    return f"Z_Construct_{kind}_{cls}_{fn}"


def class_constructor(cls, arr, fns, zrva, emitted_fns, img, rdata, rd, base, rfs, externs, symbols,
                      evidence: str = "link-array") -> str:
    """UHT 4.20 Z_Construct_UClass_<Class> with its Statics, values decoded from FClassParams."""
    rec = int(arr["class_params_rva"], 16)
    (nreg, deps, ndeps, cflags, links, nfuncs, props, nprops, cfg, cppinfo, ifaces,
     nifaces) = struct.unpack("<QQiIQi4xQi4xQQQi4x", img.read(rec, 0x58))
    statics = f"Z_Construct_UClass_{cls}_Statics"
    decl, defs = [], []
    if ndeps:
        decl.append("\tstatic UObject* (*const DependentSingletons[])();  // pending")
        deps_expr = f"{statics}::DependentSingletons, {ndeps}"
    else:
        deps_expr = "nullptr, 0"
    if fns:
        decl.append("\tstatic const FClassFunctionLinkInfo FuncInfo[];")
        info = []
        for fname, crva in sorted(fns, key=lambda x: x[0]):
            cname = creator_name(cls, fname)
            if fname not in emitted_fns:
                externs.add(f"UFunction* {cname}();  // RVA 0x{crva:08X}, not emitted (FFunctionParams unresolved)")
            info.append(f'\t{{ &{cname}, "{fname}" }},')
        defs.append(f"const FClassFunctionLinkInfo {statics}::FuncInfo[] = {{\n" + "\n".join(info) + "\n};")
        funcs_expr = f"{statics}::FuncInfo, {nfuncs}"
    else:
        funcs_expr = "nullptr, 0"
    if nprops:
        decl.append("\tstatic const UE4CodeGen_Private::FPropertyParamsBase* const PropPointers[];  // pending")
        props_expr = f"{statics}::PropPointers, {nprops}"
    else:
        props_expr = "nullptr, 0"
    if nifaces:
        decl.append("\tstatic const UE4CodeGen_Private::FImplementedInterfaceParams InterfaceParams[];  // pending")
        iface_expr = f"{statics}::InterfaceParams, {nifaces}"
    else:
        iface_expr = "nullptr, 0"
    decl.append("\tstatic const FCppClassTypeInfoStatic StaticCppClassTypeInfo;")
    abstract = img.read(cppinfo - base, 1)[0] if cppinfo else 0
    defs.append(f"const FCppClassTypeInfoStatic {statics}::StaticCppClassTypeInfo = {{ {'true' if abstract else 'false'} }};")
    decl.append("\tstatic const UE4CodeGen_Private::FClassParams ClassParams;")
    cfg_expr = "nullptr"
    if cfg:
        m = IDENT.match(rdata, cfg - base - rd.rva)
        cfg_expr = f'"{m.group(0)[:-1].decode()}"' if m else "nullptr"
    defs.append(
        f"// ClassParams: original RVA 0x{rec:08X}\n"
        f"const UE4CodeGen_Private::FClassParams {statics}::ClassParams = {{ &{cls}::StaticClass, {deps_expr}, "
        f"0x{cflags:08X}u, {funcs_expr}, {props_expr}, {cfg_expr}, "
        f"&{statics}::StaticCppClassTypeInfo, {iface_expr} }};")
    end = rfs[zrva].end
    symbols[f"?ClassParams@{statics}@@2UFClassParams@UE4CodeGen_Private@@B"] = [f"0x{rec:08X}", evidence]
    return (f"struct {statics}\n{{\n" + "\n".join(decl) + "\n};\n" + "\n".join(defs) + "\n"
            f"// Original FortniteClient-Win64-Shipping.exe: RVA 0x{zrva:08X} (end 0x{end:08X})\n"
            f"// Original VA: 0x{base + zrva:016X} | File offset: 0x{img.rva_to_off(zrva):08X}\n"
            f"// Recovery: confirmed (UHT singleton of {cls}) | Matching: see analysis/functions-uht-classes.json\n"
            f"UClass* Z_Construct_UClass_{cls}()\n{{\n\tstatic UClass* OuterClass = nullptr;\n\tif (!OuterClass)\n\t{{\n"
            f"\t\tUE4CodeGen_Private::ConstructUClass(OuterClass, {statics}::ClassParams);\n\t}}\n"
            f"\treturn OuterClass;\n}}\n")


def main() -> int:
    img = PEImage()
    dimg = load_decrypted(img)
    if dimg is None:
        print("needs the validated decrypted image", file=sys.stderr)
        return 1
    base = img.image_base
    refl = json.loads((ROOT / "analysis" / "reflection-natives.json").read_text(encoding="utf-8"))
    # Z_Construct_UClass_* registered by each class's FCompiledInDefer initializer.
    unity_ctor = {it["name"]: int(it["constructor"], 16)
                  for u in json.loads((ROOT / "analysis" / "unity-order.json").read_text(encoding="utf-8"))["units"]
                  for it in u["items"] if it["kind"] == "class"}
    rfs = {rf.begin: rf for rf in img.runtime_functions()}
    starts = set(rfs)
    rd = next(s for s in img.sections if s.name == ".rdata")
    rdata = img.read(rd.rva, rd.rawsize)
    ds = next(s for s in img.sections if s.name == ".data")
    data = img.read(ds.rva, ds.rawsize)

    def is_creator(rva: int) -> bool:
        rf = rfs.get(rva)
        if rf is None or rf.end - rf.begin != CREATOR_SIZE:
            return False
        b = dimg.read(rva, CREATOR_SIZE)
        return all(b[i] == TEMPLATE[i] for i in range(CREATOR_SIZE) if i not in MASK)

    # FFunctionParams candidates in .data: {OuterFunc -> function start, NameUTF8 -> identifier}.
    by_name: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for off in range(0, len(data) - 0x40, 8):
        a, b = struct.unpack_from("<QQ", data, off)
        if not (base <= a < base + img.size_of_image and base <= b < base + img.size_of_image):
            continue
        a -= base
        b -= base
        if a in starts and rd.rva <= b < rd.rva + rd.rawsize:
            m = IDENT.match(rdata, b - rd.rva)
            if m:
                by_name[m.group(0)[:-1].decode()].append((ds.rva + off, a))

    classes = []
    for arr in refl["function_link_arrays"]:
        fns = [(f["name"], int(f["construct_rva"], 16)) for f in arr["functions"]]
        if not arr["class"] or not all(is_creator(c) for _, c in fns):
            continue
        # Definition order: UHT emits a class's delegate signatures first, in header order
        # (their creators' code addresses preserve it), then its functions sorted by name,
        # which is the FClassFunctionLinkInfo order.
        delegates = sorted((x for x in fns if x[0].endswith("__DelegateSignature")), key=lambda x: x[1])
        functions = [x for x in fns if not x[0].endswith("__DelegateSignature")]
        classes.append((arr["class"], arr, delegates + functions))

    # Consensus outer per class from uniquely named records.
    consensus: dict[str, int | None] = {}
    for cls, _, fns in classes:
        outers = Counter(by_name[n][0][1] for n, _ in fns if len(by_name.get(n, [])) == 1)
        top = outers.most_common(1)
        consensus[cls] = top[0][0] if top and top[0][1] * 2 > sum(outers.values()) else None
    outer_class = {v: k for k, v in consensus.items() if v is not None}
    creator_by_rva = {c: creator_name(cls, n) for cls, _, fns in classes for n, c in fns}

    GEN_DIR.mkdir(parents=True, exist_ok=True)
    outputs: dict[Path, str] = {}
    entries, class_entries, native_entries, thunk_entries, symbols = [], [], [], [], {}
    natives_by_class = {c["class"]: c for c in refl["native_classes"]
                        if c["class"] and c["static_register_natives_rva"]}

    def is_srn(rva: int) -> bool:
        rf = rfs.get(rva)
        if rf is None or rf.end - rf.begin != len(SRN_TEMPLATE):
            return False
        b = dimg.read(rva, len(SRN_TEMPLATE))
        return all(b[i] == SRN_TEMPLATE[i] for i in range(len(b)) if i not in SRN_MASK)
    stats = Counter()
    for cls, arr, fns in classes:
        lines = [
            "// Generated by tools/codegen/uht_creators.py from the reflection data of",
            "// FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387). Do not edit by hand.",
            f"// Class {cls}: UFunction creators in UnrealHeaderTool 4.20 output shape, in original order.",
            f"// FClassFunctionLinkInfo array RVA {arr['array_rva']}, FClassParams RVA {arr['class_params_rva']}.",
            "",
            '#include "FortniteGameCode/UHTRecovered.h"',
            "",
        ]
        externs, bodies, emitted_fns = set(), [], set()
        nat = natives_by_class.get(cls)
        if nat is not None and not is_srn(int(nat["static_register_natives_rva"], 16)):
            nat = None
        if nat is not None:
            srn = int(nat["static_register_natives_rva"], 16)
            arr_rva = int(nat["array_rva"], 16)
            # An interface's exec thunks are members of its native I<Name> class (CLASS_Interface in
            # the FClassParams ClassFlags at +0x14).
            iface = struct.unpack("<I", dimg.read(int(arr["class_params_rva"], 16) + 0x14, 4))[0] & 0x00004000
            owner = "I" + cls[1:] if iface else cls
            pairs = "\n".join(f'\t\t{{ "{f["name"]}", &{owner}::exec{f["name"]} }},' for f in nat["functions"])
            bodies.append(
                f"// Original FortniteClient-Win64-Shipping.exe: RVA 0x{srn:08X} (end 0x{rfs[srn].end:08X})\n"
                f"// Original VA: 0x{base + srn:016X} | File offset: 0x{img.rva_to_off(srn):08X}\n"
                f"// Recovery: confirmed (registers FNameNativePtrPair array 0x{arr_rva:08X}) | Matching: see analysis/functions-uht-natives.json\n"
                f"void {cls}::StaticRegisterNatives{cls}()\n{{\n\tUClass* Class = {cls}::StaticClass();\n"
                f"\tstatic const FNameNativePtrPair Funcs[] = {{\n{pairs}\n\t}};\n"
                f"\tFNativeFunctionRegistrar::RegisterFunctions(Class, Funcs, sizeof(Funcs) / sizeof(Funcs[0]));\n}}\n")
            symbols[f"?Funcs@?1??StaticRegisterNatives{cls}@{cls}@@SAXXZ@4QBUFNameNativePtrPair@@B"] = [
                f"0x{arr_rva:08X}", "native-array"]
            if nat.get("get_private_static_class_rva"):
                symbols[f"?GetPrivateStaticClass@{cls}@@CAPEAVUClass@@XZ"] = [
                    nat["get_private_static_class_rva"], "gpsc-chain"]
            native_entries.append({"start_rva": f"0x{srn:08X}", "end_rva": f"0x{rfs[srn].end:08X}",
                                   "name": f"StaticRegisterNatives{cls}", "class": cls})
            stats["static_register_natives"] += 1
        for fname, crva in fns:
            cname = creator_name(cls, fname)
            statics = f"{cname}_Statics"
            cands = by_name.get(fname, [])
            # The class's outer: the consensus of its uniquely named records, or, when none of
            # its functions has one, the Z_Construct_UClass_<Class> its FCompiledInDefer
            # initializer registers (a different function from this creator).
            outer_ref, outer_code = consensus.get(cls), "name+outer"
            if outer_ref is None and cls in unity_ctor:
                outer_ref, outer_code = unity_ctor[cls], "name+class-ctor"
            if len(cands) == 1:
                rec, why = cands[0][0], "unique FFunctionParams record whose NameUTF8 names this function"
            else:
                hits = [c for c in cands if outer_ref is not None and c[1] == outer_ref]
                rec = hits[0][0] if len(hits) == 1 else None
                why = "only FFunctionParams record naming this function with the class's OuterFunc"
                stats[f"funcparams_resolved_by_{outer_code}"] += rec is not None
            by_class_ctor = rec is not None and len(cands) != 1 and outer_code == "name+class-ctor"
            if rec is None or by_class_ctor:
                # The creator's code is the standard shape; only its FFunctionParams record is not
                # identified (no unique record by name). It is emitted with the record declared, so
                # its ReturnFunction static keeps its place in the unity layout.
                # A record identified through the class constructor is declared only, too, with
                # its address as evidence: defining it moves the unit's TClassCompiledInDefer
                # objects, which the reference keeps in one block ahead of its records, and
                # that layout is not modelled yet (docs/REVERSE_ENGINEERING.md).
                end = rfs[crva].end
                if by_class_ctor:
                    note = f"record 0x{rec:08X} (name and class constructor), declared only"
                    symbols[f"?FuncParams@{statics}@@2UFFunctionParams@UE4CodeGen_Private@@B"] = [
                        f"0x{rec:08X}", outer_code]
                    stats["funcparams_declared_by_class_ctor"] += 1
                else:
                    note = f"record not identified: {len(cands)} candidate(s) by name"
                    stats["funcparams_unresolved"] += 1
                bodies.append(
                    f"struct {statics}\n{{\n"
                    f"\tstatic const UE4CodeGen_Private::FFunctionParams FuncParams;  // {note}\n}};\n"
                    f"// Original FortniteClient-Win64-Shipping.exe: RVA 0x{crva:08X} (end 0x{end:08X})\n"
                    f"// Original VA: 0x{base + crva:016X} | File offset: 0x{img.rva_to_off(crva):08X}\n"
                    f"// Recovery: confirmed name (FClassFunctionLinkInfo) | Matching: see analysis/functions-uht-creators.json\n"
                    f"UFunction* {cname}()\n{{\n\tstatic UFunction* ReturnFunction = nullptr;\n\tif (!ReturnFunction)\n\t{{\n"
                    f"\t\tUE4CodeGen_Private::ConstructUFunction(ReturnFunction, {statics}::FuncParams);\n\t}}\n"
                    f"\treturn ReturnFunction;\n}}\n")
                entries.append({"start_rva": f"0x{crva:08X}", "end_rva": f"0x{end:08X}", "name": cname, "class": cls})
                emitted_fns.add(fname)
                continue
            stats["funcparams_resolved"] += 1
            outer, nameptr, oflags, superf, fflags, size, props, nprops, rpc, rpcr = struct.unpack(
                "<QQIxxxxQIxxxxQQiHH", img.read(rec, 0x40))
            outer -= base
            name_lit = IDENT.match(rdata, nameptr - base - rd.rva).group(0)[:-1].decode()
            if outer == consensus.get(cls):
                outer_expr = f"Z_Construct_UClass_{cls}"
                externs.add(f"UClass* Z_Construct_UClass_{cls}();  // RVA 0x{outer:08X} (consensus OuterFunc)")
            elif consensus.get(cls) is None and outer == unity_ctor.get(cls):
                outer_expr = f"Z_Construct_UClass_{cls}"
                externs.add(f"UClass* Z_Construct_UClass_{cls}();  // RVA 0x{outer:08X} (registered by its FCompiledInDefer)")
            elif outer in outer_class:
                outer_expr = f"Z_Construct_UClass_{outer_class[outer]}"
                externs.add(f"UClass* Z_Construct_UClass_{outer_class[outer]}();  // RVA 0x{outer:08X}")
            else:
                outer_expr = f"Z_Construct_Unrecovered_0x{outer:08X}"
                externs.add(f"UObject* Z_Construct_Unrecovered_0x{outer:08X}();  // outer not yet named")
            if superf:
                s = superf - base
                super_expr = creator_by_rva.get(s, f"Z_Construct_UnrecoveredFunction_0x{s:08X}")
                if s not in creator_by_rva or creator_by_rva[s] not in {creator_name(cls, n) for n, _ in fns}:
                    externs.add(f"UFunction* {super_expr}();  // RVA 0x{s:08X}")
                super_expr = f"{super_expr}"
            else:
                super_expr = "nullptr"
            flags_expr = OBJECT_FLAGS.get(oflags, f"(EObjectFlags)0x{oflags:08X}")
            prop_decl = ""
            if nprops:
                prop_decl = ("\tstatic const UE4CodeGen_Private::FPropertyParamsBase* const PropPointers[];"
                             "  // definition pending property-parameter recovery\n")
                prop_expr = f"{statics}::PropPointers, {nprops}"
            else:
                prop_expr = "nullptr, 0"
            end = rfs[crva].end
            bodies.append(
                f"struct {statics}\n{{\n{prop_decl}"
                f"\tstatic const UE4CodeGen_Private::FFunctionParams FuncParams;\n}};\n"
                f"// FuncParams: original RVA 0x{rec:08X}; StructureSize 0x{size:X} is sizeof the event parms struct.\n"
                f"const UE4CodeGen_Private::FFunctionParams {statics}::FuncParams = {{ (UObject*(*)()){outer_expr}, "
                f"\"{name_lit}\", {flags_expr}, {super_expr}, (EFunctionFlags)0x{fflags:08X}, 0x{size:X}, "
                f"{prop_expr}, {rpc}, {rpcr} }};\n"
                f"// Original FortniteClient-Win64-Shipping.exe: RVA 0x{crva:08X} (end 0x{end:08X})\n"
                f"// Original VA: 0x{base + crva:016X} | File offset: 0x{img.rva_to_off(crva):08X}\n"
                f"// Recovery: confirmed name (FClassFunctionLinkInfo) | Matching: see analysis/functions-uht-creators.json\n"
                f"UFunction* {cname}()\n{{\n\tstatic UFunction* ReturnFunction = nullptr;\n\tif (!ReturnFunction)\n\t{{\n"
                f"\t\tUE4CodeGen_Private::ConstructUFunction(ReturnFunction, {statics}::FuncParams);\n\t}}\n"
                f"\treturn ReturnFunction;\n}}\n")
            symbols[f"?FuncParams@{statics}@@2UFFunctionParams@UE4CodeGen_Private@@B"] = [
                f"0x{rec:08X}", "name" if len(cands) == 1 else outer_code]
            entries.append({"start_rva": f"0x{crva:08X}", "end_rva": f"0x{end:08X}",
                            "name": cname, "class": cls})
            emitted_fns.add(fname)
        zrva = consensus.get(cls)
        if zrva is None and cls in unity_ctor:
            zrva = unity_ctor[cls]
            stats["class_constructor_from_unity_order"] += 1
        if zrva is not None and arr["class_params_rva"] and is_creator(zrva):
            bodies.append(class_constructor(cls, arr, fns, zrva, emitted_fns, img, rdata, rd, base, rfs,
                                            externs, symbols))
            class_entries.append({"start_rva": f"0x{zrva:08X}", "end_rva": f"0x{rfs[zrva].end:08X}",
                                  "name": f"Z_Construct_UClass_{cls}", "class": cls})
            sc = arr["static_class_rva"]
            if sc:
                thunk_entries.append({"start_rva": sc, "end_rva": f"0x{int(sc, 16) + 5:08X}",
                                      "name": f"{cls}::StaticClass", "class": cls})
            stats["class_constructors"] += 1
        text = "\n".join(lines) + "\n".join(sorted(externs)) + "\n\n" + "\n".join(bodies)
        outputs[GEN_DIR / f"{cls}.gen.cpp"] = text
    stats["files_written"], stats["files_removed"] = sync_tree(GEN_DIR, outputs, recursive=False)
    stats["classes"] = len(classes)
    stats["creators"] = len(entries)
    # Objects are the unity translation units (tools/codegen/unity.py) the fragments are compiled in.
    units = unit_of()
    for e in entries + class_entries + native_entries + thunk_entries:
        e["unit"] = units[("class", e["class"])]
    dump_compact(MANIFEST, {
        "schema_version": 1,
        "generated_by": "tools/codegen/uht_creators.py",
        "evidence": ("Names from FClassFunctionLinkInfo tables. Classes via FClassParams -> StaticClass -> "
                     "GetPrivateStaticClass. Shape: the 47-byte UHT creator. See docs/REVERSE_ENGINEERING.md."),
        "entry_defaults": {
            "category": "uht-ufunction-creator",
            "source": "FortniteGameCode/Source/Generated/UHT/{class}.gen.cpp",
            "object": UNIT_OBJECT,
            "symbol": "?{name}@@YAPEAVUFunction@@XZ",
            "name_confidence": "confirmed",
            "compact": True,
        },
        "functions": entries,
    })
    dump_compact(CLASS_MANIFEST, {
        "schema_version": 1,
        "generated_by": "tools/codegen/uht_creators.py",
        "evidence": ("Z_Construct_UClass_<Class>: the consensus OuterFunc of the class's FFunctionParams records, "
                     "with the 47-byte UHT shape. ClassParams is the FClassParams record referencing the class's "
                     "FClassFunctionLinkInfo array. See docs/REVERSE_ENGINEERING.md."),
        "entry_defaults": {
            "category": "uht-class-constructor",
            "source": "FortniteGameCode/Source/Generated/UHT/{class}.gen.cpp",
            "object": UNIT_OBJECT,
            "symbol": "?{name}@@YAPEAVUClass@@XZ",
            "name_confidence": "confirmed",
            "compact": True,
        },
        "functions": class_entries,
    })
    common = {"schema_version": 1, "generated_by": "tools/codegen/uht_creators.py"}
    dump_compact(NATIVES_MANIFEST, {**common,
        "evidence": ("StaticRegisterNatives<Class>: the only function that LEA-references the class's attributed "
                     "FNameNativePtrPair array, with the 34-byte UHT shape. See docs/REVERSE_ENGINEERING.md."),
        "entry_defaults": {"category": "uht-static-register-natives",
                           "source": "FortniteGameCode/Source/Generated/UHT/{class}.gen.cpp",
                           "object": UNIT_OBJECT,
                           "symbol": "?{name}@{class}@@SAXXZ", "name_confidence": "confirmed", "compact": True},
        "functions": native_entries})
    dump_compact(THUNK_MANIFEST, {**common,
        "evidence": ("<Class>::StaticClass: ClassNoRegisterFunc of the class's FClassParams record, a 5-byte "
                     "jmp GetPrivateStaticClass with no .pdata entry (outside the denominator)."),
        "entry_defaults": {"category": "uht-staticclass-thunk",
                           "source": "FortniteGameCode/Source/Generated/UHT/{class}.gen.cpp",
                           "object": UNIT_OBJECT,
                           "symbol": "?StaticClass@{class}@@SAPEAVUClass@@XZ", "name_confidence": "confirmed",
                           "compact": True},
        "functions": thunk_entries})
    SYMBOLS.write_text(json.dumps({
        "schema_version": 2,
        "generated_by": "tools/codegen/uht_creators.py",
        "evidence_codes": {
            "name": "the only FFunctionParams record in .data whose NameUTF8 names this function",
            "name+outer": "the only FFunctionParams record naming this function whose OuterFunc is the class consensus",
            "name+class-ctor": "the only FFunctionParams record naming this function whose OuterFunc is the Z_Construct_UClass_<Class> its FCompiledInDefer initializer registers (the class has no consensus)",
            "link-array": "the only FClassParams record whose FunctionLinkArray points at this class's FClassFunctionLinkInfo table",
            "native-array": "the FNameNativePtrPair array attributed to this class in analysis/reflection-natives.json",
            "gpsc-chain": "the only function that LEA-loads &StaticRegisterNatives<Class> (GetPrivateStaticClassBody argument), per analysis/reflection-natives.json",
        },
        "symbols": symbols,
    }, separators=(",", ":")).replace('],"', '],\n"') + "\n", encoding="utf-8")
    print(dict(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
