"""Virtual slots and exec thunks for Classes.gen.h (used by tools/codegen/uht_classes.py).

Vtable model. analysis/vtables.json names slots of class vtables from virtual natives and
says which class introduces each one. Each class declares its new slots in order: the
introduced ones by name and the gaps as placeholders, `virtual void FNGC_VSlot_0x<offset>()`.
MSVC lays out single-inheritance vtables in declaration order, so a call through a declared
slot compiles to `call [vtbl+offset]` as in the reference. The root class becomes polymorphic
(its destructor is slot 0, as UObjectBase's is) and its opaque member shrinks by the vptr.
Only the slot indexes are modelled, not the functions' bodies or the classes' other virtuals.

Signatures. A slot is declared by name only when its UFunction's full signature is known:
every parameter and the return value of a type tools/codegen/uht_props.py supports (bool,
integers, floating point, uint8 without an enum, FName, pointers to reflected classes).
<Name>_Validate returns bool. Other named slots are placeholders, with the name in a comment.

Exec thunks. For a UFunction whose thunk only calls declared virtual slots, the thunk is
written as UHT 4.20 writes it (DECLARE_FUNCTION in the RPC wrappers). UHT defines it inline
in the class body. Here it is defined out of line in the class's IMPLEMENT_CLASS fragment:
defining only some of a TU's thunks inline changed the order in which MSVC emitted other
functions' static locals (two StaticEnum singletons in CommonUI.3 swapped), breaking layout
predictions that hold with no thunks or out-of-line ones. A body the linker folded for
several UFunctions is defined in each class and has one manifest entry, under the first
class by name:

    P_GET_<macro>(<type>,Z_Param_<Name>);   (per parameter, in declaration order)
    P_FINISH;
    P_NATIVE_BEGIN;
    [if (!P_THIS->F_Validate(<args>)) { RPC_ValidateFailed(TEXT("F_Validate")); return; }]
    [*(Ret*)Z_Param__Result=]P_THIS->CppImplName(<args>);
    P_NATIVE_END;
"""
from __future__ import annotations

import json
import struct
import sys
from collections import defaultdict
from pathlib import Path

import capstone

import uht_props

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
import natives  # noqa: E402  (tools/analysis/natives.py: the exec thunk walker)

_MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
_MD.detail = True

ROOT = Path(__file__).resolve().parents[2]
VTABLES = ROOT / "analysis" / "vtables.json"
NATIVES = ROOT / "analysis" / "native-implementations.json"
CREATOR_SYMBOLS = ROOT / "analysis" / "uht-creator-symbols.json"
ENUM_MANIFEST = ROOT / "analysis" / "functions-uht-enums.json"
ENUM_SYMBOLS = ROOT / "analysis" / "uht-enum-symbols.json"

FUNC_NET, FUNC_NETVALIDATE, FUNC_CONST = 0x40, 0x80000000, 0x40000000
CONSTRUCT_USCRIPTSTRUCT = 0x0138FA20    # UE4CodeGen_Private::ConstructUScriptStruct (see docs/STATUS.md)
LEAF_LIMIT = 64


def funcparams(syms: dict, cls: str, ufunction: str) -> int | None:
    rec = syms.get(f"?FuncParams@Z_Construct_UFunction_{cls}_{ufunction}_Statics@@2UFFunctionParams@UE4CodeGen_Private@@B")
    return int(rec[0], 16) if rec else None


