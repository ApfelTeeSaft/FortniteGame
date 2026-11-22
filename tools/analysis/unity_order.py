"""Recover the source order of UHT registration code from the CRT dynamic-initializer table.

MSVC records every dynamic initializer of a translation unit in .CRT$XCU in definition order,
and the linker concatenates those contributions object by object. The reference's table is
therefore a sequence, in unity-file source order, of every registration object UHT 4.20
emits:

  class   TClassCompiledInDefer<C> AutoInitializeC  (leaf: CRC, TEXT("C"), sizeof(C))
          FCompiledInDefer Z_CompiledInDefer_UClass_C (58 bytes: Z_Construct_UClass_C, C::StaticClass)
  struct  FCompiledInDeferStruct (66 bytes: <S>::StaticStruct) and, after it,
          FScriptStruct_<Pkg>_StaticRegisterNatives<S> (92 bytes: TEXT("<S>"))
  enum    FCompiledInDeferEnum (66 bytes: <E>_StaticEnum)

Translation units are delimited by a header-defined 16-byte constant that most unity files
include. Its leaf initializer, "movaps xmm0, [K]; movaps [slot], xmm0; ret", is the first
entry of each unit; K is the constant most initializers copy. Some small plugin modules'
units lack that header. Because a unity file never spans two modules, a change of package
also starts a new unit.

The constant is GlobalVectorConstants::FloatOne (UnrealMathVectorConstants.h). A unit's other
such constants follow it, one leaf initializer each; the reference keeps only those a unit
uses. Each unit that opens at a marker records them ("vector_constants") by value, named in
header definition order (the order of .CRT$XCU). Two values are ambiguous: FloatOne is also
RotationSignificantThreshold (1 - DELTA*DELTA rounds to 1.0f), and SignMask's bits are also
IntSignMask's. Header order settles the first (a later constant cannot precede XYZMask), and
the first-defined name is taken for the second.

Nothing here reads a .bss address. The order recovered is evidence of source order, and the
generators use it to lay out translation units like the original unity files
(docs/REVERSE_ENGINEERING.md, "Module layout model").

Usage: python tools/analysis/unity_order.py   -> analysis/unity-order.json
Publishes names and RVAs only.
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
from pe import PEImage  # noqa: E402
from uht_structs import CID_FIELDS, CID_TEMPLATE, SRN_FIELDS, SRN_TEMPLATE, shape, wstr  # noqa: E402

OUT = ROOT / "analysis" / "unity-order.json"
# FCompiledInDefer (class): rcx Z_Construct_UClass_C, rdx C::StaticClass, r8 TEXT("C"), r9 package.
CLASS_CID_TEMPLATE = bytes.fromhex(
    "4883ec4833c04c8d0d0000000048894424304c8d0500000000488944242848"
    "8d1500000000488d0d0000000088442420e8000000004883c448c3")
CLASS_CID_FIELDS = {"package": (0x09, "rel"), "name": (0x15, "rel"), "static_class": (0x21, "rel"),
                    "constructor": (0x28, "rel"), "defer": (0x31, "rel")}
# TClassCompiledInDefer<C> (leaf, tail call): r9d CRC, rdx TEXT("C"), r8d sizeof(C), rcx object.
AUTO_TEMPLATE = bytes.fromhex("41b900000000488d150000000041b800000000488d0d00000000e900000000")
AUTO_FIELDS = {"crc": (0x02, "imm"), "name": (0x09, "rel"), "size": (0x0F, "imm"), "object": (0x16, "rel"),
               "ctor": (0x1B, "rel")}


# GlobalVectorConstants in header definition order (Math/UnrealMathVectorConstants.h, then
# VectorRegister.h): name -> the 16 bytes its MakeVectorRegister* initializer stores.
def _f(*v):
    return struct.pack("<4f", *v)


def _u(*v):
    return struct.pack("<4I", *[x & 0xFFFFFFFF for x in v])


_PI, _SB = 3.1415926535897932, 1 << 31
VECTOR_CONSTANTS = [
    ("FloatOne", _f(1, 1, 1, 1)), ("FloatZero", _f(0, 0, 0, 0)), ("FloatMinusOne", _f(-1, -1, -1, -1)),
    ("Float0001", _f(0, 0, 0, 1)), ("SmallLengthThreshold", _f(*[1.e-8] * 4)),
    ("FloatOneHundredth", _f(*[0.01] * 4)), ("Float111_Minus1", _f(1, 1, 1, -1)),
    ("FloatMinus1_111", _f(-1, 1, 1, 1)), ("FloatOneHalf", _f(*[0.5] * 4)), ("FloatMinusOneHalf", _f(*[-0.5] * 4)),
    ("KindaSmallNumber", _f(*[1.e-4] * 4)), ("SmallNumber", _f(*[1.e-8] * 4)),
    ("ThreshQuatNormalized", _f(*[0.01] * 4)), ("BigNumber", _f(*[3.4e+38] * 4)),
    ("IntOne", _u(1, 1, 1, 1)), ("IntZero", _u(0, 0, 0, 0)), ("IntMinusOne", _u(-1, -1, -1, -1)),
    ("QINV_SIGN_MASK", _f(-1, -1, -1, 1)), ("QMULTI_SIGN_MASK0", _f(1, -1, 1, -1)),
    ("QMULTI_SIGN_MASK1", _f(1, 1, -1, -1)), ("QMULTI_SIGN_MASK2", _f(-1, 1, 1, -1)),
    ("DEG_TO_RAD", _f(*[_PI / 180.0] * 4)), ("DEG_TO_RAD_HALF", _f(*[(_PI / 180.0) * 0.5] * 4)),
    ("RAD_TO_DEG", _f(*[180.0 / _PI] * 4)), ("XYZMask", _u(0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0)),
    ("SignBit", _u(_SB, _SB, _SB, _SB)), ("SignMask", _u(~_SB, ~_SB, ~_SB, ~_SB)),
    ("IntSignBit", _u(_SB, _SB, _SB, _SB)), ("IntSignMask", _u(~_SB, ~_SB, ~_SB, ~_SB)),
    ("AllMask", _u(*[0xFFFFFFFF] * 4)), ("IntAllMask", _u(*[0xFFFFFFFF] * 4)),
    ("FloatInfinity", _u(*[0x7F800000] * 4)), ("Pi", _f(*[_PI] * 4)), ("TwoPi", _f(*[2 * _PI] * 4)),
    ("PiByTwo", _f(*[0.5 * _PI] * 4)), ("PiByFour", _f(*[0.25 * _PI] * 4)), ("OneOverPi", _f(*[1 / _PI] * 4)),
    ("OneOverTwoPi", _f(*[1 / (2 * _PI)] * 4)), ("Float255", _f(*[255.0] * 4)), ("Float127", _f(*[127.0] * 4)),
    ("FloatNeg127", _f(*[-127.0] * 4)), ("Float360", _f(*[360.0] * 4)), ("Float180", _f(*[180.0] * 4)),
    ("FloatTwo", _f(*[2.0] * 4)), ("FloatAlmostTwo", _u(*[0x3FFFFFFF] * 4)),
    ("AnimWeightThreshold", _f(*[0.00001] * 4)), ("RotationSignificantThreshold", _f(*[1.0 - 0.00001 * 0.00001] * 4)),
]


def name_vector_constants(values: list[bytes]) -> list[str] | None:
    """Names for a unit's constant values in .CRT$XCU order: each the first header constant,
    after the previous one's, with that value. None if a value has no such constant."""
    names, pos = [], -1
    for v in values:
        hit = next((h for h in range(pos + 1, len(VECTOR_CONSTANTS)) if VECTOR_CONSTANTS[h][1] == v), None)
        if hit is None:
            return None
        names.append(VECTOR_CONSTANTS[hit][0])
        pos = hit
    return names


