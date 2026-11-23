"""Regression tests for the matching tools.

Part 1 needs nothing proprietary: synthetic unwind records and prologues.
Part 2 runs only when the reference EXE and built objects are present. It
re-verifies the manifest (compare.py --check) and the progress image
(generate.py --verify).

Usage: python tools/matching/selftest.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pe import DEFAULT_REFERENCE, REPO_ROOT  # noqa: E402
from unwind import parse_unwind, verify_prologue  # noqa: E402


class FakeImage:
    def __init__(self, blobs: dict[int, bytes]):
        self.blobs = blobs

    def read(self, rva: int, n: int) -> bytes:
        for base, b in self.blobs.items():
            if base <= rva and rva + n <= base + len(b):
                return b[rva - base:rva - base + n]
        raise ValueError("unmapped")

    def u32(self, rva: int) -> int:
        return int.from_bytes(self.read(rva, 4), "little")


def test_unwind() -> None:
    # push rbp; sub rsp,0x20; mov rbp,rdx  (a funclet prologue)
    code = bytes.fromhex("4055 4883ec20 488bea") + b"\xcc" * 8
    # UNWIND_INFO v1, no flags, prolog 6, 2 codes: (6, ALLOC_SMALL 0x20), (2, PUSH_NONVOL rbp)
    ui = bytes([0x01, 0x06, 0x02, 0x00, 0x06, 0x32, 0x02, 0x50])
    img = FakeImage({0x1000: code, 0x2000: ui})
    info = parse_unwind(img, 0x2000)
    assert [c.op for c in info.codes] == [2, 0] and info.codes[0].value == 0x20
    assert verify_prologue(img, 0x1000, info)[0] == "verified"
    # Same record against random bytes must not verify.
    img2 = FakeImage({0x1000: bytes.fromhex("d6a76744 5edd0c47 6662"), 0x2000: ui})
    assert verify_prologue(img2, 0x1000, info)[0] != "verified"
    # Wrong allocation size must be reported as a mismatch.
    img3 = FakeImage({0x1000: bytes.fromhex("4055 4883ec28 488bea"), 0x2000: ui})
    assert verify_prologue(img3, 0x1000, info)[0] == "mismatch"
    # mov [rsp+8],rbx; push rdi; sub rsp,0x20 -- small decimal displacement in capstone output
    code4 = bytes.fromhex("48895c2408 57 4883ec20")
    ui4 = bytes([0x01, 0x0A, 0x04, 0x00, 0x0A, 0x34, 0x06, 0x00, 0x0A, 0x32, 0x06, 0x70])
    img4 = FakeImage({0x1000: code4, 0x2000: ui4})
    assert verify_prologue(img4, 0x1000, parse_unwind(img4, 0x2000))[0] == "verified"
    print("unwind: ok")


def test_literals() -> None:
    from symbols_auto import _string_literal
    wide = "d3ddebug".encode("utf-16le") + b"\0\0" + b"\0" * 6
    assert _string_literal(wide) == "d3ddebug".encode("utf-16le") + b"\0\0"
    assert _string_literal(b"abc\0\0\0\0\0") == b"abc\0"
    assert _string_literal(bytes.fromhex("78ae0a776ff2ba4d")) is None  # GUID bytes are not a literal
    from symbols_auto import literal_hits
    w = "Entry".encode("utf-16le") + b"\0\0"
    hay = b"idx\0" + w + b"\0\0" + w + "Big".encode("utf-16le") + w
    # After a narrow string, after wide NULs, and as a suffix of a wide string: all three count.
    assert literal_hits(w, hay, 0x1000) == [0x1004, 0x1012, 0x1024], literal_hits(w, hay, 0x1000)
    assert literal_hits(b"dx\0", b"\0idx\0\0dx\0", 0) == [6]  # a narrow suffix is not a start
    print("literals: ok")


def run(*args: str) -> None:
    r = subprocess.run([sys.executable, *args], cwd=REPO_ROOT, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode:
        sys.stderr.write(r.stderr)
        raise SystemExit(f"FAILED: {' '.join(args)}")


def test_leave_one_out() -> None:
    from compare import Resolver
    r = Resolver.__new__(Resolver)
    # symbol key -> {observed RVA: {observing manifest entries}}
    r.observations = {"?F@@YAXXZ": {0x1000: {1}}, "?G@@YAXXZ": {0x2000: {1}, 0x3000: {2}}}
    r.entry_names = {1: "A", 2: "B"}
    assert r._observed("?F@@YAXXZ", exclude=1)[0] == set()                # never self-corroborated
    assert r._observed("?F@@YAXXZ", exclude=2)[0] == {0x1000}
    assert r._observed("?G@@YAXXZ", exclude=None)[0] == {0x2000, 0x3000}  # conflict is visible
    assert r._observed("?G@@YAXXZ", exclude=2)[0] == {0x2000}             # leave-one-out drops B
    print("leave-one-out: ok")


def test_literal_elimination() -> None:
    """A literal with N copies resolves only when the other N-1 are used by other functions."""
    from types import SimpleNamespace as NS
    from compare import Resolver
    lit = "Entry".encode("utf-16le") + b"\0\0"
    sym = NS(name="$SG1", section=1, value=0, storage=3)
    obj = NS(symbols=[sym], sections=[NS(name=".rdata", data=lit, chars=0x40000040, relocs=[])],
             symbol=lambda name: sym if name == "$SG1" else None, data_layout=lambda: {})
    r = Resolver.__new__(Resolver)
    r.functions, r.known, r.data_cache, r.data_notes, r._literal_copies, r._groups = {}, {}, {}, {}, {}, {}
    r._unobserved, r._literal_copy_sets, r.entry_addrs = {}, {}, {}
    r.hay_rva, r.hay = 0x1000, b"\0\0" + lit + b"\0\0" + lit + b"\0\0" + lit
    copies = [0x1002, 0x1010, 0x101E]
    r.entry_names, r.observations = {1: "A", 2: "B", 3: "T"}, {}
    r.by_addr = {copies[0]: {"$SGx": {1}}}
    assert r.resolve(obj, "o", "$SG1", exclude=3) == []                  # two copies still free
    r.by_addr[copies[2]] = {"??_C@lit": {2}}
    r.entry_addrs = {1: {copies[0]}, 2: {copies[2]}}
    r._unobserved = {}   # observations changed: a new pass
    got = r.resolve(obj, "o", "$SG1", exclude=3)
    assert [g[0] for g in got] == [copies[1]] and "elimination" in got[0][1], got
    assert r.resolve(obj, "o", "$SG1", exclude=2) == []                  # B's own copy is not evidence for B
    # Unobserved copies are claimed by evidence of other ownership. One inside another object's
    # observed literal range belongs to that object; one a `lea` in the reference targets belongs
    # to that code. Either leaves a single free copy.
    r.by_addr, r.entry_addrs, r._unobserved = {copies[0]: {"$SGx": {1}}}, {1: {copies[0]}}, {}
    r.observations = {("p", "$SG7"): {0x100F: {4}}, ("p", "$SG8"): {0x1018: {4}}}
    r._sg_ranges = None
    got = r.resolve(obj, "o", "$SG1", exclude=3)
    assert [g[0] for g in got] == [copies[2]], got
    assert r._inside_other_object(copies[1], "o") and not r._inside_other_object(copies[1], "p")
    r.observations, r._sg_ranges, r._unobserved = {}, None, {}
    r.img, r._xrefs = NS(), {copies[2] + 2: [0x500]}   # one lea, to TEXT("ntry"): one character in
    r.entry_ranges = {3: (0x400, 0x480)}
    got = r.resolve(obj, "o", "$SG1", exclude=3)
    assert [g[0] for g in got] == [copies[1]], got
    r.data_cache, r._unobserved = {}, {}
    r._xrefs = {copies[2]: [0x440]}   # the entry under test's own use claims nothing
    assert r.resolve(obj, "o", "$SG1", exclude=3) == []
    r.data_cache, r._unobserved = {}, {}
    r._xrefs = {copies[2]: [0x500, 0x600]}   # a pooled copy claims nothing
    assert r.resolve(obj, "o", "$SG1", exclude=3) == []
    # A copy with another object's observed literal between it and this object's own observed
    # literals is not this object's: it claims copies[2], leaving copies[1]. The entry under
    # test's own observations do not place the block.
    r._xrefs, r.data_cache, r._unobserved, r._sg_ranges, r._sg_sorted = {}, {}, {}, None, None
    r.observations = {("o", "$SG2"): {0x100A: {5}}, ("p", "$SG9"): {0x1016: {4}}}
    got = r.resolve(obj, "o", "$SG1", exclude=3)
    assert [g[0] for g in got] == [copies[1]], got
    r.data_cache, r._unobserved, r._sg_ranges, r._sg_sorted = {}, {}, None, None
    r.observations = {("o", "$SG2"): {0x100A: {3}}, ("p", "$SG9"): {0x1016: {4}}}
    assert r.resolve(obj, "o", "$SG1", exclude=3) == []
    print("literal elimination: ok")


def test_exec_thunks() -> None:
    """UHT CppImplName rules and the thunk walker on a hand-assembled validated-RPC thunk."""
    sys.path.insert(0, str(REPO_ROOT / "tools" / "analysis"))
    import capstone
    import natives as N
    net = N.FUNC_NATIVE | N.FUNC_NET
    assert N.impl_names("ServerFoo", net | N.FUNC_NETVALIDATE) == ("ServerFoo_Implementation", "ServerFoo_Validate")
    assert N.impl_names("ClientBar", net) == ("ClientBar_Implementation", None)
    assert N.impl_names("Resp", net | N.FUNC_NETRESPONSE) == ("Resp", None)
    assert N.impl_names("OnHit", N.FUNC_NATIVE | N.FUNC_BLUEPRINTEVENT | 0x800) == ("OnHit_Implementation", None)
    assert N.impl_names("GetX", N.FUNC_NATIVE) == ("GetX", None)
    code = bytes.fromhex(
        "488b4220" "4533c0" "4885c0" "488bd9" "410f95c0" "4c03c0" "4c894220"  # P_FINISH, rbx = Context
        "488b01" "ff9020060000"                                            # Context->vtbl[0x620] (_Validate)
        "84c0" "750d"                                                      # valid: skip the failure path
        "488d0d00000000" "5b" "e900100000"                                 # failure path pops rbx, tail-jumps out
        "488b03" "488bcb" "ffa028060000")                                  # Context->vtbl[0x628] (_Implementation)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    t = N.Thunk(md, FakeImage({0x1000: code}), 0x1000, 0x1000 + len(code))
    assert t.finish == 0x1000 + 20, t.finish
    got = [(c["kind"], c.get("offset", c.get("target"))) for c in t.calls]
    # The failure path's pop must not leak into the branch target: the last call is still virtual.
    assert got == [("virtual", 0x620), ("direct", 0x1000 + 50 + 0x1000), ("virtual", 0x628)], got
    print("exec thunks: ok")


def test_uht_parameters() -> None:
    """UHT 4.20 ExportFunctionThunk / ExportCppDeclaration text for synthetic property records."""
    sys.path.insert(0, str(REPO_ROOT / "tools" / "codegen"))
    import uht_props as P
    base = 0x140000000
    names = P.Names({0x100: "AActor"}, {0x200: {"name": "EMode", "form": P.ENUM_CLASS, "cpp": "EMode"},
                                        0x300: {"name": "ERes", "form": P.ENUM_NAMESPACED, "cpp": "ERes::Type"}},
                    {0x400: ("Vector", 12, 4)})

    def rec(t, name, flags, func=0, inner=()):
        return {"type": t, "name": name, "flags": flags | 0x80, "dim": 1, "func": base + func if func else 0,
                "bool": (1, 1), "inner": [{"type": x} for x in inner]}

    out, const, ref = P.CPF_OUTPARM, P.CPF_CONSTPARM, P.CPF_REFERENCEPARM
    t = P.parameter(rec("Bool", "bEnable", 0), names, base)
    assert (t["decl"], t["line"], t["arg"]) == ("bool bEnable", "P_GET_UBOOL(Z_Param_bEnable);", "Z_Param_bEnable"), t
    t = P.parameter(rec("Int", "Count", out), names, base)
    assert (t["decl"], t["line"], t["arg"]) == ("int32& Count", "P_GET_PROPERTY_REF(UIntProperty,Z_Param_Out_Count);",
                                                "Z_Param_Out_Count"), t
    t = P.parameter(rec("Object", "Target", const, 0x100), names, base)
    assert (t["decl"], t["line"]) == ("const AActor* Target", "P_GET_OBJECT(AActor,Z_Param_Target);"), t
    t = P.parameter(rec("Struct", "Loc", const | out | ref, 0x400), names, base)    # const FVector&
    assert (t["decl"], t["line"]) == ("FVector const& Loc", "P_GET_STRUCT_REF(FVector,Z_Param_Out_Loc);"), t
    t = P.parameter(rec("Enum", "Mode", out, 0x200, ("Byte",)), names, base)
    assert (t["decl"], t["line"], t["arg"]) == ("EMode& Mode", "P_GET_ENUM_REF(EMode,Z_Param_Out_Mode);",
                                                "(EMode&)(Z_Param_Out_Mode)"), t
    t = P.parameter(rec("Byte", "Result", 0, 0x300), names, base)                 # by value: the raw enum
    assert (t["decl"], t["arg"]) == ("ERes::Type Result", "ERes::Type(Z_Param_Result)"), t
    t = P.parameter(rec("Byte", "Result", out | P.CPF_RETURNPARM, 0x300), names, base)
    assert (t["ret"], t["store"]) == ("ERes::Type", "TEnumAsByte<ERes::Type>"), t
    # Declared as TEnumAsByte by the programmer (uht_exec.byte_enum_form): same thunk text.
    t = P.parameter(rec("Byte", "Result", 0, 0x300), names, base, enum_as_byte=True)
    assert (t["decl"], t["arg"]) == ("TEnumAsByte<ERes::Type> Result", "ERes::Type(Z_Param_Result)"), t
    t = P.parameter(rec("Byte", "Result", out | P.CPF_RETURNPARM, 0x300), names, base, enum_as_byte=True)
    assert (t["ret"], t["store"]) == ("TEnumAsByte<ERes::Type>", "TEnumAsByte<ERes::Type>"), t
    assert P.byte_enums([rec("Byte", "A", 0, 0x300), rec("Byte", "B", out | P.CPF_RETURNPARM, 0x300),
                         rec("Byte", "C", 0, 0x200), rec("Byte", "D", out, 0x300)], names, base) == (1, True)
    t = P.parameter(rec("Str", "Text", 0), names, base)                              # by value
    assert (t["decl"], t["line"]) == ("FString Text", "P_GET_PROPERTY(UStrProperty,Z_Param_Text);"), t
    t = P.parameter(rec("Str", "Out", out), names, base)
    assert (t["decl"], t["line"]) == ("FString& Out", "P_GET_PROPERTY_REF(UStrProperty,Z_Param_Out_Out);"), t

    def arr(name, flags, inner):
        r = rec("Array", name, flags)
        r["inner"] = [dict(inner, dim=1)]
        return r
    t = P.parameter(arr("Actors", out, {"type": "Object", "flags": 0, "func": base + 0x100}), names, base)
    assert (t["decl"], t["line"]) == ("TArray<AActor*>& Actors", "P_GET_TARRAY_REF(AActor*,Z_Param_Out_Actors);"), t
    t = P.parameter(arr("Locs", const | out | ref, {"type": "Struct", "flags": 0, "func": base + 0x400}), names, base)
    assert t["decl"] == "TArray<FVector> const& Locs", t
    t = P.parameter(arr("Names", 0, {"type": "Str", "flags": 0, "func": 0}), names, base)
    assert t["line"] == "P_GET_TARRAY(FString,Z_Param_Names);", t           # non-trivial elements (MemoryOps.h)
    names.structs[0x500] = ("HitResult", 136, 8)                     # user-defined copy (FWeakObjectPtr)
    t = P.parameter(arr("Hits", 0, {"type": "Struct", "flags": 0, "func": base + 0x500}), names, base)
    assert t["decl"] == "TArray<FHitResult> Hits", t
    t = P.parameter(rec("Struct", "Hit", const | out | ref, 0x500), names, base)
    assert t["decl"] == "FHitResult const& Hit", t
    names.structs[0x600] = ("HitResult", 136, 4)                     # FStructParams disagree: not used
    assert P.parameter(rec("Struct", "Hit", const | out | ref, 0x600), names, base) is None
    names.structs[0x700] = ("GameplayCueParameters", 184, 8)
    t = P.parameter(rec("Struct", "Parameters", const | out | ref, 0x700), names, base)
    assert (t["decl"], t["line"]) == ("FGameplayCueParameters const& Parameters",
                                      "P_GET_STRUCT_REF(FGameplayCueParameters,Z_Param_Out_Parameters);"), t
    names.structs[0x900] = ("Transform", 48, 16)
    t = P.parameter(rec("Struct", "SpawnTransform", const | out | ref, 0x900), names, base)
    assert (t["decl"], t["line"]) == ("FTransform const& SpawnTransform",
                                      "P_GET_STRUCT_REF(FTransform,Z_Param_Out_SpawnTransform);"), t
    names.structs[0x800] = ("GameplayTagContainer", 32, 8)           # TArray members: no TArray element
    assert P.parameter(arr("Tags", 0, {"type": "Struct", "flags": 0, "func": base + 0x800}), names, base)["decl"] == \
        "TArray<FGameplayTagContainer> Tags"
    names.classes[0xB00] = "UTexture2D"
    t = P.parameter(rec("SoftObject", "Image", 0x0004000000000580, 0xB00), names, base)   # a return value
    assert (t["ret"], t["store"]) == ("TSoftObjectPtr<UTexture2D>", "TSoftObjectPtr<UTexture2D>"), t
    t = P.parameter(rec("SoftObject", "Asset", 0x0004000000000180, 0xB00), names, base)
    assert (t["decl"], t["line"]) == ("TSoftObjectPtr<UTexture2D>& Asset",
                                      "P_GET_SOFTOBJECT_REF(TSoftObjectPtr<UTexture2D>,Z_Param_Out_Asset);"), t
    t = P.parameter(arr("Assets", 0x180, {"type": "SoftObject", "flags": 0, "func": base + 0xB00}), names, base)
    assert t["line"] == "P_GET_TARRAY_REF(TSoftObjectPtr<UTexture2D>,Z_Param_Out_Assets);", t
    names.structs[0xC00] = ("GameplayEventData", 168, 8)             # by value, as the RPCs take it
    t = P.parameter(rec("Struct", "Payload", 0, 0xC00), names, base)
    assert (t["decl"], t["line"]) == ("FGameplayEventData Payload",
                                      "P_GET_STRUCT(FGameplayEventData,Z_Param_Payload);"), t
    names.structs[0xD00] = ("PlayerReservation", 80, 8)             # 4.20's size: the reference's is 64
    assert P.parameter(rec("Struct", "Player", 0, 0xD00), names, base) is None
    names.structs[0xE00] = ("AssetData", 80, 8)
    t = P.parameter(arr("OutAssetData", 0x180, {"type": "Struct", "flags": 0, "func": base + 0xE00}), names, base)
    assert t["line"] == "P_GET_TARRAY_REF(FAssetData,Z_Param_Out_OutAssetData);", t
    names.structs[0xA00] = ("SlateBrush", 120, 8)                    # the reference's, without ResourceHandle
    t = P.parameter(rec("Struct", "Icon", 0x180, 0xA00), names, base)
    assert t["line"] == "P_GET_STRUCT_REF(FSlateBrush,Z_Param_Out_Icon);", t
    names.structs[0xA80] = ("SlateBrush", 136, 8)                    # 4.20's size
    assert P.parameter(rec("Struct", "Icon", 0x180, 0xA80), names, base) is None
    assert "EViewTargetBlendFunction" in P.MODELLED_ENUMS                # defined by the shims, not redeclared
    assert "EFortItemEntryState::Type" in P.MODELLED_ENUMS and P.MODELLED_STRUCTS["FortItemEntry"] == (192, 8)
    assert P.MODELLED_STRUCTS["PointerEvent"] == (104, 8)                # the reference's, without Force
    assert P.MODELLED_STRUCTS["Geometry"] == (56, 4)                     # out-of-line constructor
    assert P.MODELLED_STRUCTS["SlateBrush"] == (120, 8)                  # the reference's, without ResourceHandle
    assert "ESlateBrushDrawType::Type" in P.MODELLED_ENUMS and P.MODELLED_STRUCTS["SlateColor"] == (40, 8)
    t = P.parameter(rec("Text", "Label", 0), names, base)
    assert (t["decl"], t["line"]) == ("FText Label", "P_GET_PROPERTY(UTextProperty,Z_Param_Label);"), t
    t = P.parameter(rec("Text", "Label", const | out | ref), names, base)
    assert (t["decl"], t["line"]) == ("FText const& Label", "P_GET_PROPERTY_REF(UTextProperty,Z_Param_Out_Label);"), t
    wrapper = P.CPF_UOBJECTWRAPPER
    t = P.parameter(rec("Class", "Kind", wrapper, 0x100), names, base)               # TSubclassOf<AActor>
    assert (t["decl"], t["line"]) == ("TSubclassOf<AActor> Kind", "P_GET_OBJECT(UClass,Z_Param_Kind);"), t
    t = P.parameter(rec("Class", "Kind", wrapper | out, 0x100), names, base)         # bPassAsNoPtr
    assert t["line"] == "P_GET_OBJECT_REF_NO_PTR(TSubclassOf<AActor>,Z_Param_Out_Kind);", t
    t = P.parameter(rec("Class", "Kind", wrapper | out | P.CPF_RETURNPARM, 0x100), names, base)
    assert (t["ret"], t["store"]) == ("TSubclassOf<AActor>", "TSubclassOf<AActor>"), t
    assert P.parameter(rec("Interface", "Item", 0), names, base) is None            # not modelled
    assert P.enum_declarations(names) == ["enum class EMode : uint8 {};", "namespace ERes { enum Type {}; }"]
    print("uht parameters: ok")


def test_vtable_store() -> None:
    """InternalConstructor<C> -> (conditional tail jump) C::C -> super ctor, then [this] = vtable."""
    from types import SimpleNamespace as NS
    sys.path.insert(0, str(REPO_ROOT / "tools" / "analysis"))
    import capstone
    import vtables as V
    ic = bytes.fromhex("488b09" "4885c9" "0f85f40f0000" "c3")         # obj = X.GetObj(); if (obj) jmp 0x2000
    ctor = bytes.fromhex("4053" "4883ec20" "488bd9" "e8f20f0000"         # push rbx; ...; call Super::Super
                         "488d05eb2f0000" "488903"                       # lea rax, [0x5000]; mov [rbx], rax
                         "4883c420" "5b" "c3")
    img = FakeImage({0x1000: ic + b"\xcc" * 0x40, 0x2000: ctor + b"\xcc" * 0x40})
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    rdata = NS(contains_rva=lambda r: 0x5000 <= r < 0x6000)
    assert V.constructor_vtable(md, img, {}, rdata, 0x1000) == (0x5000, 0x2000, []), \
        V.constructor_vtable(md, img, {}, rdata, 0x1000)
    print("vtable store: ok")


STATICENUM_PROBE = """struct UEnum;
UEnum* FNGC_Make(int);
UEnum* EZeta_StaticEnum() { static UEnum* Singleton = nullptr; if (!Singleton) Singleton = FNGC_Make(3); return Singleton; }
UEnum* EAlpha_StaticEnum() { static UEnum* Singleton = nullptr; if (!Singleton) Singleton = FNGC_Make(1); return Singleton; }
UEnum* EMid_StaticEnum() { static UEnum* Singleton = nullptr; if (!Singleton) Singleton = FNGC_Make(2); return Singleton; }
static struct FNGCUnityPrologue { FNGCUnityPrologue(); } GNGCUnityPrologue;
struct FDefer { FDefer(UEnum* (*)()); };
static FDefer DZeta(EZeta_StaticEnum), DAlpha(EAlpha_StaticEnum), DMid(EMid_StaticEnum);
"""


def test_staticenum_layout() -> None:
    """Every unity unit defines its external StaticEnum functions before the prologue, in the
    order of its FCompiledInDeferEnum fragments (source order). With MSVC v140 present, also
    check the compiler property this relies on: external functions' static locals are laid out
    in definition order, ahead of the plain .bss."""
    import re
    unity = REPO_ROOT / "FortniteGameCode" / "Source" / "Generated" / "UHT" / "Unity"
    inc = re.compile(r'#include "\.\./Enums/[^/]+/(\w+)\.(staticenum|defer)\.gen\.cpp"')
    units = 0
    for f in sorted(unity.glob("*.gen.cpp")):
        src = f.read_text(encoding="utf-8")
        prologue = src.find('#include "FortniteGameCode/UnityPrologue.h"')
        found = list(inc.finditer(src))
        se = [m for m in found if m.group(2) == "staticenum"]
        assert all(0 <= m.start() < prologue for m in se), f.name
        assert [m.group(1) for m in se] == [m.group(1) for m in found if m.group(2) == "defer"], f.name
        units += bool(se)
    assert units, "no unit defines a StaticEnum"
    for f in (unity.parent / "Enums").rglob("*.staticenum.gen.cpp"):
        assert not re.search(r"static UEnum\* \w+_StaticEnum\(", f.read_text(encoding="utf-8")), f.name
    # A unit's GlobalVectorConstants must follow its StaticEnum functions: no shim header may
    # define them or include TransformRecovered.h (the fragments include the shims); each unit
    # defines its own after the StaticEnum includes and includes FTransform only after both
    # constants its default constructor reads.
    shims = REPO_ROOT / "FortniteGameCode" / "Shims" / "FortniteGameCode"
    transform = '#include "FortniteGameCode/TransformRecovered.h"'
    for h in sorted(shims.glob("*.h")):
        text = h.read_text(encoding="utf-8")
        assert transform not in text and "static const VectorRegister" not in text, h.name
    with_constants = 0
    for f in sorted(unity.glob("*.gen.cpp")):
        src = f.read_text(encoding="utf-8")
        block = src.find("namespace GlobalVectorConstants")
        if block < 0:
            assert transform not in src, f.name
            continue
        with_constants += 1
        prologue = src.find('#include "FortniteGameCode/UnityPrologue.h"')
        assert all(m.start() < block for m in inc.finditer(src) if m.group(2) == "staticenum"), f.name
        assert block < prologue, f.name
        if transform in src:
            t = src.find(transform)
            assert src.find(" FloatOne = ") < t and src.find(" XYZMask = ") < t and -1 not in (
                src.find(" FloatOne = "), src.find(" XYZMask = ")), f.name
    assert with_constants, "no unit defines its vector constants"
    import msvc
    if not msvc.VS140_VCVARS.exists():
        print(f"staticenum layout: ok ({units} units; MSVC v140 not present, compile probe skipped)")
        return
    import tempfile
    from coff import CoffObject
    with tempfile.TemporaryDirectory() as tmp:
        src, obj = Path(tmp) / "probe.cpp", Path(tmp) / "probe.obj"
        src.write_text(STATICENUM_PROBE, encoding="utf-8")
        r = msvc.compile_cpp(src, obj)
        assert obj.exists(), r.stdout[-800:]
        bss = [s for s, _, _ in CoffObject(obj).data_layout().get(".bss", [])]
    got = [re.match(r"\?Singleton@\?1\?\?(\w+)_StaticEnum@@", s).group(1) if s.startswith("?Singleton@") else s
           for s in bss]
    assert got[:4] == ["EZeta", "EAlpha", "EMid", "?GNGCUnityPrologue@@3UFNGCUnityPrologue@@A"], got
    print(f"staticenum layout: ok ({units} units; definition-order probe)")


def test_interface_classes() -> None:
    """Every native interface in Classes.gen.h has UHT's GENERATED_IINTERFACE_BODY typedefs and
    its two leading slots, and only interfaces' exec thunks are defined as I<Name> members."""
    import re
    header = REPO_ROOT / "FortniteGameCode" / "Source" / "Generated" / "UHT" / "Classes.gen.h"
    text = header.read_text(encoding="utf-8")
    found = re.findall(r"^class (I\w+)\n\{\npublic:\n\ttypedef (U\w+) UClassType;\n\ttypedef (I\w+) ThisClass;\n(.*?)\n\};",
                       text, re.M | re.S)
    assert found, "no native interface declared"
    for iname, uname, this, body in found:
        assert iname == this == "I" + uname[1:], iname
        if "virtual" in body:
            assert body.startswith(f"\tvirtual ~{iname}();  // slot 0") and "_getUObject() const;  // slot 1" in body, iname
    print(f"interface classes: ok ({len(found)})")


