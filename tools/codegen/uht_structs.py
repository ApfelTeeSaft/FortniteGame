"""Generate UHT-shaped USTRUCT registration code from the reference's own reflection data.

For every USTRUCT whose StaticStruct() has the plain UnrealHeaderTool 4.20 shape (an 82-byte
function in three .pdata fragments that calls the package singleton out of line), this writes
FortniteGameCode/Source/Generated/UHT/Structs/<Package>/F<Struct>.gen.cpp with, in UHT order
(CodeGenerator.cpp, ExportGeneratedStructBodyMacros):

  F<Struct>::StaticStruct()                    static Singleton, GetStaticStruct(...)
  Z_Construct_UScriptStruct_F<Struct>_Statics   NewStructOps (declared), ReturnStructParams
  Z_Construct_UScriptStruct_F<Struct>()         static ReturnStruct, ConstructUScriptStruct
  Get_Z_Construct_UScriptStruct_F<Struct>_CRC() the CRC constant read from the reference
  FCompiledInDeferStruct / FScriptStruct_<Pkg>_StaticRegisterNatives<Struct> objects

The two registration objects come right after StaticStruct in UHT output but at the end of
the file here. Zero-initialized namespace-scope objects share one non-COMDAT .bss section,
created at the first such object of a translation unit. In the original unity file an
earlier object had created it, so the COMDAT statics Singleton and ReturnStruct are adjacent
in the reference. Emitting the objects in UHT position would put that section between them
(docs/REVERSE_ENGINEERING.md). Code generation is unaffected: no function here inlines another.

Identification uses no bytes of the function each fact will be checked against:

* StaticStruct: the shape above, found at a primary .pdata entry. Its LEA of a 47-byte UHT
  singleton names that singleton as the struct's Z_Construct_UScriptStruct_*, and its wide
  TEXT("<Struct>") literal names the struct.
* Package singletons: 47-byte singletons whose FPackageParams name "/Script/<Package>".
* ReturnStructParams: the only FStructParams record in .data whose NameUTF8 is the struct
  name and whose OuterFunc is the package singleton StaticStruct calls.
* CRC function: the only 16-byte-aligned "mov eax, imm32; ret" in .text with the struct's CRC.
* NewStructOps: the record's StructOpsFunc, with the UHT shape. Identical bodies are folded by
  /OPT:ICF, so one function may serve several structs (recorded as folded sources).
* Registration initializers (grouped dynamic-initializer code): the FCompiledInDeferStruct one
  is the only function of its shape that LEA-loads the struct's StaticStruct; the
  StaticRegisterNatives one is the only function of its shape whose FName literal is the
  struct name, and its sizeof/alignof must equal the record's.

Outputs: generated sources, analysis/functions-uht-structs.json (constructors),
analysis/functions-uht-staticstruct.json (StaticStruct functions),
analysis/functions-uht-structops.json (NewStructOps), analysis/functions-uht-struct-defer.json
and analysis/functions-uht-struct-natives.json (registration initializers), and
analysis/uht-struct-symbols.json (addresses with evidence codes).

Usage: python tools/codegen/uht_structs.py
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
sys.path.insert(0, str(ROOT / "tools" / "codegen"))
from compare import load_decrypted  # noqa: E402
from manifest_io import dump_compact  # noqa: E402
from pe import PEImage  # noqa: E402
from unwind import UNW_FLAG_CHAININFO, parse_unwind  # noqa: E402
from uht_creators import CREATOR_SIZE, MASK, TEMPLATE  # noqa: E402

GEN_DIR = ROOT / "FortniteGameCode" / "Source" / "Generated" / "UHT" / "Structs"
CTOR_MANIFEST = ROOT / "analysis" / "functions-uht-structs.json"
OPS_MANIFEST = ROOT / "analysis" / "functions-uht-structops.json"
DEFER_MANIFEST = ROOT / "analysis" / "functions-uht-struct-defer.json"
SRN_MANIFEST = ROOT / "analysis" / "functions-uht-struct-natives.json"
SS_MANIFEST = ROOT / "analysis" / "functions-uht-staticstruct.json"
SYMBOLS = ROOT / "analysis" / "uht-struct-symbols.json"
SS_SIZE = 82
# StaticStruct with the package singleton called out of line. Groups: Singleton (load), CRC
# function, package singleton, sizeof, TEXT name, Z_Construct_UScriptStruct_*, GetStaticStruct,
# Singleton (store). Each group is a rel32 whose instruction ends at the offset in SS_NEXT.
SS_PLAIN = re.compile(
    rb"\x48\x83\xec\x38\x48\x8b\x05(....)\x48\x85\xc0\x75\x3d\x48\x89\x5c\x24\x30\xe8(....)\x8b\xd8"
    rb"\xe8(....)\x48\x8b\xd0\x89\x5c\x24\x20\x41\xb9(....)\x4c\x8d\x05(....)\x48\x8d\x0d(....)"
    rb"\xe8(....)\x48\x8b\x5c\x24\x30\x48\x89\x05(....)\x48\x83\xc4\x38\xc3", re.S)
SS_NEXT = (0x0B, 0x1A, 0x21, None, 0x35, 0x3C, 0x41, 0x4D)
# Further UHT shapes, as templates with per-struct fields zeroed. Field kinds: "rel" is a rel32
# that ends its instruction, "imm" a 32-bit immediate.
CID_TEMPLATE = bytes.fromhex(
    "4883ec3841b801000000488d1500000000488d4c2440e8000000004533c948c744242000000000488d1500000000"
    "488d0d000000004c8b00e8000000004883c438c3")
CID_FIELDS = {"name": (0x0D, "rel"), "fname": (0x17, "rel"), "package": (0x2A, "rel"),
              "staticstruct": (0x31, "rel"), "defer": (0x39, "rel")}
SRN_TEMPLATE = bytes.fromhex(
    "40534883ec20b910000000e800000000488bd84885c0741ac7400800000000c7400c00000000488d0500000000"
    "488903eb0233db41b801000000488d1500000000488d4c2430e800000000488bd3488b08e8000000004883c4205bc3")
SRN_FIELDS = {"new": (0x0C, "rel"), "size": (0x1B, "imm"), "align": (0x22, "imm"), "vtable": (0x29, "rel"),
              "name": (0x3D, "rel"), "fname": (0x47, "rel"), "defer": (0x52, "rel")}
NSO_TEMPLATE = bytes.fromhex(
    "4883ec28b910000000e8000000004885c0741d488d0d00000000c7400800000000488908c7400c000000004883c428c3"
    "4883c428c3")
NSO_FIELDS = {"new": (0x0A, "rel"), "vtable": (0x16, "rel"), "size": (0x1D, "imm"), "align": (0x27, "imm")}
OBJECT_FLAGS = {0x45: "RF_Public|RF_Transient|RF_MarkAsNative", 0x41: "RF_Public|RF_Transient"}
# Names the shared shim declares; a struct of that C++ name would collide.
SHIM_NAMES = {"FFrame", "FNameNativePtrPair", "FNativeFunctionRegistrar", "FClassFunctionLinkInfo",
              "FCppClassTypeInfoStatic"}


def shape(b: bytes | None, rva: int, template: bytes, fields: dict) -> dict | None:
    """Field values (rel32 fields as absolute RVAs) if `b` equals `template` outside them."""
    if b is None or len(b) != len(template):
        return None
    masked = {i for off, _ in fields.values() for i in range(off, off + 4)}
    if any(b[i] != template[i] for i in range(len(b)) if i not in masked):
        return None
    return {k: (rva + off + 4 + struct.unpack_from("<i", b, off)[0] if kind == "rel"
                else struct.unpack_from("<I", b, off)[0]) for k, (off, kind) in fields.items()}


def rel32(b: bytes, at: int, nxt: int, rva: int) -> int:
    return rva + nxt + struct.unpack_from("<i", b, at)[0]


def cstr(img: PEImage, rva: int) -> str | None:
    b = img.read(rva, 512)
    n = b.find(b"\0")
    return b[:n].decode("ascii") if n > 0 and all(0x20 <= c < 0x7F for c in b[:n]) else None


def wstr(img: PEImage, rva: int) -> str | None:
    b = img.read(rva, 1024)
    out = []
    for i in range(0, len(b) - 1, 2):
        c = b[i] | b[i + 1] << 8
        if c == 0:
            return "".join(out) or None
        if not 0x20 <= c < 0x7F:
            return None
        out.append(chr(c))
    return None


def main() -> int:
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

    def singleton(rva: int):
        """(ReturnX slot, params record, callee) of a 47-byte UHT singleton, else None."""
        rf = allrf.get(rva)
        if rf is None or rf.end - rf.begin != CREATOR_SIZE:
            return None
        b = dimg.read(rva, CREATOR_SIZE)
        if b is None or any(b[i] != TEMPLATE[i] for i in range(CREATOR_SIZE) if i not in MASK):
            return None
        return rel32(b, 7, 0xB, rva), rel32(b, 0x13, 0x17, rva), rel32(b, 0x1F, 0x23, rva)

    stats = Counter()
    found = []
    for p in primary:
        try:
            b = dimg.read(p, SS_SIZE)
        except ValueError:
            continue
        m = SS_PLAIN.fullmatch(b)
        if m is None:
            continue
        g = [struct.unpack("<i", x)[0] for x in m.groups()]
        f = {k: (p + nxt + v if nxt is not None else v) for k, nxt, v in zip(
            ("singleton", "crc_fn", "package", "size", "name", "ctor", "get_static_struct", "store"),
            SS_NEXT, g)}
        frags = sorted(x for x in allrf if p <= x < p + SS_SIZE)
        tiles = all(allrf[a].end == nb for a, nb in zip(frags, frags[1:] + [p + SS_SIZE]))
        chained = all(parse_unwind(img, allrf[a].unwind).chained[0] == p for a in frags[1:])
        if not (len(frags) == 3 and tiles and chained and f["store"] == f["singleton"]):
            stats["staticstruct_fragments_mismatch"] += 1
            continue
        f["staticstruct"] = p
        found.append(f)

    gss = Counter(f["get_static_struct"] for f in found).most_common(1)[0][0]
    found = [f for f in found if f["get_static_struct"] == gss]
    ctors = {f["ctor"]: singleton(f["ctor"]) for f in found}
    construct_struct = Counter(v[2] for v in ctors.values() if v).most_common(1)[0][0]
    pkg_sing = {f["package"]: singleton(f["package"]) for f in found}
    construct_package = Counter(v[2] for v in pkg_sing.values() if v).most_common(1)[0][0]
    packages = {}
    for rva, s in pkg_sing.items():
        if s and s[2] == construct_package:
            name = cstr(img, struct.unpack("<Q", img.read(s[1], 8))[0] - base)
            if name and name.startswith("/Script/"):
                packages[rva] = name

    # FStructParams candidates in .data keyed by (NameUTF8, OuterFunc).
    ds = next(s for s in img.sections if s.name == ".data")
    data = img.read(ds.rva, ds.rawsize)
    records = defaultdict(list)
    for off in range(0, len(data) - 0x48, 8):
        outer, _, _, nameptr, oflags = struct.unpack_from("<QQQQI", data, off)
        if outer - base in packages and base <= nameptr < base + img.size_of_image and oflags in OBJECT_FLAGS:
            n = cstr(img, nameptr - base)
            if n:
                records[(n, outer - base)].append(ds.rva + off)

    # CRC functions: 16-byte-aligned "mov eax, imm32; ret" anywhere in .text, by constant.
    tdata = bytes(dimg.data_rva[text.rva:text.rva + text.vsize])
    crc_sites = defaultdict(list)
    for i in range(0, len(tdata) - 6, 16):
        if tdata[i] == 0xB8 and tdata[i + 5] == 0xC3:
            crc_sites[struct.unpack_from("<I", tdata, i + 1)[0]].append(text.rva + i)

    ctor_name = {}   # ctor RVA -> struct name, for SuperFunc references
    rows = []
    for f in found:
        sing = ctors.get(f["ctor"])
        if sing is None or sing[2] != construct_struct:
            stats["ctor_not_singleton"] += 1
            continue
        if f["package"] not in packages:
            stats["package_unknown"] += 1
            continue
        name = wstr(img, f["name"])
        recs = records.get((name, f["package"]), []) if name else []
        if len(recs) != 1:
            stats["record_not_unique"] += 1
            continue
        rec = recs[0]
        outer, sup, ops, nameptr, oflags, sflags, size, align, props, nprops = struct.unpack(
            "<QQQQIIQQQi4x", img.read(rec, 0x48))
        if size != f["size"] or cstr(img, nameptr - base) != name:
            stats["record_inconsistent"] += 1
            continue
        crc_b = dimg.read(f["crc_fn"], 6)
        if crc_b[0] != 0xB8 or crc_b[5] != 0xC3:
            stats["crc_shape"] += 1
            continue
        crc = struct.unpack_from("<I", crc_b, 1)[0]
        if crc_sites.get(crc) != [f["crc_fn"]]:
            stats["crc_not_unique"] += 1
            continue
        cpp = "F" + name
        if cpp in SHIM_NAMES:
            stats["shim_name_collision"] += 1
            continue
        ctor_name[f["ctor"]] = cpp
        rows.append(dict(f, name=name, cpp=cpp, rec=rec, sup=sup - base if sup else 0, ops=ops,
                         oflags=oflags, sflags=sflags, align=align, nprops=nprops, crc=crc,
                         ctor_end=allrf[f["ctor"]].end, pkg_name=packages[f["package"]]))

    seen = Counter((r["pkg_name"], r["cpp"].lower()) for r in rows)
    rows = [r for r in rows if seen[(r["pkg_name"], r["cpp"].lower())] == 1]

    def read(rva: int, n: int) -> bytes | None:
        try:
            return dimg.read(rva, n)
        except ValueError:
            return None

    # Registration initializers, by shape over every primary function.
    cid_by_ss, srn_by_name = defaultdict(list), defaultdict(list)
    for p in primary:
        n = allrf[p].end - p
        if n == len(CID_TEMPLATE):
            f = shape(read(p, n), p, CID_TEMPLATE, CID_FIELDS)
            if f:
                cid_by_ss[f["staticstruct"]].append((p, f))
        elif n == len(SRN_TEMPLATE):
            f = shape(read(p, n), p, SRN_TEMPLATE, SRN_FIELDS)
            if f:
                srn_by_name[wstr(img, f["name"])].append((p, f))
    name_count = Counter(r["name"] for r in rows)
    for r in rows:
        c = cid_by_ss.get(r["staticstruct"], [])
        r["cid"] = c[0] if len(c) == 1 else None
        s_ = srn_by_name.get(r["name"], [])
        ok = len(s_) == 1 and name_count[r["name"]] == 1 and (s_[0][1]["size"], s_[0][1]["align"]) == (r["size"], r["align"])
        r["srn"] = s_[0] if ok else None
        ops = r["ops"] - base if r["ops"] else None
        f = None
        if ops in allrf and allrf[ops].end - ops == len(NSO_TEMPLATE):
            f = shape(read(ops, len(NSO_TEMPLATE)), ops, NSO_TEMPLATE, NSO_FIELDS)
        r["nso"] = (ops, f) if f and (f["size"], f["align"]) == (r["size"], r["align"]) else None
        stats["compiledindefer_found"] += r["cid"] is not None
        stats["registernatives_found"] += r["srn"] is not None
        stats["newstructops_found"] += r["nso"] is not None

    GEN_DIR.mkdir(parents=True, exist_ok=True)
    for old in GEN_DIR.rglob("*.gen.cpp"):
        old.unlink()
    ctor_entries, ss_entries, symbols = [], [], {}
    defer_entries, srn_entries, ops_groups = [], [], defaultdict(list)
    for pkg_rva, pname in packages.items():
        symbols[f"?Z_Construct_UPackage_{pname.replace('/', '_')}@@YAPEAVUPackage@@XZ"] = [
            f"0x{pkg_rva:08X}", "package-params"]
    for r in sorted(rows, key=lambda r: r["ctor"]):
        short = r["pkg_name"].rsplit("/", 1)[1]
        pkg_fn = f"Z_Construct_UPackage_{r['pkg_name'].replace('/', '_')}"
        cpp, name = r["cpp"], r["name"]
        zc = f"Z_Construct_UScriptStruct_{cpp}"
        statics = f"{zc}_Statics"
        crc_fn = f"Get_{zc}_CRC"
        ss, ss_end = r["staticstruct"], r["staticstruct"] + SS_SIZE
        if r["sup"]:
            sup_name = ctor_name.get(r["sup"])
            super_expr = f"Z_Construct_UScriptStruct_{sup_name}" if sup_name else f"Z_Construct_UScriptStruct_Unrecovered_0x{r['sup']:08X}"
            super_decl = f"UScriptStruct* {super_expr}();  // RVA 0x{r['sup']:08X}\n"
        else:
            super_expr, super_decl = "nullptr", ""
        decl = ["\t\tstatic void* NewStructOps();"]
        if r["nprops"]:
            decl.append("\t\tstatic const UE4CodeGen_Private::FPropertyParamsBase* const PropPointers[];  // pending")
            props_expr = f"{statics}::PropPointers, {r['nprops']}"
        else:
            props_expr = "nullptr, 0"
        flags = OBJECT_FLAGS[r["oflags"]]
        nso_note = (f"\t// Original FortniteClient-Win64-Shipping.exe: RVA 0x{r['nso'][0]:08X} (StructOpsFunc; may be ICF-folded)\n"
                    if r["nso"] else "\t// StructOpsFunc not matched to the UHT shape\n")
        cid_note = (f"// Original dynamic initializer: RVA 0x{r['cid'][0]:08X}\n" if r["cid"] else "")
        srn_note = (f"// Original dynamic initializer: RVA 0x{r['srn'][0]:08X}\n" if r["srn"] else "")
        src = (
            "// Generated by tools/codegen/uht_structs.py from the reflection data of\n"
            "// FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387). Do not edit by hand.\n"
            f"// USTRUCT {cpp} of {r['pkg_name']}: registration code in UnrealHeaderTool 4.20 output shape.\n"
            f"// FStructParams RVA 0x{r['rec']:08X}. The registration objects follow the CRC function\n"
            f"// instead of StaticStruct; see tools/codegen/uht_structs.py.\n\n"
            '#include "FortniteGameCode/UObjectRegistrationRecovered.h"\n\n'
            "// Cross Module References\n"
            f"\tUScriptStruct* {zc}();\n"
            f"\tUPackage* {pkg_fn}();  // RVA 0x{r['package']:08X}\n"
            f"{super_decl}"
            f"struct alignas({r['align']}) {cpp}\n{{\n\tstatic class UScriptStruct* StaticStruct();\n"
            f"\tunsigned char Opaque[0x{r['size']:X}];  // layout not reconstructed; sizeof/alignof from FStructParams\n}};\n"
            f"// Original FortniteClient-Win64-Shipping.exe: RVA 0x{ss:08X} (end 0x{ss_end:08X}, three .pdata fragments)\n"
            f"// Original VA: 0x{base + ss:016X} | File offset: 0x{img.rva_to_off(ss):08X}\n"
            f"// Recovery: confirmed (TEXT(\"{name}\") and {zc}) | Matching: see analysis/functions-uht-staticstruct.json\n"
            f"class UScriptStruct* {cpp}::StaticStruct()\n{{\n"
            "\tstatic class UScriptStruct* Singleton = NULL;\n\tif (!Singleton)\n\t{\n"
            f"\t\textern uint32 {crc_fn}();\n"
            f"\t\tSingleton = GetStaticStruct({zc}, {pkg_fn}(), TEXT(\"{name}\"), sizeof({cpp}), {crc_fn}());\n"
            "\t}\n\treturn Singleton;\n}\n"
            f"\tstruct {statics}\n\t{{\n" + "\n".join(decl) + "\n"
            "\t\tstatic const UE4CodeGen_Private::FStructParams ReturnStructParams;\n\t};\n"
            f"{nso_note}"
            f"\tvoid* {statics}::NewStructOps()\n\t{{\n"
            f"\t\treturn (UScriptStruct::ICppStructOps*)new UScriptStruct::TCppStructOps<{cpp}>();\n\t}}\n"
            f"\t// ReturnStructParams: original RVA 0x{r['rec']:08X}\n"
            f"\tconst UE4CodeGen_Private::FStructParams {statics}::ReturnStructParams = {{\n"
            f"\t\t(UObject* (*)()){pkg_fn},\n\t\t{super_expr},\n\t\t&NewStructOps,\n\t\t\"{name}\",\n"
            f"\t\t{flags},\n\t\tEStructFlags(0x{r['sflags']:08X}),\n\t\tsizeof({cpp}),\n\t\talignof({cpp}),\n"
            f"\t\t{props_expr},\n\t}};\n"
            f"\t// Original FortniteClient-Win64-Shipping.exe: RVA 0x{r['ctor']:08X} (end 0x{r['ctor_end']:08X})\n"
            f"\t// Original VA: 0x{base + r['ctor']:016X} | File offset: 0x{img.rva_to_off(r['ctor']):08X}\n"
            f"\t// Recovery: confirmed (StaticStruct registers it) | Matching: see analysis/functions-uht-structs.json\n"
            f"\tUScriptStruct* {zc}()\n\t{{\n\t\tstatic UScriptStruct* ReturnStruct = nullptr;\n"
            f"\t\tif (!ReturnStruct)\n\t\t{{\n"
            f"\t\t\tUE4CodeGen_Private::ConstructUScriptStruct(ReturnStruct, {statics}::ReturnStructParams);\n"
            "\t\t}\n\t\treturn ReturnStruct;\n\t}\n"
            f"\t// Original RVA 0x{r['crc_fn']:08X} (leaf, no .pdata); the constant is read from it.\n"
            f"\tuint32 {crc_fn}() {{ return {r['crc']}U; }}\n"
            f"{cid_note}"
            f"static FCompiledInDeferStruct Z_CompiledInDeferStruct_UScriptStruct_{cpp}({cpp}::StaticStruct, "
            f"TEXT(\"{r['pkg_name']}\"), TEXT(\"{name}\"), false, nullptr, nullptr);\n"
            f"{srn_note}"
            f"static struct FScriptStruct_{short}_StaticRegisterNatives{cpp}\n{{\n"
            f"\tFScriptStruct_{short}_StaticRegisterNatives{cpp}()\n\t{{\n"
            f"\t\tUScriptStruct::DeferCppStructOps(FName(TEXT(\"{name}\")),new UScriptStruct::TCppStructOps<{cpp}>);\n"
            f"\t}}\n}} ScriptStruct_{short}_StaticRegisterNatives{cpp};\n")
        out = GEN_DIR / short / f"{cpp}.gen.cpp"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(src, encoding="utf-8", newline="\n")
        common = {"package": short, "struct": cpp}
        ctor_entries.append({"start_rva": f"0x{r['ctor']:08X}", "end_rva": f"0x{r['ctor_end']:08X}",
                             "name": zc, **common})
        ss_entries.append({"start_rva": f"0x{ss:08X}", "end_rva": f"0x{ss_end:08X}",
                           "name": f"{cpp}::StaticStruct", **common})
        if r["cid"]:
            defer_entries.append({"start_rva": f"0x{r['cid'][0]:08X}",
                                  "end_rva": f"0x{r['cid'][0] + len(CID_TEMPLATE):08X}",
                                  "name": f"dynamic initializer for Z_CompiledInDeferStruct_UScriptStruct_{cpp}", **common})
        if r["srn"]:
            srn_entries.append({"start_rva": f"0x{r['srn'][0]:08X}",
                                "end_rva": f"0x{r['srn'][0] + len(SRN_TEMPLATE):08X}",
                                "name": f"dynamic initializer for ScriptStruct_{short}_StaticRegisterNatives{cpp}", **common})
        if r["nso"]:
            ops_groups[r["nso"][0]].append((cpp, short))
        symbols[f"?ReturnStructParams@{statics}@@2UFStructParams@UE4CodeGen_Private@@B"] = [
            f"0x{r['rec']:08X}", "name+package"]
        symbols[f"?{crc_fn}@@YAIXZ"] = [f"0x{r['crc_fn']:08X}", "crc-content"]
        stats["structs"] += 1

    head = {"schema_version": 1, "generated_by": "tools/codegen/uht_structs.py"}
    ops_entries = []
    for ops in sorted(ops_groups):
        (cpp, short), *rest = sorted(ops_groups[ops])
        e = {"start_rva": f"0x{ops:08X}", "end_rva": f"0x{ops + len(NSO_TEMPLATE):08X}",
             "name": f"Z_Construct_UScriptStruct_{cpp}_Statics::NewStructOps", "package": short, "struct": cpp}
        if rest:
            e["folded_sources"] = [{"object": f"Source/Generated/UHT/Structs/{p2}/{c2}.gen.obj",
                                    "symbol": f"?NewStructOps@Z_Construct_UScriptStruct_{c2}_Statics@@SAPEAXXZ"}
                                   for c2, p2 in rest]
        ops_entries.append(e)
    stats["newstructops_functions"] = len(ops_entries)
    src_tpl = "FortniteGameCode/Source/Generated/UHT/Structs/{package}/{struct}.gen.cpp"
    obj_tpl = "Source/Generated/UHT/Structs/{package}/{struct}.gen.obj"
    dump_compact(CTOR_MANIFEST, {**head,
        "evidence": ("Z_Construct_UScriptStruct_<Struct>: the 47-byte UHT singleton that the struct's StaticStruct "
                     "passes to GetStaticStruct. ReturnStructParams by content. See docs/REVERSE_ENGINEERING.md."),
        "entry_defaults": {"category": "uht-struct-constructor", "source": src_tpl, "object": obj_tpl,
                           "symbol": "?{name}@@YAPEAVUScriptStruct@@XZ", "name_confidence": "confirmed",
                           "compact": True},
        "functions": ctor_entries})
    dump_compact(SS_MANIFEST, {**head,
        "evidence": ("<Struct>::StaticStruct: 82-byte UHT shape in three chained .pdata fragments, passing "
                     "TEXT(\"<Struct>\") and Z_Construct_UScriptStruct_<Struct> to GetStaticStruct."),
        "entry_defaults": {"category": "uht-staticstruct", "source": src_tpl, "object": obj_tpl,
                           "symbol": "?StaticStruct@{struct}@@SAPEAVUScriptStruct@@XZ",
                           "name_confidence": "confirmed", "compact": True},
        "functions": ss_entries})
    src_tpl_ = src_tpl
    dump_compact(OPS_MANIFEST, {**head,
        "evidence": ("Z_Construct_UScriptStruct_<Struct>_Statics::NewStructOps: StructOpsFunc of the struct's "
                     "FStructParams record, 53-byte UHT shape. /OPT:ICF folds identical bodies; the other "
                     "structs sharing one are listed as folded sources."),
        "entry_defaults": {"category": "uht-struct-ops", "source": src_tpl_, "object": obj_tpl,
                           "symbol": "?NewStructOps@Z_Construct_UScriptStruct_{struct}_Statics@@SAPEAXXZ",
                           "name_confidence": "confirmed", "compact": True},
        "functions": ops_entries})
    dump_compact(DEFER_MANIFEST, {**head,
        "evidence": ("Dynamic initializer of Z_CompiledInDeferStruct_UScriptStruct_<Struct>: the only function of "
                     "the 66-byte shape that LEA-loads the struct's StaticStruct."),
        "entry_defaults": {"category": "uht-struct-compiledindefer", "source": src_tpl_, "object": obj_tpl,
                           "symbol": "??__EZ_CompiledInDeferStruct_UScriptStruct_{struct}@@YAXXZ",
                           "name_confidence": "confirmed", "compact": True},
        "functions": defer_entries})
    dump_compact(SRN_MANIFEST, {**head,
        "evidence": ("Dynamic initializer of ScriptStruct_<Pkg>_StaticRegisterNatives<Struct>: the only function of "
                     "the 92-byte shape whose FName literal is the struct name; sizeof/alignof equal FStructParams."),
        "entry_defaults": {"category": "uht-struct-registernatives", "source": src_tpl_, "object": obj_tpl,
                           "symbol": "??__EScriptStruct_{package}_StaticRegisterNatives{struct}@@YAXXZ",
                           "name_confidence": "confirmed", "compact": True},
        "functions": srn_entries})
    SYMBOLS.write_text(json.dumps({
        "schema_version": 2,
        "generated_by": "tools/codegen/uht_structs.py",
        "evidence_codes": {
            "package-params": "the 47-byte UHT singleton calling ConstructUPackage whose FPackageParams NameUTF8 is this package",
            "name+package": "the only FStructParams record in .data whose NameUTF8 is the struct name and whose OuterFunc is its package singleton",
            "crc-content": "the only 16-byte-aligned 'mov eax, imm32; ret' in .text with this struct's CRC constant",
        },
        "symbols": symbols,
    }, separators=(",", ":")).replace('],"', '],\n"') + "\n", encoding="utf-8")
    stats["staticstruct_plain"] = len(found)
    stats["packages"] = len(packages)
    print(dict(stats), f"GetStaticStruct 0x{gss:08X}", f"ConstructUScriptStruct 0x{construct_struct:08X}",
          f"ConstructUPackage 0x{construct_package:08X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