def constant_initializer(code: bytes | None, rva: int) -> int | None:
    """K of a leaf 'movaps|movdqa xmm0, [K]; movaps|movdqa [slot], xmm0; ret' initializer."""
    if not code:
        return None
    if code[:3] == b"\x0f\x28\x05" and code[7:10] == b"\x0f\x29\x05" and code[14] == 0xC3:
        return rva + 7 + struct.unpack_from("<i", code, 3)[0]
    if code[:4] == b"\x66\x0f\x6f\x05" and code[8:12] == b"\x66\x0f\x7f\x05" and code[16] == 0xC3:
        return rva + 8 + struct.unpack_from("<i", code, 4)[0]
    return None


def place_package_delegates(img, dimg, allrf, base, units: list[dict]) -> Counter:
    """Insert package-scope delegates (no .CRT$XCU entry) into the units' item lists.

    A package's delegates are listed in the SingletonFuncArray of its FPackageParams; those
    whose FFunctionParams OuterFunc is the package singleton are package-scope (the array also
    lists class-scope delegates and noexport structs). UHT emits a header's package-scope
    delegates first, before its enums, structs and classes. Their position follows from the
    order of namespace-scope parameter records in .data, which is definition order:
    FFunctionParams of creators and FStructParams. EnumParams is a function-local static
    whose place reflects code generation, so enums are not anchors. Between the anchors
    before (P) and after (N) a delegate:
      * if an enum lies between them, the delegate precedes the first such enum;
      * otherwise classes without UFunctions (no .data record) may lie between. Their
        FClassParams and the delegate's PropPointers array are both namespace-scope .rdata
        definitions, so the delegate follows those classes whose FClassParams precede its
        PropPointers. A delegate without parameters precedes N.
    """
    stats = Counter()
    TEMPLATE_47 = bytes.fromhex("4883ec28488b05000000004885c0751a488d1500000000488d0d00000000e800000000488b05000000004883c428c3")
    MASK_47 = set(range(7, 11)) | set(range(0x13, 0x17)) | set(range(0x1A, 0x1E)) | set(range(0x1F, 0x23)) | set(range(0x26, 0x2A))

    def singleton(rva):
        rf = allrf.get(rva)
        if rf is None or rf.end - rva != 47:
            return None
        try:
            b = dimg.read(rva, 47)
        except ValueError:
            return None
        if any(b[i] != TEMPLATE_47[i] for i in range(47) if i not in MASK_47):
            return None
        return (rva + 0xB + struct.unpack_from("<i", b, 7)[0], rva + 0x17 + struct.unpack_from("<i", b, 0x13)[0],
                rva + 0x23 + struct.unpack_from("<i", b, 0x1F)[0])

    def cstr(rva):
        b = img.read(rva, 300)
        n = b.find(b"\0")
        return b[:n].decode("ascii", "replace") if n > 0 else None

    def lea_singleton(fn, callee_ok):
        """The 47-byte singleton a StaticStruct-like function LEA-loads into rcx."""
        try:
            b = dimg.read(fn, 0x80)
        except ValueError:
            return None
        for i in range(len(b) - 7):
            if b[i:i + 3] == b"\x48\x8d\x0d":
                t = fn + i + 7 + struct.unpack_from("<i", b, i + 3)[0]
                s = singleton(t)
                if s and callee_ok(s[2]):
                    return s
        return None

    refl = json.loads((ROOT / "analysis" / "reflection-natives.json").read_text(encoding="utf-8"))
    # Package singletons by package name, and their delegate creators.
    packages = {}
    for u in units:
        for it in u["items"]:
            packages.setdefault(it["package"], None)
    construct_function = None
    delegates = []
    for rva, rf in allrf.items():
        s = singleton(rva) if rf.end - rva == 47 else None
        if s is None:
            continue
        rec = s[1]
        name = cstr(struct.unpack("<Q", img.read(rec, 8))[0] - base) if img.section_of(rec).name == ".rdata" else None
        if name and name.startswith("/Script/") and name in packages:
            packages[name] = (rva, rec)
    creators_of_class = {a["class"]: [int(f["construct_rva"], 16) for f in a["functions"]]
                         for a in refl["function_link_arrays"] if a["class"]}
    entries = []
    for pname, pk in packages.items():
        if pk is None:
            continue
        prva, prec = pk
        arr, n = struct.unpack_from("<Qi", img.read(prec + 0x18, 12))   # SingletonFuncArray, NumSingletons
        for i in range(n):
            g = struct.unpack("<Q", img.read(arr - base + 8 * i, 8))[0] - base
            s = singleton(g)
            if s is not None:
                entries.append((pname, prva, g, s))
    # Delegates far outnumber noexport structs in these arrays: their callee is ConstructUFunction.
    construct_function = Counter(s[2] for *_, s in entries).most_common(1)[0][0]
    for pname, prva, g, s in entries:
        if s[2] != construct_function:
            continue
        outer, nameptr = struct.unpack("<QQ", img.read(s[1], 16))
        if outer - base == prva:
            delegates.append({"kind": "delegate", "name": cstr(nameptr - base), "package": pname,
                              "constructor": f"0x{g:08X}", "_rec": s[1], "_props": struct.unpack(
                                  "<Q", img.read(s[1] + 0x28, 8))[0]})
    delegate_rvas = {int(d["constructor"], 16) for d in delegates}

    # Anchors: (record address, unit index, item index).
    anchors = []
    for ui, u in enumerate(units):
        for ii, it in enumerate(u["items"]):
            rec = None
            if it["kind"] == "class":
                recs = [singleton(c)[1] for c in creators_of_class.get(it["name"], [])
                        if c not in delegate_rvas and singleton(c)]
                rec = min(recs) if recs else None
                s = singleton(int(it["constructor"], 16))
                it["_classparams"] = s[1] if s else None
            elif it["kind"] == "struct":
                s = lea_singleton(int(it["static_struct"], 16), lambda c: c != construct_function)
                rec = s[1] if s else None
            if rec is not None:
                anchors.append((rec, ui, ii))
    anchors.sort()
    keys = [a[0] for a in anchors]
    inserts = defaultdict(list)       # (unit, position) -> delegates, in record order
    for d in sorted(delegates, key=lambda d: d["_rec"]):
        j = bisect.bisect_right(keys, d["_rec"])
        P = anchors[j - 1] if j else None
        N = anchors[j] if j < len(anchors) else None
        if N is None:
            if P is None:
                stats["delegates_unplaced"] += 1
                continue
            ui, pos, how = P[1], P[2] + 1, "after last anchor"
        else:
            ui = N[1]
            items = units[ui]["items"]
            lo = P[2] + 1 if P is not None and P[1] == N[1] else 0   # a new unit starts after P
            between = range(lo, N[2])
            enum_at = next((k for k in between if items[k]["kind"] == "enum"), None)
            classes = [k for k in between if items[k]["kind"] == "class"]
            if enum_at is not None:
                pos, how = enum_at, "before first enum between anchors"
            elif classes and d["_props"]:
                after = [k for k in classes if items[k].get("_classparams")
                         and items[k]["_classparams"] < d["_props"] - base]
                pos = (max(after) + 1) if after else lo
                how = "after classes whose FClassParams precede its PropPointers"
            elif classes:
                pos, how = N[2], "before next anchor (no PropPointers to order classes without UFunctions)"
            else:
                pos, how = N[2], "before next anchor"
        inserts[(ui, pos)].append(d)
        stats[f"delegates: {how}"] += 1
    for (ui, pos) in sorted(inserts, reverse=True):
        for d in reversed(inserts[(ui, pos)]):
            units[ui]["items"].insert(pos, {k: v for k, v in d.items() if not k.startswith("_")})
    for u in units:
        for it in u["items"]:
            it.pop("_classparams", None)
    stats["package_delegates"] = len(delegates)
    return stats