def test_vector_constants() -> None:
    """Naming a unit's .CRT$XCU constant values in header definition order."""
    sys.path.insert(0, str(REPO_ROOT / "tools" / "analysis"))
    import struct
    import unity_order as U
    one, xyz = struct.pack("<4f", 1, 1, 1, 1), struct.pack("<4I", 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0)
    sign_mask = struct.pack("<4I", *[0x7FFFFFFF] * 4)
    assert U.name_vector_constants([one, xyz, sign_mask]) == ["FloatOne", "XYZMask", "SignMask"]
    # {1,1,1,1} after XYZMask can only be RotationSignificantThreshold (defined last).
    assert U.name_vector_constants([xyz, one]) == ["XYZMask", "RotationSignificantThreshold"]
    assert U.name_vector_constants([xyz, xyz]) is None              # one definition per name
    assert U.name_vector_constants([b"\x01" * 16]) is None           # not a header constant
    print("vector constants: ok")


def test_local_prediction() -> None:
    from compare import local_prediction
    # Layout [a=0][b=8][s=16][c=24][d=32]; a layout gap in the reference between b and s.
    n = [(0, 0x1010, "a"), (8, 0x1010, "b"), (24, 0x2010, "c"), (32, 0x2010, "d")]
    assert local_prediction(16, n) is None                                # sides disagree
    assert local_prediction(16, n[2:]) == (0x2010, ["c", "d"])            # one side only
    agree = [(0, 0x3010, "a"), (24, 0x3010, "c"), (40, 0x9999, "far")]
    assert local_prediction(16, agree) == (0x3010, ["a", "c"])            # far block cannot outvote
    assert local_prediction(16, []) is None
    print("local section-relative: ok")


