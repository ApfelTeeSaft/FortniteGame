"""Generate UHT 4.20 class declarations and IMPLEMENT_CLASS bodies for every reflected class.

Inputs: analysis/unity-order.json (each class's FCompiledInDefer and TClassCompiledInDefer
registration: Z_Construct_UClass_*, <Class>::StaticClass, sizeof, CRC), analysis/reflection-
natives.json (native function names), and the decrypted image.

GetPrivateStaticClass (IMPLEMENT_CLASS) passes everything DECLARE_CLASS defines to
GetPrivateStaticClassBody:
- StaticPackage(), the class name and &PrivateStaticClass;
- StaticRegisterNatives<Class>, sizeof, StaticClassFlags, StaticClassCastFlags() and
  StaticConfigName();
- InternalConstructor<Class>, InternalVTableHelperCtorCaller<Class> and AddReferencedObjects;
- Super::StaticClass and WithinClass::StaticClass.

Decoding the reference's 151- and 162-byte bodies therefore recovers the class hierarchy and
the declaration values. The body is reached from <Class>::StaticClass, a 5-byte jmp named
by the class's FCompiledInDefer initializer.

Outputs:
* FortniteGameCode/Source/Generated/UHT/Classes.gen.h: every class, superclasses first, with
  real inheritance (so &C::AddReferencedObjects resolves as in the engine) and an opaque
  member that makes sizeof(C) the recovered size. Members are added only where the reference
  shows them: AddReferencedObjects when a class's pointer differs from its superclass's,
  exec thunks for native classes. Shim headers supply extra members for UClass,
  UScriptStruct and UEnum.
* FortniteGameCode/Source/Generated/UHT/Classes/<Package>/<Class>.gen.cpp: the empty
  StaticRegisterNatives of a class without natives, Z_Construct_UClass_* for a class without
  UFunctions, and IMPLEMENT_CLASS's GetPrivateStaticClass.
* analysis/functions-uht-gpsc.json, analysis/functions-uht-classes-nofunc.json and
  analysis/uht-class-symbols.json.

Each fragment also holds IMPLEMENT_CLASS's TClassCompiledInDefer object (AutoInitialize<Class>)
and UHT's FCompiledInDefer object, whose dynamic initializers go to
analysis/functions-uht-class-autoinit.json (leaf, outside the denominator) and
analysis/functions-uht-class-defer.json.

Usage: python tools/codegen/uht_classes.py   (after tools/analysis/unity_order.py)
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
from capstone import CS_ARCH_X86, CS_MODE_64, Cs  # noqa: E402
from compare import load_decrypted  # noqa: E402
from unity import UNIT_OBJECT, unit_of  # noqa: E402
from genio import sync_tree  # noqa: E402
from manifest_io import dump_compact  # noqa: E402
from pe import PEImage  # noqa: E402
from uht_creators import CREATOR_SIZE, MASK, TEMPLATE, class_constructor  # noqa: E402
from uht_structs import shape, wstr  # noqa: E402
import uht_exec  # noqa: E402

GEN = ROOT / "FortniteGameCode" / "Source" / "Generated" / "UHT"
HEADER = GEN / "Classes.gen.h"
FRAG_DIR = GEN / "Classes"
GPSC_MANIFEST = ROOT / "analysis" / "functions-uht-gpsc.json"
NOFUNC_MANIFEST = ROOT / "analysis" / "functions-uht-classes-nofunc.json"
DEFER_MANIFEST = ROOT / "analysis" / "functions-uht-class-defer.json"
AUTO_MANIFEST = ROOT / "analysis" / "functions-uht-class-autoinit.json"
EXEC_MANIFEST = ROOT / "analysis" / "functions-uht-exec.json"
EXEC_SYMBOL = "?exec{ufunction}@{class}@@SAXPEAVUObject@@AEAUFFrame@@QEAX@Z"
# mov r9d, CRC; lea rdx, TEXT; mov r8d, sizeof; lea rcx, object; jmp UClassCompiledInDefer
AUTO_INITIALIZER_SIZE = 31
SYMBOLS = ROOT / "analysis" / "uht-class-symbols.json"
UNITY_ORDER = ROOT / "analysis" / "unity-order.json"
# Classes whose extra (non-DECLARE_CLASS) members come from the shim headers.
EXTRA_MEMBERS = ("UClass", "UScriptStruct", "UEnum", "UByteProperty", "UInt8Property", "UInt16Property",
                 "UIntProperty", "UInt64Property", "UUInt16Property", "UUInt32Property", "UUInt64Property",
                 "UFloatProperty", "UDoubleProperty", "UNameProperty", "UStrProperty", "UTextProperty")
# Intrinsic classes whose GetPrivateStaticClass is not decoded, with what the thunks need:
# UField (Class.h) is UObject plus `UField* Next`; FFrame::StepCompiledIn reads Next at +0x28
# in the reference's thunks, right after UObject's 0x28 bytes.
INTRINSIC = {"UField": {"super": "UObject", "size": 0x30,
                        "members": [("\tUField* Next;  // +0x28", 8)]}}
CLASS_DEPRECATED = 0x02000000

_G162 = ("4c8bdc4883ec78488b05000000004885c00f858600000088442468"
         "4c8d0d00000000488d05000000004989" "43e84c8d0500000000488d050000000049" "8943e0488d1500000000488d050000000049"
         "8943d8488d0d00000000488d050000000049" "8943d0488d05000000004989" "43c8488d05000000004989" "43c049c743b800000000"
         "c744242800000000c744242000000000e800000000488b05000000004883c478c3")
GPSC162 = bytes.fromhex(_G162)
GPSC162_FIELDS = {"psc_load": (0x0A, "rel"), "srn": (0x1E, "rel"), "within": (0x25, "rel"), "psc": (0x30, "rel"),
                  "super": (0x37, "rel"), "name": (0x42, "rel"), "aro": (0x49, "rel"), "package": (0x54, "rel"),
                  "vtable_ctor": (0x5B, "rel"), "ctor": (0x66, "rel"), "config": (0x71, "rel"),
                  "cast": (0x7D, "imm"), "flags": (0x85, "imm"), "size": (0x8D, "imm"), "body": (0x92, "rel"),
                  "psc_ret": (0x99, "rel")}
_G151 = ("4c8bdc4883ec78488b05000000004885c0757f88442468"
         "4c8d0d00000000488d05000000004989" "43e84c8d050000000049" "8943e0488d1500000000488d050000000049"
         "8943d8488d0d00000000488d050000000049" "8943d0488d05000000004989" "43c8488d05000000004989" "43c049c743b800000000"
         "c744242800000000c744242000000000e800000000488b05000000004883c478c3")
GPSC151 = bytes.fromhex(_G151)
GPSC151_FIELDS = {"psc_load": (0x0A, "rel"), "srn": (0x1A, "rel"), "within": (0x21, "rel"), "psc": (0x2C, "rel"),
                  "name": (0x37, "rel"), "aro": (0x3E, "rel"), "package": (0x49, "rel"), "vtable_ctor": (0x50, "rel"),
                  "ctor": (0x5B, "rel"), "config": (0x66, "rel"), "cast": (0x72, "imm"), "flags": (0x7A, "imm"),
                  "size": (0x82, "imm"), "body": (0x87, "rel"), "psc_ret": (0x8E, "rel")}


_MD = Cs(CS_ARCH_X86, CS_MODE_64)
_REG64 = {"al": "rax", "eax": "rax", "rax": "rax", "ecx": "rcx", "rcx": "rcx", "edx": "rdx", "rdx": "rdx",
          "r8d": "r8", "r8": "r8", "r9d": "r9", "r9": "r9"}
# GetPrivateStaticClassBody argument -> location at the call.
_ARGS = {"package": "rcx", "name": "rdx", "psc": "r8", "srn": "r9", "size": 0x20, "flags": 0x28, "cast": 0x30,
         "config": 0x38, "ctor": 0x40, "vtable_ctor": 0x48, "aro": 0x50, "super": 0x58, "within": 0x60,
         "dynamic": 0x68}


def decode_gpsc(b: bytes | None, rva: int) -> dict | None:
    """GetPrivateStaticClassBody arguments of an IMPLEMENT_CLASS body, from its instruction stream.

    Registers and stack slots are tracked up to the first call. Stack slots are normalised to
    rsp-relative offsets at the call, whether written through r11 (= entry rsp) or rsp.
    """
    if b is None:
        return None
    regs, stack, frame, uses_r11, psc_load = {}, {}, None, False, None
    for ins in _MD.disasm(b, rva):
        op, mn = ins.op_str, ins.mnemonic
        tgt = None
        m = re.search(r"\[rip ([+-]) (0x[0-9a-f]+)\]", op)
        if m:
            tgt = ins.address + ins.size + (1 if m.group(1) == "+" else -1) * int(m.group(2), 16)
        if mn == "mov" and op == "r11, rsp":
            uses_r11 = True
        elif mn == "sub" and op.startswith("rsp, "):
            frame = int(op.split(", ")[1], 16)
        elif mn == "mov" and op.startswith("rax, qword ptr [rip") and psc_load is None:
            psc_load, regs["rax"] = tgt, 0          # zero on the path that reaches the call
        elif mn == "lea" and tgt is not None and op.split(",")[0] in _REG64:
            regs[_REG64[op.split(",")[0]]] = tgt
        elif mn in ("mov", "movabs") and op.split(",")[0] in _REG64 and re.fullmatch(r"\w+, (0x[0-9a-f]+|\d+)", op):
            regs[_REG64[op.split(",")[0]]] = int(op.split(", ")[1], 0)
        elif mn == "xor" and op.split(", ")[0] == op.split(", ")[-1] and op.split(",")[0] in _REG64:
            regs[_REG64[op.split(",")[0]]] = 0
        elif mn == "mov" and " ptr [" in op and ("[r11 - " in op or "[rsp + " in op):
            dst, src = op.split("], ")
            k = int(re.search(r"(0x[0-9a-f]+|\d+)$", dst).group(1), 0)
            slot = (frame - k) if "[r11 - " in dst and uses_r11 and frame is not None else k
            if "[r11 - " in dst and not uses_r11:
                return None
            if src in _REG64:
                stack[slot] = regs.get(_REG64[src])
            elif re.fullmatch(r"0x[0-9a-f]+|\d+", src):
                stack[slot] = int(src, 0)
            else:
                stack[slot] = None                 # a saved non-volatile register, not an argument
        elif mn == "call":
            if not op.startswith("0x"):
                return None
            out = {k: (regs.get(v) if isinstance(v, str) else stack.get(v)) for k, v in _ARGS.items()}
            out["body"], out["psc_load"] = int(op, 16), psc_load
            # The function returns after re-reading PrivateStaticClass.
            out["ret_end"] = None
            tail = b[ins.address + ins.size - rva:]
            for t in _MD.disasm(tail, ins.address + ins.size):
                if t.mnemonic == "ret":
                    out["ret_end"] = t.address + 1
                    break
            return out if out["ret_end"] else None
    return None


def main() -> int:
    assert len(GPSC162) == 162 and len(GPSC151) == 151, (len(GPSC162), len(GPSC151))
    img = PEImage()
    dimg = load_decrypted(img)
    if dimg is None:
        print("needs the validated decrypted image", file=sys.stderr)
        return 1
    base = img.image_base
    allrf = {rf.begin: rf for rf in img.runtime_functions()}
    rd = next(s for s in img.sections if s.name == ".rdata")
    rdata = img.read(rd.rva, rd.rawsize)
    order = json.loads(UNITY_ORDER.read_text(encoding="utf-8"))
    refl = json.loads((ROOT / "analysis" / "reflection-natives.json").read_text(encoding="utf-8"))
    stats = Counter()

    def read(rva: int, n: int) -> bytes | None:
        try:
            return dimg.read(rva, n)
        except ValueError:
            return None

    classes = {}
    for unit in order["units"]:
        for it in unit["items"]:
            if it["kind"] == "class":
                classes[it["name"]] = dict(it)
    by_static_class = {int(c["static_class"], 16): n for n, c in classes.items()}

    # Decode GetPrivateStaticClass through the StaticClass thunk. The common 151/162-byte forms
    # are checked against their templates; every form is decoded by following the instruction
    # stream to the GetPrivateStaticClassBody call (64-bit cast flags, shrink-wrapped intrinsics).
    for name, c in classes.items():
        sc = int(c["static_class"], 16)
        b = read(sc, 5)
        gpsc = sc + 5 + struct.unpack_from("<i", b, 1)[0] if b and b[0] == 0xE9 else None
        c["gpsc"] = None
        if gpsc is None or gpsc not in allrf:
            stats["gpsc_not_located"] += 1
            continue
        n = allrf[gpsc].end - gpsc
        if n == 162:
            stats["gpsc_template_162"] += shape(read(gpsc, n), gpsc, GPSC162, GPSC162_FIELDS) is not None
        elif n == 151:
            stats["gpsc_template_151"] += shape(read(gpsc, n), gpsc, GPSC151, GPSC151_FIELDS) is not None
        f = decode_gpsc(read(gpsc, 0x200), gpsc)
        if not f or f["psc"] != f["psc_load"] or None in (f["super"], f["within"], f["size"], f["flags"]):
            stats["gpsc_not_decoded"] += 1
            continue
        end = allrf[gpsc].end
        while end in allrf and allrf[end].end and end < f["ret_end"]:   # chained fragments are contiguous
            end = allrf[end].end
        c["gpsc"] = gpsc
        c["gpsc_end"] = max(end, f["ret_end"]) if n < 64 else allrf[gpsc].end
        c["decoded"] = f
    bodies = Counter(c["decoded"]["body"] for c in classes.values() if c.get("decoded"))
    body = bodies.most_common(1)[0][0]

    # Hierarchy and declaration values.
    for name, c in classes.items():
        f = c.get("decoded")
        if not f or f["body"] != body:
            c["decoded"] = None
            continue
        c["super"] = by_static_class.get(f["super"])
        c["within"] = by_static_class.get(f["within"])
        c["package_text"] = wstr(img, f["package"])
        c["config_text"] = wstr(img, f["config"])
        lit = f["name"] - 2 - (22 if f["flags"] & CLASS_DEPRECATED else 0)
        c["name_ok"] = wstr(img, lit) == name
        c["size"] = f["size"]
        c["flags"] = f["flags"]
        c["cast"] = f["cast"]
        stats["decoded"] += 1
        stats["name_literal_consistent"] += c["name_ok"]
        stats["size_matches_auto_initialize"] += c.get("sizeof") == f["size"]
    for name, c in classes.items():
        f = c.get("decoded")
        if f:
            sup = classes.get(c["super"]) if c.get("super") else None
            c["owns_aro"] = name == c.get("super") or sup is None or not sup.get("decoded") or \
                sup["decoded"]["aro"] != f["aro"]

    for name, spec in INTRINSIC.items():
        if name in classes and not classes[name].get("decoded"):
            classes[name].update(super=spec["super"], size=spec["size"], intrinsic=True)

    # Topological order (superclass first); unknown superclasses become roots.
    emitted, out_order = set(), []

    def visit(n, depth=0):
        if n in emitted or n not in classes or depth > 64:
            return
        s = classes[n].get("super")
        if s and s != n:
            visit(s, depth + 1)
        emitted.add(n)
        out_order.append(n)

    for n in sorted(classes):
        visit(n)

    natives = {c["class"]: c for c in refl["native_classes"] if c["class"] and c["static_register_natives_rva"]}
    model = uht_exec.build(dimg, base, classes, out_order, allrf, _MD)
    stats.update({f"vtable model: {k}": v for k, v in model["stats"].items()})
    decl_size = {}
    lines = [
        "// Generated by tools/codegen/uht_classes.py from the reflection data of",
        "// FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387). Do not edit by hand.",
        "// Every reflected class, superclasses first, with the DECLARE_CLASS members IMPLEMENT_CLASS uses.",
        "// Superclass, flags, cast flags, package, config name and sizeof are decoded from each class's",
        "// GetPrivateStaticClass. Opaque members only give sizeof(Class) its recovered value; the",
        "// layout is not reconstructed. Virtual slots are declared where analysis/vtables.json names",
        "// them, with placeholders for the gaps, so calls through them use the reference's offsets;",
        "// exec thunks calling only such slots are defined in the class fragments (tools/codegen/uht_exec.py).",
        "#pragma once",
        "",
        "".join(f"class {n};\n" for n in out_order),
        "// Enums the declared signatures use, in their UEnum::ECppForm (FEnumParams); only the form",
        "// and the underlying type are recovered, not the enumerators.",
        "\n".join(model["enums"]),
        "",
    ]
    for n in out_order:
        c = classes[n]
        sup = c.get("super") if c.get("decoded") or c.get("intrinsic") else None
        has_base = sup is not None and sup != n and sup in decl_size
        base_size = decl_size.get(sup, 0) if has_base else 0
        size = c.get("size") or c.get("sizeof")
        if size is not None and has_base and size < base_size:
            has_base, base_size = False, 0
        decl_size[n] = size if size is not None else base_size + 1
        body_lines = ["\tstatic UClass* GetPrivateStaticClass();", "public:"]
        if c.get("decoded"):
            body_lines += [
                f"\tenum {{StaticClassFlags=0x{c['flags']:08X}u}};",
                f"\ttypedef {sup} Super;",
                f"\ttypedef {c['within']} WithinClass;" if c.get("within") else "",
                f"\ttypedef {n} ThisClass;",
                "\tinline static UClass* StaticClass() { return GetPrivateStaticClass(); }",
                f"\tinline static const TCHAR* StaticPackage() {{ return TEXT(\"{c['package_text']}\"); }}",
                f"\tinline static EClassCastFlags StaticClassCastFlags() {{ return (EClassCastFlags)0x{c['cast']:016X}ull; }}",
                (f"\tstatic const TCHAR* StaticConfigName() {{ return TEXT(\"{c['config_text']}\"); }}"
                 if c.get("config_text") is not None else ""),
            ]
            if c.get("owns_aro"):
                body_lines.append("\tstatic void AddReferencedObjects(UObject* InThis, FReferenceCollector& Collector);")
        else:
            body_lines += ["\tinline static UClass* StaticClass() { return GetPrivateStaticClass(); }",
                           "\t// GetPrivateStaticClass not decoded (intrinsic class or other shape): no further members"]
        body_lines += model["decls"].get(n, [])
        body_lines.append(f"\tstatic void StaticRegisterNatives{n}();")
        nat = natives.get(n)
        if nat:
            body_lines += [f"\tstatic void exec{f['name']}(UObject* Context, FFrame& Stack, void* const Z_Param__Result);"
                           for f in nat["functions"]]
        if n in EXTRA_MEMBERS:
            body_lines += [f"#ifdef FNGC_EXTRA_MEMBERS_{n}", f"\tFNGC_EXTRA_MEMBERS_{n}", "#endif"]
        members = INTRINSIC.get(n, {}).get("members", []) if c.get("intrinsic") else []
        body_lines += [m for m, _ in members]
        pad = (decl_size[n] - base_size - (8 if n in model["roots_with_vptr"] else 0)
               - sum(size for _, size in members))
        if pad > 0:
            body_lines += ["private:", f"\tunsigned char Opaque[0x{pad:X}];  // sizeof({n}) = 0x{decl_size[n]:X}"
                           + ("" if size is not None else " (not recovered)")]
        head = f"class {n}" + (f" : public {sup}" if has_base else "")
        lines.append(head + "\n{\n" + "\n".join(x for x in body_lines if x) + "\n};\n")
        stats["declared"] += 1
    header = "\n".join(lines)

    # ClassParams of classes without UFunctions: the only FClassParams record whose
    # ClassNoRegisterFunc is the class's StaticClass.
    link_classes = {a["class"] for a in refl["function_link_arrays"] if a["class"]}
    sc_slots = defaultdict(list)
    sc_values = {base + int(c["static_class"], 16): n for n, c in classes.items()}
    lo_img, hi_img = base, base + img.size_of_image

    def is_ptr_or_null(v: int) -> bool:
        return v == 0 or lo_img <= v < hi_img

    for off in range(0, len(rdata) - 0x58, 8):
        v = struct.unpack_from("<Q", rdata, off)[0]
        n = sc_values.get(v)
        if n is None:
            continue
        # FClassParams of a class without UFunctions: dependency array, small counts, no function
        # table, property array, config name, a CppClassInfo pointer, interface array. The same
        # StaticClass address also appears in property metadata (ICF folds
        # Z_Construct_UClass_<C>_NoRegister into it), whose layout fails these checks.
        (_, deps, ndeps, _, links, nfuncs, props, nprops, cfg, cpp, ifaces, nifaces) = struct.unpack_from(
            "<QQiIQi4xQi4xQQQi4x", rdata, off)
        if (is_ptr_or_null(deps) and 0 <= ndeps < 256 and links == 0 and nfuncs == 0 and is_ptr_or_null(props)
                and 0 <= nprops < 4096 and is_ptr_or_null(cfg) and cpp and lo_img <= cpp < hi_img
                and is_ptr_or_null(ifaces) and 0 <= nifaces < 64):
            sc_slots[n].append(rd.rva + off)

    def singleton(rva):
        rf = allrf.get(rva)
        if rf is None or rf.end - rva != CREATOR_SIZE:
            return None
        b = read(rva, CREATOR_SIZE)
        if b is None or any(b[i] != TEMPLATE[i] for i in range(CREATOR_SIZE) if i not in MASK):
            return None
        return b

    outputs, gpsc_entries, nofunc_entries, symbols = {}, [], [], {}
    defer_entries, auto_entries = [], []
    thunk_fragments = set()
    for n in out_order:
        c = classes[n]
        if not c.get("decoded") or "auto_initialize" not in c:
            continue
        short = c["package"].rsplit("/", 1)[1]
        parts = [
            "// Generated by tools/codegen/uht_classes.py from the reflection data of\n"
            "// FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387). Do not edit by hand.\n"
            f"// Class {n} of {c['package']}: the IMPLEMENT_CLASS part of its UHT 4.20 output.\n\n"
            '#include "FortniteGameCode/UHTRecovered.h"\n\n']
        mine = [t for (k, _), t in sorted(model["thunks"].items()) if k == n]
        parts += mine
        thunk_fragments.add(n) if mine else None
        if n not in natives:
            parts.append(f"void {n}::StaticRegisterNatives{n}()\n{{\n}}\n")
        zrva = int(c["constructor"], 16)
        if n not in link_classes:
            recs = [r for r in sc_slots.get(n, []) if singleton(zrva) is not None]
            if len(recs) == 1:
                ext = set()
                syms = {}
                parts.append(class_constructor(n, {"class_params_rva": f"0x{recs[0]:08X}"}, [], zrva, set(), img,
                                               rdata, rd, base, allrf, ext, syms, evidence="static-class"))
                parts.insert(1, "".join(f"{e}\n" for e in sorted(ext)))
                symbols.update(syms)
                nofunc_entries.append({"start_rva": f"0x{zrva:08X}", "end_rva": f"0x{allrf[zrva].end:08X}",
                                       "name": f"Z_Construct_UClass_{n}", "class": n, "package": short})
                stats["nofunc_constructors"] += 1
            else:
                stats["nofunc_classparams_not_unique"] += 1
        f = c["decoded"]
        auto = int(c["auto_initialize"], 16)
        parts.append(
            f"// IMPLEMENT_CLASS({n}, {c.get('crc', 0)}u)\n"
            f"// Original dynamic initializer: RVA 0x{auto:08X} (leaf; CRC and sizeof are its arguments)\n"
            f"static TClassCompiledInDefer<{n}> AutoInitialize{n}(TEXT(\"{n}\"), sizeof({n}), {c.get('crc', 0)}u);\n")
        parts.append(
            f"// Original FortniteClient-Win64-Shipping.exe: RVA 0x{c['gpsc']:08X} (end 0x{c['gpsc_end']:08X})\n"
            f"// Original VA: 0x{base + c['gpsc']:016X} | File offset: 0x{img.rva_to_off(c['gpsc']):08X}\n"
            f"// Recovery: confirmed (IMPLEMENT_CLASS({n}, {c.get('crc', 0)}u); reached from {n}::StaticClass) | "
            "Matching: see analysis/functions-uht-gpsc.json\n"
            f"UClass* {n}::GetPrivateStaticClass()\n{{\n"
            "\tstatic UClass* PrivateStaticClass = NULL;\n\tif (!PrivateStaticClass)\n\t{\n"
            "\t\t/* this could be handled with templates, but we want it external to avoid code bloat */\n"
            "\t\tGetPrivateStaticClassBody(\n"
            "\t\t\tStaticPackage(),\n"
            f"\t\t\t(TCHAR*)TEXT(\"{n}\") + 1 + ((StaticClassFlags & CLASS_Deprecated) ? 11 : 0),\n"
            "\t\t\tPrivateStaticClass,\n"
            f"\t\t\tStaticRegisterNatives{n},\n"
            f"\t\t\tsizeof({n}),\n"
            f"\t\t\t(EClassFlags){n}::StaticClassFlags,\n"
            f"\t\t\t{n}::StaticClassCastFlags(),\n"
            f"\t\t\t{n}::StaticConfigName(),\n"
            f"\t\t\t(UClass::ClassConstructorType)InternalConstructor<{n}>,\n"
            f"\t\t\t(UClass::ClassVTableHelperCtorCallerType)InternalVTableHelperCtorCaller<{n}>,\n"
            f"\t\t\t&{n}::AddReferencedObjects,\n"
            f"\t\t\t&{n}::Super::StaticClass,\n"
            f"\t\t\t&{n}::WithinClass::StaticClass\n"
            "\t\t);\n\t}\n\treturn PrivateStaticClass;\n}\n")
        cid = int(c["compiled_in_defer"], 16)
        parts.append(
            f"UClass* Z_Construct_UClass_{n}();\n"
            f"// Original dynamic initializer: RVA 0x{cid:08X}\n"
            f"static FCompiledInDefer Z_CompiledInDefer_UClass_{n}(Z_Construct_UClass_{n}, &{n}::StaticClass, "
            f"TEXT(\"{c['package']}\"), TEXT(\"{n}\"), false, nullptr, nullptr, nullptr);\n")
        if c.get("config_text") is None or not c.get("within"):
            stats["gpsc_skipped_incomplete_declaration"] += 1
            continue
        outputs[FRAG_DIR / short / f"{n}.gen.cpp"] = "".join(parts)
        gpsc_entries.append({"start_rva": f"0x{c['gpsc']:08X}", "end_rva": f"0x{c['gpsc_end']:08X}",
                             "name": f"{n}::GetPrivateStaticClass", "class": n, "package": short})
        if cid in allrf:
            defer_entries.append({"start_rva": f"0x{cid:08X}", "end_rva": f"0x{allrf[cid].end:08X}",
                                  "name": f"dynamic initializer for Z_CompiledInDefer_UClass_{n}", "class": n,
                                  "package": short})
        auto_entries.append({"start_rva": f"0x{auto:08X}", "end_rva": f"0x{auto + AUTO_INITIALIZER_SIZE:08X}",
                             "name": f"dynamic initializer for AutoInitialize{n}", "class": n, "package": short})
        stats["gpsc_emitted"] += 1

    HEADER.write_text(header, encoding="utf-8") if not HEADER.exists() or HEADER.read_text(encoding="utf-8") != header else None
    stats["files_written"], stats["files_removed"] = sync_tree(FRAG_DIR, outputs)
    head = {"schema_version": 1, "generated_by": "tools/codegen/uht_classes.py"}
    src_tpl = "FortniteGameCode/Source/Generated/UHT/Classes/{package}/{class}.gen.cpp"
    obj_tpl = UNIT_OBJECT
    units = unit_of()
    exec_entries = [e for e in model["entries"] if e["class"] in thunk_fragments]
    stats["vtable model: exec thunk entries without a class fragment"] = len(model["entries"]) - len(exec_entries)
    for e in gpsc_entries + nofunc_entries + defer_entries + auto_entries + exec_entries:
        e["unit"] = units[("class", e["class"])]
    for e in exec_entries:
        e["ufunction"] = e["name"].split("::exec", 1)[1]
        e["package"] = classes[e["class"]]["package"].rsplit("/", 1)[1]
    dump_compact(EXEC_MANIFEST, {**head,
        "evidence": ("Exec thunk <Class>::exec<Name> (analysis/reflection-natives.json) of a UFunction whose native is "
                     "virtual: it calls only vtable slots named in analysis/vtables.json, with the signature from the "
                     "UFunction's FFunctionParams. Leaf thunks (no .pdata entry) are outside the denominator."),
        "entry_defaults": {"category": "uht-exec-thunk", "source": src_tpl,
                           "object": obj_tpl, "symbol": EXEC_SYMBOL, "name_confidence": "confirmed", "compact": True},
        "functions": exec_entries})
    dump_compact(GPSC_MANIFEST, {**head,
        "evidence": ("<Class>::GetPrivateStaticClass (IMPLEMENT_CLASS): the jmp target of <Class>::StaticClass, which "
                     "the class's FCompiledInDefer initializer registers; 151/162-byte shape."),
        "entry_defaults": {"category": "uht-getprivatestaticclass", "source": src_tpl, "object": obj_tpl,
                           "symbol": "?GetPrivateStaticClass@{class}@@CAPEAVUClass@@XZ", "name_confidence": "confirmed",
                           "compact": True},
        "functions": gpsc_entries})
    dump_compact(DEFER_MANIFEST, {**head,
        "evidence": ("Dynamic initializer of Z_CompiledInDefer_UClass_<Class>: the 58-byte .CRT$XCU entry registering "
                     "Z_Construct_UClass_<Class> and <Class>::StaticClass (analysis/unity-order.json)."),
        "entry_defaults": {"category": "uht-class-compiledindefer", "source": src_tpl, "object": obj_tpl,
                           "symbol": "??__EZ_CompiledInDefer_UClass_{class}@@YAXXZ", "name_confidence": "confirmed",
                           "compact": True},
        "functions": defer_entries})
    dump_compact(AUTO_MANIFEST, {**head,
        "evidence": ("Dynamic initializer of AutoInitialize<Class> (IMPLEMENT_CLASS's TClassCompiledInDefer): the leaf "
                     ".CRT$XCU entry passing TEXT(\"<Class>\"), sizeof and the CRC to UClassCompiledInDefer. No .pdata "
                     "entry, so outside the denominator."),
        "entry_defaults": {"category": "uht-class-autoinitialize", "source": src_tpl, "object": obj_tpl,
                           "symbol": "??__EAutoInitialize{class}@@YAXXZ", "name_confidence": "confirmed",
                           "compact": True},
        "functions": auto_entries})
    dump_compact(NOFUNC_MANIFEST, {**head,
        "evidence": ("Z_Construct_UClass_<Class> of a class without UFunctions: the constructor its FCompiledInDefer "
                     "initializer registers; ClassParams is the only FClassParams naming <Class>::StaticClass."),
        "entry_defaults": {"category": "uht-class-constructor", "source": src_tpl, "object": obj_tpl,
                           "symbol": "?{name}@@YAPEAVUClass@@XZ", "name_confidence": "confirmed", "compact": True},
        "functions": nofunc_entries})
    SYMBOLS.write_text(json.dumps({
        "schema_version": 2, "generated_by": "tools/codegen/uht_classes.py",
        "evidence_codes": {"static-class": "the only FClassParams record whose ClassNoRegisterFunc is the class's StaticClass (named by its FCompiledInDefer initializer)"},
        "symbols": symbols}, separators=(",", ":")).replace('],"', '],\n"') + "\n", encoding="utf-8")
    print(dict(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