def place_package_init(img, dimg, allrf, base, units: list[dict]) -> Counter:
    """Locate each module's <Module>.init.gen.cpp (the package singleton) in its unity files.

    A StaticStruct or StaticEnum compiled after the package singleton's definition inlines it
    (it calls ConstructUPackage itself); one compiled earlier, or in another unit, calls it.
    MSVC inlines it even when it is defined later in the unit, so a calling item and
    init.gen.cpp are never in the same translation unit. UBT's unity files include .gen.cpp
    files in alphabetical order, as the recovered item order shows. A consistent module
    therefore has one unit in which the items switch from calling to inlining, and
    init.gen.cpp opens a unity file between the last calling and the first inlining item.
    Within that window the alphabetical rule decides: init.gen.cpp precedes the first item
    whose header-like name (class or struct name without its prefix) sorts after
    "<Module>.init", case-insensitively; otherwise it precedes the first inlining item. The
    unit is split there. Each struct and enum item records its form ("static_inlined"); a
    module whose boundary is absent or inconsistent records no position.
    """
    from capstone import CS_ARCH_X86, CS_MODE_64, Cs
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    stats = Counter()

    def calls_of(fn):
        try:
            b = dimg.read(fn, 0x100)
        except ValueError:
            return []
        out = []
        for ins in md.disasm(b, fn):
            if ins.mnemonic == "call" and ins.op_str.startswith("0x"):
                out.append(int(ins.op_str, 16))
            if ins.mnemonic == "ret":
                break
        return out

    # ConstructUPackage: the callee shared by the package singletons (47-byte UHT shape whose
    # parameters name a /Script/ package).
    callees = Counter()
    for rva, rf in allrf.items():
        if rf.end - rva != 47:
            continue
        try:
            b = dimg.read(rva, 47)
        except ValueError:
            continue
        if b[:7] != bytes.fromhex("4883ec28488b05") or b[0x1E] != 0xE8:
            continue
        rec = rva + 0x17 + struct.unpack_from("<i", b, 0x13)[0]
        sec = img.section_of(rec)
        if sec is None or sec.name != ".rdata":
            continue
        nameptr = struct.unpack("<Q", img.read(rec, 8))[0]
        if base <= nameptr < base + img.size_of_image and img.read(nameptr - base, 8) == b"/Script/":
            callees[rva + 0x23 + struct.unpack_from("<i", b, 0x1F)[0]] += 1
    construct_package = callees.most_common(1)[0][0]

    splits = []
    by_package = defaultdict(list)       # package -> [(unit index, item index, inlined)]
    for ui, u in enumerate(units):
        for ii, it in enumerate(u["items"]):
            fn = it.get("static_struct") or it.get("static_enum")
            if fn and it["kind"] in ("struct", "enum"):
                it["static_inlined"] = construct_package in calls_of(int(fn, 16))
                by_package[it["package"]].append((ui, ii, it["static_inlined"]))
    for pkg, seq in by_package.items():
        inl = [s for s in seq if s[2]]
        if not inl:
            stats["init_not_located (no inlining item)"] += 1
            continue
        ui = inl[0][0]
        first = min(s[1] for s in inl)
        consistent = all(s[0] == ui and s[1] >= first for s in inl) and \
            all(not (s[0] == ui and s[1] > first) for s in seq if not s[2])
        if not consistent:
            stats["init_not_located (inconsistent forms)"] += 1
            continue
        last_plain = max([s[1] for s in seq if s[0] == ui and not s[2]], default=-1)
        key = (pkg.rsplit("/", 1)[1] + ".init").lower()
        items = units[ui]["items"]
        pos = first
        for k in range(last_plain + 1, first + 1):
            it = items[k]
            name = it["name"][1:] if it["kind"] == "class" else it["name"] if it["kind"] == "struct" else None
            if name is not None and name.lower() > key:
                pos = k
                break
        splits.append((ui, pos))
        stats["init_located"] += 1
    # MSVC inlines a function defined later in the same translation unit too, so items that
    # call the package singleton cannot share a unit with init.gen.cpp at all: init.gen.cpp
    # opens a unity file of its own. A unit is split there when items precede it.
    for ui, pos in sorted(splits, reverse=True):
        u = units[ui]
        if pos == 0:
            u["package_init_before"] = 0
            continue
        head, tail = u["items"][:pos], u["items"][pos:]
        lo, hi = u["table_range"]
        cut = next((it["table_index"] for it in tail if "table_index" in it), hi)
        u["items"] = head
        u["table_range"] = [lo, cut]
        units.insert(ui + 1, {"index": None, "marker_unit": u["marker_unit"],
                              "table_range": [cut, hi],
                              "package": u["package"], "split": "init.gen.cpp opens a unity file",
                              "package_init_before": 0, "items": tail})
        stats["units_split_at_init"] += 1
    for k, u in enumerate(units):
        u["index"] = k
    return stats