def test_section_relative_runs() -> None:
    """Gap next to the symbol: the strictly longer run of agreeing neighbours decides."""
    from types import SimpleNamespace as NS
    from compare import Resolver
    names = [f"s{i}" for i in range(7)]
    syms = {n: NS(name=n, section=1, value=8 * i, storage=3) for i, n in enumerate(names)}
    obj = NS(symbols=list(syms.values()), sections=[NS(name=".bss", data=b"", chars=0xC0000080, relocs=[])],
             symbol=lambda n: syms.get(n), data_layout=lambda: {".bss": [(n, 8 * i, 3) for i, n in enumerate(names)]})
    r = Resolver.__new__(Resolver)
    r.functions, r.known, r.data_cache, r.data_notes, r._literal_copies, r._groups = {}, {}, {}, {}, {}, {}
    r._unobserved, r._literal_copy_sets, r.entry_addrs = {}, {}, {}
    r.hay_rva, r.hay, r.by_addr = 0, b"", {}
    r.entry_names = {10 + i: f"F{i}" for i in range(7)}
    # Symbol s<i> is observed only by entry 10+i: s0..s2 in block A (base 0x1000), s4..s5 in
    # block B (base 0x2000), s6 unobserved.
    r.observations = {("o", f"s{i}"): {0x1000 + 8 * i: {10 + i}} for i in range(3)}
    r.observations.update({("o", f"s{i}"): {0x2000 + 8 * i: {10 + i}} for i in (4, 5)})
    got = r.resolve(obj, "o", "s3", exclude=13)
    assert [g[0] for g in got] == [0x1018] and "longer run" in got[0][1], got    # 3 vs 2 neighbours
    r.observations[("o", "s6")] = {0x2030: {16}}                                   # now 3 vs 3
    assert r.resolve(obj, "o", "s3", exclude=13) == []
    got = r.resolve(obj, "o", "s1", exclude=11)                                    # both sides in block A
    assert [g[0] for g in got] == [0x1008] and "(local)" in got[0][1], got
    print("section-relative runs: ok")


