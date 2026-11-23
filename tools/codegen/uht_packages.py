"""Generate package-scope delegate creators and package singletons (UHT 4.20 output shape).

A header's package-scope delegates (DECLARE_DYNAMIC_*_DELEGATE outside a class) are emitted
first in its .gen.cpp as Z_Construct_UDelegateFunction_<Pkg>_<Name>__DelegateSignature: a
47-byte singleton with its FFunctionParams, like a class's UFunction creators.
tools/analysis/unity_order.py identifies them through their package's SingletonFuncArray and
places them in the unity order.

<Module>.init.gen.cpp holds Z_Construct_UPackage__Script_<Pkg>() (ExportGeneratedPackageInitCode).
Its function-local SingletonFuncArray lists every delegate of the package (class-scope ones
included) and its noexport structs; FPackageParams adds the name, flags and the two CRCs.

Evidence:
* delegate FuncParams: the only FFunctionParams record in .data naming the delegate whose
  OuterFunc is its package singleton;
* PackageParams: the only FPackageParams record in .rdata whose NameUTF8 is the package name.

Outputs: Generated/UHT/Delegates/<Pkg>/<Name>.gen.cpp, Generated/UHT/Packages/<Pkg>.init.gen.cpp,
analysis/functions-uht-package-delegates.json, analysis/functions-uht-packages.json and
analysis/uht-package-symbols.json.

Usage: python tools/codegen/uht_packages.py   (after tools/analysis/unity_order.py)
"""
from __future__ import annotations

import json
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "matching"))
sys.path.insert(0, str(ROOT / "tools" / "codegen"))
from compare import load_decrypted  # noqa: E402
from genio import sync_tree  # noqa: E402
from manifest_io import dump_compact  # noqa: E402
from pe import PEImage  # noqa: E402
from uht_creators import CREATOR_SIZE, MASK, OBJECT_FLAGS, TEMPLATE, creator_name  # noqa: E402
from uht_structs import cstr  # noqa: E402
from unity import UNIT_OBJECT, unit_of  # noqa: E402

GEN = ROOT / "FortniteGameCode" / "Source" / "Generated" / "UHT"
DEL_DIR = GEN / "Delegates"
PKG_DIR = GEN / "Packages"
DEL_MANIFEST = ROOT / "analysis" / "functions-uht-package-delegates.json"
PKG_MANIFEST = ROOT / "analysis" / "functions-uht-packages.json"
SYMBOLS = ROOT / "analysis" / "uht-package-symbols.json"
PKG_COMPILED_IN = 0x00000010


