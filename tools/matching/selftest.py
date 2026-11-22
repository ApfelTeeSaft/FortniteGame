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
    assert P.parameter(arr("Names", 0, {"type": "Str", "flags": 0, "func": 0}), names, base) is None  # FString elements: not modelled
    names.structs[0x500] = ("HitResult", 136, 8)                     # user-defined copy (FWeakObjectPtr)
    assert P.parameter(arr("Hits", 0, {"type": "Struct", "flags": 0, "func": base + 0x500}), names, base) is None
    t = P.parameter(rec("Struct", "Hit", const | out | ref, 0x500), names, base)
    assert t["decl"] == "FHitResult const& Hit", t
    names.structs[0x600] = ("HitResult", 136, 4)                     # FStructParams disagree: not used
    assert P.parameter(rec("Struct", "Hit", const | out | ref, 0x600), names, base) is None
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


def main() -> int:
    test_unwind()
    test_local_prediction()
    test_section_relative_runs()
    test_literals()
    test_leave_one_out()
    test_literal_elimination()
    test_exec_thunks()
    test_vtable_store()
    test_uht_parameters()
    test_staticenum_layout()
    if not DEFAULT_REFERENCE.exists():
        print("reference EXE not present: skipping manifest verification")
        return 0
    run(str(HERE / "compare.py"), "--build", "--check", "--quiet")
    run(str(REPO_ROOT / "tools" / "progress" / "generate.py"), "--verify")
    print("selftest: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