def test_match_queue() -> None:
    import match_queue as Q
    assert Q.kind("$SG175471") == "string literal ($SG, per-occurrence copy)"
    assert Q.kind("?StaticClass@AFoo@@SAPEAVUClass@@XZ") == "<Class>::StaticClass"
    assert Q.kind("?EFoo_StaticEnum@@YAPEAVUEnum@@XZ") == "<Enum>_StaticEnum"
    assert Q.kind("?Singleton@?1??EFoo_StaticEnum@@YAPEAVUEnum@@XZ@4PEAV2@EA") == "singleton (.bss)"
    assert Q.kind("??4FSlateBrush@@QEAAAEAU0@AEBU0@@Z") == "constructor / assignment"
    e = {"start_rva": "0x10", "name": "f", "category": "c", "in_denominator": True, "match": "partial",
         "byte_diff": {"differing_bytes": 3, "unresolved_relocations": [{"offset": "0x1", "symbol": "$SG1"}]}}
    assert Q.causes(e) == ["string literal ($SG, per-occurrence copy)", "differing bytes"]
    x = dict(e, start_rva="0x20", match="exact")
    doc, groups = Q.build([e, x, dict(e, start_rva="0x30", in_denominator=False)])
    assert doc["total"] == 1 and doc["groups"][0]["examples"] == ["0x10 f"], doc  # exact and outside skipped
    print("match queue: ok")