def strings_by_reference(dimg, base: int, rec: int, exec_rva: int, rfs: dict) -> bool | None:
    """Whether the UFunction's flagless FString parameters are 'const FString&' (True) or
    by value (False); None if the reference does not decide it.

    RPC parameters must be const references (HeaderParser). Otherwise the reference thunk
    shows it: a by-value FString is copy-constructed before the native call, TArray's
    CopyToEmpty calling ResizeForCopy and memcpy, while a const reference passes the local's
    address. So the direct calls between P_FINISH and the first virtual native call number
    two per by-value string, none for references."""
    n = uht_props.plain_strings(dimg, base, rec)
    if n == 0:
        return False
    fflags = struct.unpack("<I", dimg.read(rec + 0x20, 4))[0]
    if fflags & FUNC_NET:
        return True
    t = natives.Thunk(_MD, dimg, exec_rva, rfs[exec_rva].end if exec_rva in rfs else None)
    native = next((c["at"] for c in t.calls if c["post"] and c["kind"] == "virtual"), None)
    if native is None:
        return None
    copies = sum(1 for c in t.calls if c["post"] and c["kind"] == "direct" and c["at"] < native)
    return True if copies == 0 else False if copies == 2 * n else None


def signature(dimg, base: int, syms: dict, names, cls: str, ufunction: str, exec_rva: int, rfs: dict) -> dict | None:
    """The UFunction's parameters (uht_props.function_signature) and constness, or None."""
    rec = funcparams(syms, cls, ufunction)
    if rec is None:
        return None
    by_ref = strings_by_reference(dimg, base, rec, exec_rva, rfs)
    if by_ref is None:
        return None
    sig = uht_props.function_signature(dimg, base, rec, names, by_ref)
    if sig is not None:
        sig["const"] = bool(sig["flags"] & FUNC_CONST)
    return sig


def enum_info(dimg, base: int) -> dict[int, dict]:
    """Z_Construct_UEnum_* RVA -> UEnum name, UEnum::ECppForm and C++ type, read from the enum's
    FEnumParams (NameUTF8 +0x10, CppForm +0x28, CppTypeUTF8 +0x30)."""
    ctors = json.loads(ENUM_MANIFEST.read_text(encoding="utf-8"))["functions"]
    syms = json.loads(ENUM_SYMBOLS.read_text(encoding="utf-8"))["symbols"]
    out = {}
    for e in ctors:
        rec = syms.get(f"?EnumParams@?4??{e['name']}@@YAPEAVUEnum@@XZ@4UFEnumParams@UE4CodeGen_Private@@B")
        if rec is None:
            continue
        r = int(rec[0], 16)
        name, form, cpp = struct.unpack("<16xQ16xB7xQ", dimg.read(r, 0x38))
        out[int(e["start_rva"], 16)] = {"name": _cstr(dimg, base, name), "form": form, "cpp": _cstr(dimg, base, cpp)}
    return out


class StructInfo(dict):
    """Z_Construct_UScriptStruct_* RVA -> (name, SizeOf, AlignOf) from the FStructParams its
    `lea rdx` passes to ConstructUScriptStruct (NameUTF8 +0x18, SizeOf +0x28, AlignOf +0x30)."""

    def __init__(self, dimg, base: int):
        super().__init__()
        self.dimg, self.base = dimg, base

    def __missing__(self, rva: int):
        val = None
        code = self.dimg.read(rva, 0x40)
        i = code.find(b"\x48\x8d\x15")                # lea rdx, [rip+FStructParams]
        if i >= 0 and code.find(b"\xe8", i) > i:
            rec = rva + i + 7 + struct.unpack_from("<i", code, i + 3)[0]
            call = code.find(b"\xe8", i)
            target = rva + call + 5 + struct.unpack_from("<i", code, call + 1)[0]
            if target == CONSTRUCT_USCRIPTSTRUCT:
                name, size, align = struct.unpack("<24xQ8xQQ", self.dimg.read(rec, 0x38))
                val = (_cstr(self.dimg, self.base, name), size, align)
        self[rva] = val
        return val

    def get(self, rva, default=None):
        v = self[rva]
        return default if v is None else v


def _cstr(dimg, base: int, va: int) -> str:
    return dimg.read(va - base, 256).split(b"\0")[0].decode()


def leaf_end(md, dimg, rva: int) -> int | None:
    """End of a leaf thunk: just after its first unconditional exit."""
    for ins in md.disasm(dimg.read(rva, LEAF_LIMIT), rva):
        if ins.mnemonic in ("jmp", "ret"):
            return ins.address + ins.size
    return None