def main() -> int:
    img = PEImage()
    dimg = load_decrypted(img)
    if dimg is None:
        print("needs the validated decrypted image", file=sys.stderr)
        return 1
    base = img.image_base
    allrf = {rf.begin: rf for rf in img.runtime_functions()}
    order = json.loads((ROOT / "analysis" / "unity-order.json").read_text(encoding="utf-8"))
    refl = json.loads((ROOT / "analysis" / "reflection-natives.json").read_text(encoding="utf-8"))
    stats = Counter()

    def singleton(rva):
        rf = allrf.get(rva)
        if rf is None or rf.end - rva != CREATOR_SIZE:
            return None
        try:
            b = dimg.read(rva, CREATOR_SIZE)
        except ValueError:
            return None
        if any(b[i] != TEMPLATE[i] for i in range(CREATOR_SIZE) if i not in MASK):
            return None
        return tuple(rva + nxt + struct.unpack_from("<i", b, at)[0] for at, nxt in ((7, 0xB), (0x13, 0x17), (0x1F, 0x23)))

    # Package singletons: FPackageParams in .rdata name the package.
    packages = {}
    for rva in allrf:
        s = singleton(rva)
        if s is None or img.section_of(s[1]) is None or img.section_of(s[1]).name != ".rdata":
            continue
        name = cstr(img, struct.unpack("<Q", img.read(s[1], 8))[0] - base)
        if name and name.startswith("/Script/"):
            packages[name] = (rva, s)
    rd = next(s for s in img.sections if s.name == ".rdata")
    rdata = img.read(rd.rva, rd.rawsize)
    # FPackageParams by content: an 8-aligned .rdata record whose NameUTF8 points at the
    # package's name string, with PKG_CompiledIn set and a plausible singleton array.
    name_va = {}
    for pname in packages:
        lit = pname.encode() + b"\0"
        p = rdata.find(lit)
        while p >= 0:
            if p == 0 or rdata[p - 1] == 0:
                name_va.setdefault(pname, []).append(base + rd.rva + p)
            p = rdata.find(lit, p + 1)
    by_name_ptr = {v: k for k, vs in name_va.items() for v in vs}
    package_records = defaultdict(list)
    for off in range(0, len(rdata) - 0x24, 8):
        v = struct.unpack_from("<Q", rdata, off)[0]
        pname = by_name_ptr.get(v)
        if pname is None:
            continue
        flags, _, _, arr, n = struct.unpack_from("<IIIxxxxQi", rdata, off + 8)
        if flags & PKG_COMPILED_IN and (arr == 0 or base <= arr < base + img.size_of_image) and 0 <= n < 100000:
            package_records[pname].append(rd.rva + off)

    # FFunctionParams candidates in .data by (NameUTF8, OuterFunc).
    ds = next(s for s in img.sections if s.name == ".data")
    data = img.read(ds.rva, ds.rawsize)
    pkg_rvas = {v[0]: k for k, v in packages.items()}
    records = defaultdict(list)
    for off in range(0, len(data) - 0x40, 8):
        outer, nameptr = struct.unpack_from("<QQ", data, off)
        if outer - base in pkg_rvas and base <= nameptr < base + img.size_of_image:
            n = cstr(img, nameptr - base)
            if n and n.endswith("__DelegateSignature"):
                records[(n, outer - base)].append(ds.rva + off)

    # Names of everything a SingletonFuncArray can list.
    creator_names = {}
    for a in refl["function_link_arrays"]:
        if a["class"]:
            for f in a["functions"]:
                creator_names[int(f["construct_rva"], 16)] = creator_name(a["class"], f["name"])
    units = unit_of()
    outputs, del_entries, pkg_entries, symbols = {}, [], [], {}
    for u in order["units"]:
        for it in u["items"]:
            if it["kind"] != "delegate":
                continue
            pname, name = it["package"], it["name"]
            short = pname.rsplit("/", 1)[1]
            prva = packages[pname][0]
            crva = int(it["constructor"], 16)
            cname = f"Z_Construct_UDelegateFunction_{short}_{name}"
            creator_names[crva] = cname
            recs = records.get((name, prva), [])
            if len(recs) != 1:
                stats["delegate_record_not_unique"] += 1
                continue
            rec = recs[0]
            outer, nameptr, oflags, superf, fflags, size, props, nprops, rpc, rpcr = struct.unpack(
                "<QQIxxxxQIxxxxQQiHH", img.read(rec, 0x40))
            statics = f"{cname}_Statics"
            pkg_fn = f"Z_Construct_UPackage_{pname.replace('/', '_')}"
            prop_decl = ("\tstatic const UE4CodeGen_Private::FPropertyParamsBase* const PropPointers[];  // pending\n"
                         if nprops else "")
            prop_expr = f"{statics}::PropPointers, {nprops}" if nprops else "nullptr, 0"
            super_expr = "nullptr"
            if superf:
                super_expr = creator_names.get(superf - base, f"Z_Construct_UnrecoveredFunction_0x{superf - base:08X}")
            end = allrf[crva].end
            outputs[DEL_DIR / short / f"{name}.gen.cpp"] = (
                "// Generated by tools/codegen/uht_packages.py from the reflection data of\n"
                "// FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387). Do not edit by hand.\n"
                f"// Package-scope delegate {name} of {pname}: its UFunction creator in UHT 4.20 output shape.\n\n"
                '#include "FortniteGameCode/UHTRecovered.h"\n\n'
                f"\tUPackage* {pkg_fn}();  // RVA 0x{prva:08X}\n"
                + (f"\tUFunction* {super_expr}();\n" if superf else "")
                # FuncParams is a static local of the creator, as in the reference's generated code
                # (see tools/codegen/uht_creators.py); PropPointers stays a declared member.
                + (f"\tstruct {statics}\n\t{{\n{prop_decl}\t}};\n" if prop_decl else "") +
                f"\t// Original FortniteClient-Win64-Shipping.exe: RVA 0x{crva:08X} (end 0x{end:08X})\n"
                f"\t// Original VA: 0x{base + crva:016X} | File offset: 0x{img.rva_to_off(crva):08X}\n"
                f"\t// Recovery: confirmed (listed by {pkg_fn}'s SingletonFuncArray) | "
                "Matching: see analysis/functions-uht-package-delegates.json\n"
                f"\tUFunction* {cname}()\n\t{{\n\t\tstatic UFunction* ReturnFunction = nullptr;\n"
                f"\t\tif (!ReturnFunction)\n\t\t{{\n"
                f"\t\t\t// FuncParams: original RVA 0x{rec:08X}\n"
                f"\t\t\tstatic const UE4CodeGen_Private::FFunctionParams FuncParams = {{ (UObject*(*)()){pkg_fn}, "
                f"\"{name}\", {OBJECT_FLAGS.get(oflags, f'(EObjectFlags)0x{oflags:08X}')}, {super_expr}, "
                f"(EFunctionFlags)0x{fflags:08X}, 0x{size:X}, {prop_expr}, {rpc}, {rpcr} }};\n"
                f"\t\t\tUE4CodeGen_Private::ConstructUFunction(ReturnFunction, FuncParams);\n\t\t}}\n"
                "\t\treturn ReturnFunction;\n\t}\n")
            del_entries.append({"start_rva": f"0x{crva:08X}", "end_rva": f"0x{end:08X}", "name": cname,
                                "package": short, "delegate": name, "unit": units[("delegate", f"{pname}:{name}")]})
            symbols[f"?FuncParams@?4??{cname}@@YAPEAVUFunction@@XZ@4UFFunctionParams@UE4CodeGen_Private@@B"] = [
                f"0x{rec:08X}", "name+package"]
            stats["package_delegates"] += 1

    # Package singletons.
    function_callee = Counter(singleton(int(it["constructor"], 16))[2] for u in order["units"] for it in u["items"]
                              if it["kind"] == "delegate").most_common(1)[0][0]
    for pname, (prva, s) in sorted(packages.items()):
        short = pname.rsplit("/", 1)[1]
        rec = s[1]
        _, flags, h1, h2, arr, n = struct.unpack("<QIIIxxxxQi", img.read(rec, 0x24))
        entries = []
        for i in range(n):
            g = struct.unpack("<Q", img.read(arr - base + 8 * i, 8))[0] - base
            if g in creator_names:
                entries.append((creator_names[g], "UFunction", g))
                continue
            gs = singleton(g)
            if gs and gs[2] == function_callee:
                # A delegate creator from a function table that is not attributed to a class.
                entries.append((f"Z_Construct_UDelegateFunction_Unattributed_0x{g:08X}", "UFunction", g))
                continue
            sname = cstr(img, struct.unpack("<Q", img.read(gs[1] + 0x18, 8))[0] - base) if gs else None
            entries.append((f"Z_Construct_UScriptStruct_F{sname}" if sname else f"Z_Construct_Unrecovered_0x{g:08X}",
                            "UScriptStruct", g))
        pkg_fn = f"Z_Construct_UPackage_{pname.replace('/', '_')}"
        externs = "".join(f"\t{t}* {nm}();  // RVA 0x{g:08X}\n" for nm, t, g in entries)
        array = ("\t\t\tstatic UObject* (*const SingletonFuncArray[])() = {\n"
                 + "".join(f"\t\t\t\t(UObject* (*)()){nm},\n" for nm, _, _ in entries) + "\t\t\t};\n") if entries else ""
        rng = "SingletonFuncArray, sizeof(SingletonFuncArray) / sizeof(SingletonFuncArray[0])" if entries else "nullptr, 0"
        end = allrf[prva].end
        outputs[PKG_DIR / f"{short}.init.gen.cpp"] = (
            "// Generated by tools/codegen/uht_packages.py from the reflection data of\n"
            "// FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387). Do not edit by hand.\n"
            f"// {short}.init.gen.cpp: the package singleton of {pname} in UHT 4.20 output shape.\n\n"
            '#include "FortniteGameCode/UHTRecovered.h"\n\n' + externs +
            f"\t// Original FortniteClient-Win64-Shipping.exe: RVA 0x{prva:08X} (end 0x{end:08X})\n"
            f"\t// Original VA: 0x{base + prva:016X} | File offset: 0x{img.rva_to_off(prva):08X}\n"
            f"\t// Recovery: confirmed (FPackageParams 0x{rec:08X} names {pname}) | Matching: see analysis/functions-uht-packages.json\n"
            f"\tUPackage* {pkg_fn}()\n\t{{\n\t\tstatic UPackage* ReturnPackage = nullptr;\n\t\tif (!ReturnPackage)\n\t\t{{\n"
            f"{array}"
            "\t\t\tstatic const UE4CodeGen_Private::FPackageParams PackageParams = {\n"
            f"\t\t\t\t\"{pname}\",\n\t\t\t\tPKG_CompiledIn | 0x{flags & ~PKG_COMPILED_IN:08X},\n"
            f"\t\t\t\t0x{h1:08X},\n\t\t\t\t0x{h2:08X},\n\t\t\t\t{rng},\n\t\t\t}};\n"
            "\t\t\tUE4CodeGen_Private::ConstructUPackage(ReturnPackage, PackageParams);\n\t\t}\n"
            "\t\treturn ReturnPackage;\n\t}\n")
        pkg_entries.append({"start_rva": f"0x{prva:08X}", "end_rva": f"0x{end:08X}", "name": pkg_fn, "package": short,
                            "unit": units.get(("package", pname), f"Packages.{short}")})
        if package_records.get(pname) == [rec]:
            symbols[f"?PackageParams@?4??{pkg_fn}@@YAPEAVUPackage@@XZ@4UFPackageParams@UE4CodeGen_Private@@B"] = [
                f"0x{rec:08X}", "package-name"]
        else:
            stats["package_record_not_unique"] += 1
        stats["packages"] += 1

    stats["files_written"], stats["files_removed"] = sync_tree(DEL_DIR, {k: v for k, v in outputs.items() if DEL_DIR in k.parents})
    w, r = sync_tree(PKG_DIR, {k: v for k, v in outputs.items() if PKG_DIR in k.parents})
    stats["files_written"] += w
    head = {"schema_version": 1, "generated_by": "tools/codegen/uht_packages.py"}
    dump_compact(DEL_MANIFEST, {**head,
        "evidence": ("Z_Construct_UDelegateFunction_<Pkg>_<Name>: a package-scope delegate listed by its package's "
                     "SingletonFuncArray whose FFunctionParams OuterFunc is the package singleton."),
        "entry_defaults": {"category": "uht-ufunction-creator",
                           "source": "FortniteGameCode/Source/Generated/UHT/Delegates/{package}/{delegate}.gen.cpp",
                           "object": UNIT_OBJECT, "symbol": "?{name}@@YAPEAVUFunction@@XZ",
                           "name_confidence": "confirmed", "compact": True},
        "functions": del_entries})
    dump_compact(PKG_MANIFEST, {**head,
        "evidence": "Z_Construct_UPackage__Script_<Pkg>: the 47-byte singleton whose FPackageParams name the package.",
        "entry_defaults": {"category": "uht-package-constructor",
                           "source": "FortniteGameCode/Source/Generated/UHT/Packages/{package}.init.gen.cpp",
                           "object": UNIT_OBJECT, "symbol": "?{name}@@YAPEAVUPackage@@XZ",
                           "name_confidence": "confirmed", "compact": True},
        "functions": pkg_entries})
    SYMBOLS.write_text(json.dumps({
        "schema_version": 2, "generated_by": "tools/codegen/uht_packages.py",
        "evidence_codes": {
            "name+package": "the only FFunctionParams record in .data naming this delegate whose OuterFunc is its package singleton",
            "package-name": "the only FPackageParams-shaped record in .rdata whose NameUTF8 points at the package name"},
        "symbols": symbols}, separators=(",", ":")).replace('],"', '],\n"') + "\n", encoding="utf-8")
    print(dict(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