def test_accessor_mangling() -> None:
    sys.path.insert(0, str(REPO_ROOT / "tools" / "codegen"))
    from uht_accessors import mangle
    assert mangle("UCommonTextStyle", "GetLineHeightPercentage", "float", [], True, {}) == \
        "?GetLineHeightPercentage@UCommonTextStyle@@QEBAMXZ"
    assert mangle("UCommonUserWidget", "SetConsumePointerInput", None, ["bool"], False, {}) == \
        "?SetConsumePointerInput@UCommonUserWidget@@QEAAX_N@Z"
    assert mangle("UCommonTabListWidget", "GetLinkedSwitcher", "UCommonWidgetSwitcher*", [], True, {}) == \
        "?GetLinkedSwitcher@UCommonTabListWidget@@QEBAPEAVUCommonWidgetSwitcher@@XZ"
    assert mangle("UFoo", "GetOuterFoo", "UFoo*", [], True, {}) == "?GetOuterFoo@UFoo@@QEBAPEAV1@XZ"   # back-reference
    assert mangle("UFoo", "GetState", "EFoo", [], True, {"EFoo": 1}) == "?GetState@UFoo@@QEBA?AW4EFoo@@XZ"
    assert mangle("UFoo", "SetMode", None, ["EMode::Type"], False, {"EMode::Type": 1}) == \
        "?SetMode@UFoo@@QEAAXW4Type@EMode@@@Z"
    assert mangle("UFoo", "GetPoint", "FVector", [], True, {}) == "?GetPoint@UFoo@@QEBA?AUFVector@@XZ"
    assert mangle("UFoo", "SetPoint", None, ["const FVector&"], False, {}) == "?SetPoint@UFoo@@QEAAXAEBUFVector@@@Z"
    assert mangle("UFoo", "GetPad", None, ["FMargin&"], True, {}) == "?GetPad@UFoo@@QEBAXAEAUFMargin@@@Z"
    # Template-ids: class templates (V), arguments with a fresh back-reference table (v140 probes).
    assert mangle("UCommonListView", "GetSelectionModeBP", "TEnumAsByte<ESelectionMode::Type>", [], True,
                  {"ESelectionMode::Type": 1}) == \
        "?GetSelectionModeBP@UCommonListView@@QEBA?AV?$TEnumAsByte@W4Type@ESelectionMode@@@@XZ"
    assert mangle("UFoo", "GetSelf", "TSubclassOf<UFoo>", [], True, {}) == "?GetSelf@UFoo@@QEBA?AV?$TSubclassOf@VUFoo@@@@XZ"
    assert mangle("UFoo", "SetEffect", None, ["TSubclassOf<UGameplayEffect>"], False, {}) == \
        "?SetEffect@UFoo@@QEAAXV?$TSubclassOf@VUGameplayEffect@@@@@Z"
    print("accessor mangling: ok")