def main() -> int:
    assert len(CLASS_CID_TEMPLATE) == 58, len(CLASS_CID_TEMPLATE)
    img = PEImage()
    dimg = load_decrypted(img)
    if dimg is None:
        print("needs the validated decrypted image", file=sys.stderr)
        return 1
    base = img.image_base
    text = img.sections[0]
    allrf = {rf.begin: rf for rf in img.runtime_functions()}

    def read(rva: int, n: int) -> bytes | None:
        try:
            return dimg.read(rva, n)
        except ValueError:
            return None

    def is_class_cid(rva: int):
        rf = allrf.get(rva)
        if rf is None or rf.end - rva != len(CLASS_CID_TEMPLATE):
            return None
        return shape(read(rva, len(CLASS_CID_TEMPLATE)), rva, CLASS_CID_TEMPLATE, CLASS_CID_FIELDS)

    # The initializer table: the maximal run of non-null .text pointers that contains class
    # registration initializers.
    rd = next(s for s in img.sections if s.name == ".rdata")
    raw = img.read(rd.rva, rd.rawsize)
    lo_t, hi_t = base + text.rva, base + text.rva + text.vsize
    seed = None
    for off in range(0, len(raw) - 8, 8):
        v = struct.unpack_from("<Q", raw, off)[0]
        if lo_t <= v < hi_t and is_class_cid(v - base):
            seed = off
            break
    if seed is None:
        print("no class registration initializer found", file=sys.stderr)
        return 1

    def code_ptr(off: int) -> bool:
        v = struct.unpack_from("<Q", raw, off)[0]
        return lo_t <= v < hi_t

    a = seed
    while a >= 8 and code_ptr(a - 8):
        a -= 8
    b = seed
    while b + 8 < len(raw) and code_ptr(b + 8):
        b += 8
    table = [struct.unpack_from("<Q", raw, o)[0] - base for o in range(a, b + 8, 8)]

    # Translation-unit markers: the leaf copy of the most common 16-byte constant.
    marker_src = {}
    for i, v in enumerate(table):
        bb = read(v, 15)
        if bb and bb[:3] == bytes.fromhex("0f2805") and bb[7:10] == bytes.fromhex("0f2905") and bb[14] == 0xC3:
            marker_src[i] = v + 7 + struct.unpack_from("<i", bb, 3)[0]
    marker_const = Counter(marker_src.values()).most_common(1)[0][0]
    markers = sorted(i for i, k in marker_src.items() if k == marker_const)

    # Classify registration initializers.
    entries = []
    cid_callees = Counter()
    for i, v in enumerate(table):
        rf = allrf.get(v)
        n = rf.end - v if rf else None
        if n == len(CLASS_CID_TEMPLATE):
            f = is_class_cid(v)
            if f:
                entries.append((i, "class_cid", v, f))
                continue
        if n == len(CID_TEMPLATE):
            f = shape(read(v, n), v, CID_TEMPLATE, CID_FIELDS)
            if f:
                cid_callees[f["defer"]] += 1
                entries.append((i, "cid", v, f))
                continue
        if n == len(SRN_TEMPLATE):
            f = shape(read(v, n), v, SRN_TEMPLATE, SRN_FIELDS)
            if f:
                entries.append((i, "srn", v, f))
                continue
        if rf is None:
            f = shape(read(v, len(AUTO_TEMPLATE)), v, AUTO_TEMPLATE, AUTO_FIELDS)
            if f:
                entries.append((i, "auto", v, f))

    # The struct registration callee is the one whose initializers are followed by a
    # StaticRegisterNatives initializer naming the same type; the other one registers enums.
    votes = Counter()
    for (i, k, v, f), nxt in zip(entries, entries[1:]):
        if k == "cid" and nxt[1] == "srn" and wstr(img, f["name"]) == wstr(img, nxt[3]["name"]):
            votes[f["defer"]] += 1
    struct_callee = votes.most_common(1)[0][0]
    enum_callee = next(c for c, _ in cid_callees.most_common() if c != struct_callee)

    tu_of = {}
    bounds = markers + [len(table)]
    for k, (s, e) in enumerate(zip(bounds, bounds[1:])):
        for i in range(s, e):
            tu_of[i] = k

    tus = defaultdict(list)
    stats = Counter()
    pending_auto = {}
    for i, kind, v, f in entries:
        tu = tu_of.get(i)
        if kind == "auto":
            pending_auto[wstr(img, f["name"])] = (i, v, f)
            continue
        if kind == "class_cid":
            name = wstr(img, f["name"])
            item = {"kind": "class", "name": name, "package": wstr(img, f["package"]),
                    "constructor": f"0x{f['constructor']:08X}", "static_class": f"0x{f['static_class']:08X}",
                    "compiled_in_defer": f"0x{v:08X}", "table_index": i}
            au = pending_auto.pop(name, None)
            if au is not None:
                item.update({"auto_initialize": f"0x{au[1]:08X}", "sizeof": au[2]["size"], "crc": au[2]["crc"]})
            tus[tu].append(item)
            stats["classes"] += 1
        elif kind == "cid":
            name = wstr(img, f["name"])
            if f["defer"] == struct_callee:
                tus[tu].append({"kind": "struct", "name": name, "package": wstr(img, f["package"]),
                                "static_struct": f"0x{f['staticstruct']:08X}", "compiled_in_defer": f"0x{v:08X}",
                                "table_index": i})
                stats["structs"] += 1
            elif f["defer"] == enum_callee:
                tus[tu].append({"kind": "enum", "name": name, "package": wstr(img, f["package"]),
                                "static_enum": f"0x{f['staticstruct']:08X}", "compiled_in_defer": f"0x{v:08X}",
                                "table_index": i})
                stats["enums"] += 1
        elif kind == "srn":
            name = wstr(img, f["name"])
            for item in reversed(tus[tu]):
                if item["kind"] == "struct" and item["name"] == name:
                    item["register_natives"] = f"0x{v:08X}"
                    stats["struct_register_natives"] += 1
                    break
    stats["unpaired_auto_initializers"] = len(pending_auto)

    out_tus = []
    for k in sorted(t for t in tus if t is not None):
        piece = []
        for it in tus[k] + [None]:
            if piece and (it is None or it["package"] != piece[-1]["package"]):
                out_tus.append({"index": len(out_tus), "marker_unit": k,
                                "table_range": [piece[0]["table_index"], piece[-1]["table_index"] + 1],
                                "package": piece[0]["package"], "items": piece})
                piece = []
            if it is not None:
                piece.append(it)
    stats.update(place_package_delegates(img, dimg, allrf, base, out_tus))
    stats.update(place_package_init(img, dimg, allrf, base, out_tus))

    # GlobalVectorConstants of each unit that opens at its marker (the first piece of the
    # marker's unit): the leaf constant initializers from the marker on, read by value.
    opened = set()
    for t in out_tus:
        k = t["marker_unit"]
        if k is None or k in opened:
            continue
        opened.add(k)
        values, i = [], markers[k]
        while i < t["table_range"][0]:
            K = constant_initializer(read(table[i], 20), table[i])
            if K is None:
                break
            values.append(read(K, 16))
            i += 1
        names = name_vector_constants(values)
        if names is None:
            stats["units with an unidentified vector constant"] += 1
        elif names:
            t["vector_constants"] = names
            stats["units with vector constants"] += 1

    head = {
        "schema_version": 1,
        "generated_by": "tools/analysis/unity_order.py",
        "evidence": ("Order of UHT registration objects in the CRT dynamic-initializer table (.CRT$XCU), which "
                     "MSVC emits in definition order per translation unit. Units are delimited by the leaf "
                     "initializer of a header constant most unity files include, and by package changes. "
                     "No .bss address is read."),
        "table": {"rva": f"0x{rd.rva + a:08X}", "entries": len(table), "markers": len(markers),
                  "marker_constant": f"0x{marker_const:08X}", "struct_registrar": f"0x{struct_callee:08X}",
                  "enum_registrar": f"0x{enum_callee:08X}"},
    }
    # One item per line keeps the file small and its diffs readable.
    parts = []
    for t in out_tus:
        meta = json.dumps({k: v for k, v in t.items() if k != "items"}, separators=(",", ":"))[:-1]
        items = ",\n".join("  " + json.dumps(it, separators=(",", ":")) for it in t["items"])
        parts.append(f'{meta},"items":[\n{items}\n ]}}')
    OUT.write_text(json.dumps(head, indent=1)[:-2] + ',\n "units": [\n' + ",\n".join(parts) + "\n ]\n}\n",
                   encoding="utf-8")
    stats["units_with_items"] = len(out_tus)
    print(dict(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