def build(dimg, base: int, classes: dict, out_order: list[str], rfs: dict, md) -> dict:
    """Slot declarations, inline thunk definitions and manifest entries for Classes.gen.h."""
    vtj = json.loads(VTABLES.read_text(encoding="utf-8"))
    nat = json.loads(NATIVES.read_text(encoding="utf-8"))
    syms = json.loads(CREATOR_SYMBOLS.read_text(encoding="utf-8"))["symbols"]
    # Object properties' ClassFunc is Z_Construct_UClass_<C>_NoRegister, the same code as (folded
    # with) <C>::StaticClass; class constructors name the class too.
    ctor_class = {int(c["constructor"], 16): n for n, c in classes.items() if c.get("constructor")}
    ctor_class.update({int(c["static_class"], 16): n for n, c in classes.items() if c.get("static_class")})
    typenames = uht_props.Names(ctor_class, enum_info(dimg, base), StructInfo(dimg, base))

    sigs: dict[tuple[str, str], dict] = {}
    intro = defaultdict(dict)          # introducing class -> slot -> (name, owner, ufunction)
    owner_of = {}
    for e in nat["virtual_natives"]:
        owner_of[(e["class"], e["name"].split("::", 1)[1])] = e
    for s in vtj["slots"]:
        e = owner_of.get((s["ufunction_class"], s["name"]))
        if e is None:
            continue
        intro[s["class"]][s["slot"]] = (s["name"], s["ufunction_class"], e["ufunction"])
        sig = signature(dimg, base, syms, typenames, e["class"], e["ufunction"], int(e["exec_rva"], 16), rfs)
        if sig is not None:
            if s["name"].endswith("_Validate"):
                sig = dict(sig, ret="bool")
            sigs[(s["ufunction_class"], s["name"])] = sig

    def sup(n: str) -> str | None:
        c = classes[n]
        s = c.get("super") if c.get("decoded") or c.get("intrinsic") else None
        return s if s and s != n and s in classes else None

    children = defaultdict(list)
    for n in out_order:
        if sup(n):
            children[sup(n)].append(n)

    # Which subtrees declare slots at all; their root becomes polymorphic.
    needs = {}
    for n in reversed(out_order):
        needs[n] = bool(intro.get(n)) or any(needs[k] for k in children[n])
    lower = {r["class"]: r["slots_lower"] for r in vtj["classes"]}

    declared: dict[str, int] = {}
    decls: dict[str, list[str]] = {}
    visible: dict[str, dict[str, int]] = {}    # class -> name -> slot, through its ancestors
    named_ok: set[tuple[str, str]] = set()      # (owner, CppImplName) declared by name
    roots_with_vptr = set()
    stats = defaultdict(int)
    for n in out_order:
        p = sup(n)
        have = declared.get(p, 0) if p else 0
        names = dict(visible.get(p, {})) if p else {}
        mine = intro.get(n, {})
        if not needs[n]:
            declared[n], visible[n], decls[n] = have, names, []
            continue
        top = max(mine) + 1 if mine else have
        if p is None:
            roots_with_vptr.add(n)
            top = max(top, lower.get(n) or 1)
        out = []
        for i in range(have, top):
            if p is None and i == 0:
                out.append(f"\tvirtual ~{n}();  // slot 0 (+0x0): the destructor, as UObjectBase's")
                continue
            if i in mine:
                name, owner, uf = mine[i]
                sig = sigs.get((owner, name))
                if sig is not None and name not in names:
                    decl = ", ".join(d for d, _, _ in sig["params"])
                    out.append(f"\tvirtual {sig['ret'] or 'void'} {name}({decl}){' const' if sig['const'] else ''};  "
                               f"// slot {i} (+0x{8 * i:X}), UFunction {owner}::{uf}")
                    names[name] = i
                    named_ok.add((owner, name))
                    stats["slots declared by name"] += 1
                    continue
                why = "signature not recovered" if sig is None else "name already declared above"
                out.append(f"\tvirtual void FNGC_VSlot_0x{8 * i:X}();  // slot {i}: {owner}::{name} ({why})")
                stats["named slots declared as placeholders"] += 1
                continue
            out.append(f"\tvirtual void FNGC_VSlot_0x{8 * i:X}();")
            stats["placeholder slots"] += 1
        declared[n], visible[n], decls[n] = top, names, out

    # Exec thunks whose every native call is a slot declared by name.
    by_owner = defaultdict(list)
    for e in nat["virtual_natives"]:
        by_owner[(e["exec_rva"], e["class"], e["ufunction"])].append(e)
    direct_execs = {e["exec_rva"] for e in nat["natives"]}
    thunks: dict[tuple[str, str], str] = {}
    entries, entry_at = [], {}
    for (exec_rva, cls, uf), es in sorted(by_owner.items()):
        if exec_rva in direct_execs:
            continue                   # also calls a native directly: its address is unresolved
        names = [e["name"].split("::", 1)[1] for e in es]
        if not all((cls, nm) in named_ok and names.count(nm) == 1 for nm in names):
            continue
        fflags = sigs[(cls, names[0])]["flags"]
        impl = next((nm for nm in names if not nm.endswith("_Validate")), None)
        val = next((nm for nm in names if nm.endswith("_Validate")), None)
        if impl is None or (val is not None) != bool(fflags & FUNC_NETVALIDATE) or len(names) != 1 + (val is not None):
            continue
        sig = sigs[(cls, impl)]
        ret, args = sig["store"], ",".join(a for _, _, a in sig["params"])
        body = [f"\t{line}" for _, line, _ in sig["params"]] + ["\tP_FINISH;", "\tP_NATIVE_BEGIN;"]
        if val:
            body += [f"\tif (!P_THIS->{val}({args}))", "\t{", f"\t\tRPC_ValidateFailed(TEXT(\"{val}\"));",
                     "\t\treturn;", "\t}"]
        body.append(f"\t{f'*({ret}*)Z_Param__Result=' if ret else ''}P_THIS->{impl}({args});")
        stats["exec thunks with parameters"] += bool(sig["params"])
        body.append("\tP_NATIVE_END;")
        r = int(exec_rva, 16)
        end = rfs[r].end if r in rfs else leaf_end(md, dimg, r)
        if end is None:
            continue
        thunks[(cls, uf)] = (f"// Original FortniteClient-Win64-Shipping.exe: RVA 0x{r:08X} (end 0x{end:08X})"
                             f"{'' if r in rfs else ', leaf (no .pdata)'}\n"
                             f"// Recovery: UHT 4.20 DECLARE_FUNCTION(exec{uf}) | Matching: see analysis/functions-uht-exec.json\n"
                             f"void {cls}::exec{uf}(UObject* Context, FFrame& Stack, void* const Z_Param__Result)\n"
                             "{\n" + "\n".join(body) + "\n}\n")
        stats["exec thunks defined"] += 1
        if exec_rva in entry_at:
            # The same body for another UFunction (linker-folded): one manifest entry per address.
            entry_at[exec_rva]["thunk_shared_by"] = entry_at[exec_rva].get("thunk_shared_by", 1) + 1
            continue
        entry_at[exec_rva] = {"start_rva": f"0x{r:08X}", "end_rva": f"0x{end:08X}", "name": f"{cls}::exec{uf}",
                              "class": cls}
        entries.append(entry_at[exec_rva])
        stats["exec thunk addresses"] += 1
        stats["exec thunk addresses, leaf"] += r not in rfs
    return {"decls": decls, "thunks": thunks, "roots_with_vptr": roots_with_vptr, "entries": entries,
            "enums": uht_props.enum_declarations(typenames),
            "stats": dict(stats)}