def test_accessor_shapes() -> None:
    sys.path.insert(0, str(REPO_ROOT / "tools" / "codegen"))
    from types import SimpleNamespace as I
    from uht_accessors import bit_shape, copy_shape
    ins = lambda *t: [I(mnemonic=x.split(" ", 1)[0], op_str=x.split(" ", 1)[1] if " " in x else "") for x in t]  # noqa: E731
    # FVector by value: 12 bytes from [rcx+0x3f0] to the return slot, which is returned.
    s = copy_shape(ins("mov eax, dword ptr [rcx + 0x3f8]", "movsd xmm0, qword ptr [rcx + 0x3f0]",
                       "movsd qword ptr [rdx], xmm0", "mov dword ptr [rdx + 8], eax", "mov rax, rdx"))
    assert s == {"dst": "rdx", "src": "rcx", "delta": 0x3F0, "size": 12, "ret_rdx": True}, s
    s = copy_shape(ins("movups xmm0, xmmword ptr [rcx + 0x2a0]", "movups xmmword ptr [rdx], xmm0"))
    assert s["size"] == 16 and not s["ret_rdx"]                               # an out parameter
    assert copy_shape(ins("movsd xmm0, qword ptr [rcx + 0x10]", "movsd qword ptr [rdx + 4], xmm0")) is None  # gap at 0
    assert bit_shape(ins("mov eax, dword ptr [rcx + 0x69c]", "shr eax, 2", "and eax, 1")) == \
        {"kind": "get", "offset": 0x69C, "width": 4, "bit": 2, "ternary": False}
    assert bit_shape(ins("mov eax, dword ptr [rcx + 0xa84]", "shr eax, 4", "and al, 1"))["ternary"]  # b ? true : false
    assert bit_shape(ins("and dword ptr [rcx + 0x69c], 0xfffffffe", "movzx eax, dl", "and eax, 1",
                         "or dword ptr [rcx + 0x69c], eax")) == {"kind": "set", "offset": 0x69C, "width": 4, "bit": 0}
    assert bit_shape(ins("and dword ptr [rcx + 0x69c], 0xfffffffd", "movzx eax, dl", "and eax, 1",
                         "or dword ptr [rcx + 0x69c], eax")) is None          # clears bit 1, sets bit 0
    from uht_accessors import cmp_shape, guard_shape
    assert cmp_shape(ins("cmp dword ptr [rcx + 0x2f0], 0xffffffff", "setne al")) == \
        {"offset": 0x2F0, "width": 4, "imm": 0xFFFFFFFF, "cc": "ne"}
    assert cmp_shape(ins("cmp qword ptr [rcx + 0x8], 0", "sete cl")) is None              # not the return register
    # Ptr ? Ptr->X : 0 with the null path straight after the ret: a bare ret (rax is zero) or a
    # zeroing instruction.
    import capstone

    class Img:
        def __init__(self, code: dict):
            self.code = code

        def read(self, rva, n):
            return self.code[rva][:n]
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    body = [I(mnemonic="mov", op_str="rax, qword ptr [rcx + 0x208]"), I(mnemonic="test", op_str="rax, rax"),
            I(mnemonic="je", op_str="0x1014"), I(mnemonic="movzx", op_str="eax, byte ptr [rax + 0x180]")]
    ret = I(mnemonic="ret", op_str="", address=0x1013)
    g = guard_shape(body, ret, Img({0x1014: b"\xc3" + b"\xcc" * 15}), md)
    assert g == {"ptr": 0x208, "offset": 0x180, "wc": "b1", "zero": "rax", "end": 0x1015}, g
    g = guard_shape(body, ret, Img({0x1014: b"\x0f\x57\xc0\xc3" + b"\xcc" * 12}), md)      # xorps xmm0, xmm0; ret
    assert g["zero"] == "xorps xmm0, xmm0" and g["end"] == 0x1018, g
    assert guard_shape(body, I(mnemonic="ret", op_str="", address=0x1000), Img({0x1001: b"\xc3" * 16}), md) is None
    print("accessor shapes: ok")


def test_split_objects() -> None:
    sys.path.insert(0, str(REPO_ROOT / "tools" / "analysis"))
    from unity_order import split_objects

    def cls(name, obj, lit, ti):
        return {"kind": "class", "name": name, "auto_object": f"0x{obj:08X}", "name_literal": f"0x{lit:08X}",
                "table_index": ti}

    def enum(name, lit, ti):
        return {"kind": "enum", "name": name, "name_literal": f"0x{lit:08X}", "table_index": ti}

    # Two runs (0x1000.., 0x2000..) whose literal ranges are disjoint: two objects. The enum
    # between them goes with the object whose literal range holds its literal.
    items = [cls("A", 0x1000, 0x500, 0), cls("B", 0x1028, 0x510, 1), enum("E", 0x900, 2),
             cls("C", 0x2000, 0x900, 3), cls("D", 0x2028, 0x910, 4)]
    out, st = split_objects([{"index": 0, "marker_unit": 0, "package": "/Script/X", "items": items}])
    assert [[i["name"] for i in u["items"]] for u in out] == [["A", "B"], ["E", "C", "D"]], out
    assert st["units cut into objects"] == 1 and [u["index"] for u in out] == [0, 1]
    # Interleaved literals: one object emitted in two batches, kept whole.
    items2 = [cls("A", 0x1000, 0x500, 0), cls("B", 0x1028, 0x920, 1), cls("C", 0x2000, 0x700, 2)]
    out, st = split_objects([{"index": 0, "marker_unit": 0, "package": "/Script/X", "items": items2}])
    assert len(out) == 1 and st["units kept whole: runs of one object (literals interleave)"] == 1
    # An item between the objects whose literal lies in neither range: not cut.
    items3 = [cls("A", 0x1000, 0x500, 0), enum("E", 0x700, 1), cls("C", 0x2000, 0x900, 2)]
    out, st = split_objects([{"index": 0, "marker_unit": 0, "package": "/Script/X", "items": items3}])
    assert len(out) == 1 and st["units kept whole: an item between objects is not placed"] == 1
    print("split objects: ok")


def test_folded_and_code_run() -> None:
    """ICF-folded bodies and InternalConstructor runs resolve only from other entries' observations."""
    from types import SimpleNamespace as NS
    from compare import Resolver
    CODE = 0x60501020            # code | COMDAT | align 16
    r = Resolver.__new__(Resolver)
    r.observations, r.entry_names, r.folded_obs, r._code_groups, r.by_addr = {}, {}, {}, {}, {}

    def obj_of(secs, names):
        fi = {n: (0, len(sc.data), sc) for n, sc in zip(names, secs)}
        return NS(sections=secs, function_index=lambda: fi,
                  functions=lambda: [(NS(name=n), sc) for n, sc in zip(names, secs)])
    leaf = NS(index=1, name=".text$mn", chars=CODE, data=bytes.fromhex("33c0c3"), relocs=[])
    reloc = NS(index=2, name=".text$mn", chars=CODE, data=bytes.fromhex("e900000000"), relocs=[NS(offset=1)])
    o = obj_of([leaf, reloc], ["F", "J"])
    fb = Resolver._folded_body(o, "F")
    assert fb == (".text$mn", bytes.fromhex("33c0c3")) and Resolver._folded_body(o, "J") is None
    r.folded_obs = {fb: {0x5000: {1, 2}}}
    assert r._observed_folded(fb, 3)[0] == {0x5000}
    r.folded_obs = {fb: {0x5000: {3}}}
    assert r._observed_folded(fb, 3)[0] == set()                  # the entry's own observation
    r.folded_obs = {fb: {0x5000: {1}, 0x6000: {2}}}
    assert r._observed_folded(fb, 3)[0] == {0x5000, 0x6000}       # conflicting: resolve() declines

    # A unit's GetPrivateStaticClass sections give the run order A, B, C, D. A, B and D have
    # compiled 20-byte instances (32-byte slots); C's instance is declared only.
    ic = lambda c: f"??$InternalConstructor@V{c}@@@@YAXAEBVFObjectInitializer@@@Z"
    gp = lambda c: f"?GetPrivateStaticClass@{c}@@CAPEAVUClass@@XZ"
    body = bytes.fromhex("488b014885c0740b488bd1488bc8e900000000c3")
    secs, names = [], []
    for k, c in enumerate("ABCD"):
        secs.append(NS(index=k + 1, name=".text$mn", chars=CODE, data=bytes(8), relocs=[NS(offset=1, symbol=ic(c))]))
        names.append(gp(c))
    for k, c in enumerate("ABD"):
        secs.append(NS(index=k + 5, name=".text$mn", chars=CODE, data=body, relocs=[NS(offset=15, symbol="?ctor")]))
        names.append(ic(c))
    o = obj_of(secs, names)
    r._rf_end, r.img = {0x1040: 0x1069}, None      # C's inlined form: 41 bytes, a 48-byte slot

    def run(sym, obs, extra=None):
        r.observations = {ic(c): {a: {n}} for n, (c, a) in enumerate(obs.items(), 1)}
        r.by_addr = {}
        for c, a in obs.items():
            r.by_addr.setdefault(a, {})[ic(c)] = {list(obs).index(c) + 1}
        for a, k in (extra or {}).items():
            r.by_addr.setdefault(a, {}).update(k)
        got = r._internal_constructor_run(o, "u", ic(sym), 9)
        return got[0][0] if got else None
    assert run("B", {"A": 0x1000, "C": 0x1040, "D": 0x1070}) == 0x1020        # both sides agree
    assert run("B", {"A": 0x1000, "C": 0x1050, "D": 0x1080}) is None          # a gap: they disagree
    assert run("D", {"A": 0x1000, "B": 0x1020, "C": 0x1040}) is None          # one side, no image
    assert run("C", {"A": 0x1000, "B": 0x1020, "D": 0x1070}) == 0x1040        # declared only: its extent
    # B folded with E elsewhere: B's slot is empty, so C follows A directly.
    assert run("C", {"A": 0x1000, "B": 0x9000, "D": 0x1050}, {0x9000: {ic("E"): {7}}}) is None
    r._rf_end = {0x1020: 0x1049}
    assert run("C", {"A": 0x1000, "B": 0x9000, "D": 0x1050}, {0x9000: {ic("E"): {7}}}) == 0x1020
    # One side only: the reference must hold B's body at the prediction, with nothing else seen there.
    r.dimg = NS(read=lambda a, n: (body if a == 0x1020 else bytes(n))[:n])
    assert run("B", {"A": 0x1000}) == 0x1020
    assert run("B", {"A": 0x1000}, {0x1020: {"?Other": {5}}}) is None
    r.dimg = NS(read=lambda a, n: bytes(n))
    assert run("B", {"A": 0x1000}) is None
    assert r._internal_constructor_run(o, "u", gp("A"), 9) is None
    print("folded bodies and code runs: ok")


def test_record_bracket() -> None:
    """A creator's static is the one free slot between its record-neighbours' statics."""
    from compare import Resolver
    r = Resolver.__new__(Resolver)
    rf = lambda c: f"?ReturnFunction@?1??{c}@@YAPEAVUFunction@@XZ@4PEAV2@EA"
    A, X, B = "Z_Construct_UFunction_C_A", "Z_Construct_UDelegateFunction_P_X__DelegateSignature", "Z_Construct_UFunction_C_B"
    r._creator_runs = {X: (A, B), A: (None, X), B: (X, None)}
    r._name_index = None

    def setup(obs):
        r.observations = {("o", k): {v: {e}} for k, (v, e) in obs.items()}
        r.by_addr = {}
        for k, (v, e) in obs.items():
            r.by_addr.setdefault(v, {})[("o", k)] = {e}
        r._name_index = None
    setup({rf(A): (0x100, 1), rf(B): (0x118, 2), "?OuterClass@K": (0x108, 3)})
    assert [p for p, _ in r._record_bracket(rf(X), 9)] == [0x110]       # 0x108 is held: 0x110
    setup({rf(A): (0x100, 1), rf(B): (0x120, 2), "?OuterClass@K": (0x108, 3)})
    assert r._record_bracket(rf(X), 9) == []                             # two free slots
    setup({rf(A): (0x100, 1), rf(B): (0x110, 2), rf(X): (0x108, 9)})
    assert [p for p, _ in r._record_bracket(rf(X), 9)] == [0x108]       # its own observation is no claim
    assert r._record_bracket(rf(A), 9) == []                             # an end of the run
    assert r._record_bracket("?OuterClass@?1??Z_Construct_UClass_C@@YAPEAVUClass@@XZ@4PEAV2@EA", 9) == []
    print("record-bracketed slots: ok")


def test_rigid_successor() -> None:
    from compare import rigid_successor
    oc = lambda c: f"?OuterClass@?1??Z_Construct_UClass_{c}@@YAPEAVUClass@@XZ@4PEAV2@EA"
    psc = lambda c: f"?PrivateStaticClass@?1??GetPrivateStaticClass@{c}@@CAPEAVUClass@@XZ@4PEAV3@EA"
    rf = lambda f: f"?ReturnFunction@?1??{f}@@YAPEAVUFunction@@XZ@4PEAV2@EA"
    assert rigid_successor(oc("AActor"), psc("AActor"))
    assert not rigid_successor(oc("AActor"), psc("AActorB")) and not rigid_successor(psc("AActor"), oc("AActor"))
    assert rigid_successor(rf("Z_Construct_UFunction_AActor_Tick"), oc("AActor"))
    assert rigid_successor(rf("Z_Construct_UDelegateFunction_AActor_OnX__DelegateSignature"), oc("AActor"))
    assert not rigid_successor(rf("Z_Construct_UFunction_APawn_Tick"), oc("AActor"))
    assert not rigid_successor(rf("Z_Construct_UFunction_AActor_Tick"), rf("Z_Construct_UFunction_AActor_Walk"))
    print("rigid successors: ok")


def test_slot_elimination() -> None:
    from compare import Resolver
    r = Resolver.__new__(Resolver)
    block = {"unit": "U.1", "slot": 8, "symbols": ["A", "B", "C", "D"]}
    r.blocks = {m: block for m in block["symbols"]}

    def setup(obs: dict, other: dict | None = None):
        r.observations = {("obj", k): {v: {i + 10}} for i, (k, v) in enumerate(obs.items())}
        r.by_addr = {v: {("obj", k): {i + 10}} for i, (k, v) in enumerate(obs.items())}
        for k, v in (other or {}).items():
            r.observations[("obj", k)] = {v: {99}}
            r.by_addr.setdefault(v, {})[("obj", k)] = {99}
        r._name_index = None
    setup({"A": 0x100, "B": 0x108, "D": 0x118})                       # C fills the gap
    assert [p for p, _ in r._slot_elimination("C", None)] == [0x110]
    setup({"B": 0x108, "C": 0x110, "D": 0x118}, {"X": 0x120})            # A: 0x120 is someone else's
    assert [p for p, _ in r._slot_elimination("A", None)] == [0x100]
    setup({"B": 0x108, "C": 0x110, "D": 0x118})                           # either end: declined
    assert r._slot_elimination("A", None) == []
    setup({"A": 0x100, "B": 0x108, "D": 0x140})                           # not one block: declined
    assert r._slot_elimination("C", None) == []
    # Both ends free, but just below the block another unit's .bss closes with a class's
    # PrivateStaticClass: the block starts directly above it, so A takes the lower end.
    psc = "?PrivateStaticClass@?1??GetPrivateStaticClass@AOther@@CAPEAVUClass@@XZ@4PEAV3@EA"
    other_obj = "Source/Generated/UHT/Unity/V.1.gen.obj"
    r.symbol_objects = {"?GetPrivateStaticClass@AOther@@CAPEAVUClass@@XZ": other_obj}
    r._last_bss = {other_obj: psc}
    setup({"B": 0x108, "C": 0x110, "D": 0x118}, {psc: 0xF8})
    assert [p for p, _ in r._slot_elimination("A", None)] == [0x100]
    r._last_bss = {other_obj: "?Something@@3PEAXEA"}                    # not its object's last static
    assert r._slot_elimination("A", None) == []
    r._last_bss = {"Source/Generated/UHT/Unity/U.1.s2.gen.obj": psc}     # the block's own unit
    r.symbol_objects = {"?GetPrivateStaticClass@AOther@@CAPEAVUClass@@XZ": "Source/Generated/UHT/Unity/U.1.s2.gen.obj"}
    assert r._slot_elimination("A", None) == []
    print("slot elimination: ok")


def main() -> int:
    test_slot_elimination()
    test_rigid_successor()
    test_record_bracket()
    test_split_objects()
    test_accessor_mangling()
    test_accessor_shapes()
    test_match_queue()
    test_unwind()
    test_local_prediction()
    test_section_relative_runs()
    test_literals()
    test_leave_one_out()
    test_literal_elimination()
    test_folded_and_code_run()
    test_exec_thunks()
    test_vtable_store()
    test_uht_parameters()
    test_staticenum_layout()
    test_vector_constants()
    test_interface_classes()
    if not DEFAULT_REFERENCE.exists():
        print("reference EXE not present: skipping manifest verification")
        return 0
    run(str(HERE / "compare.py"), "--build", "--check", "--quiet")
    run(str(REPO_ROOT / "tools" / "progress" / "generate.py"), "--verify")
    print("selftest: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
