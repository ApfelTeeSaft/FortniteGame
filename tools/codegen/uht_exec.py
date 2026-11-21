"""Virtual slots and exec thunks for Classes.gen.h (used by tools/codegen/uht_classes.py).

Vtable model. analysis/vtables.json names slots of class vtables from virtual natives and
says which class introduces each one. Each class declares its new slots in order: the
introduced ones by name and the gaps as placeholders, `virtual void FNGC_VSlot_0x<offset>()`.
MSVC lays out single-inheritance vtables in declaration order, so a call through a declared
slot compiles to `call [vtbl+offset]` as in the reference. The root class becomes polymorphic
(its destructor is slot 0, as UObjectBase's is) and its opaque member shrinks by the vptr.
Only the slot indexes are modelled, not the functions' bodies or the classes' other virtuals.

Signatures. A slot is declared by name only when its UFunction's full signature is known.
That is the case with no properties, or with a single CPF_ReturnParm property returned in a
register: bool, uint8, int32, float, double, or an object pointer whose class is known.
<Name>_Validate returns bool. Other named slots are placeholders, with the name in a comment.

Exec thunks. For a UFunction whose thunk only calls declared virtual slots, the thunk is
written as UHT 4.20 writes it (DECLARE_FUNCTION in the RPC wrappers). UHT defines it inline
in the class body. Here it is defined out of line in the class's IMPLEMENT_CLASS fragment:
defining only some of a TU's thunks inline changed the order in which MSVC emitted other
functions' static locals (two StaticEnum singletons in CommonUI.3 swapped), breaking layout
predictions that hold with no thunks or out-of-line ones. A body the linker folded for
several UFunctions is defined in each class and has one manifest entry, under the first
class by name:

    P_FINISH;
    P_NATIVE_BEGIN;
    [if (!P_THIS->F_Validate()) { RPC_ValidateFailed(TEXT("F_Validate")); return; }]
    [*(Ret*)Z_Param__Result=]P_THIS->CppImplName();
    P_NATIVE_END;
"""
from __future__ import annotations

import json
import struct
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VTABLES = ROOT / "analysis" / "vtables.json"
NATIVES = ROOT / "analysis" / "native-implementations.json"
CREATOR_SYMBOLS = ROOT / "analysis" / "uht-creator-symbols.json"

FUNC_NETVALIDATE, FUNC_CONST = 0x80000000, 0x40000000
CPF_RETURNPARM, CPF_UOBJECTWRAPPER = 0x400, 0x0004000000000000
# EPropertyClass (UObjectGlobals.h, UE4CodeGen_Private) -> C++ type returned in a register.
PRIMITIVE = {0: "uint8", 3: "int32", 6: "uint32", 10: "float", 11: "double"}
BYTE, BOOL, OBJECT = 0, 12, 14
LEAF_LIMIT = 64


def funcparams(syms: dict, cls: str, ufunction: str) -> int | None:
    rec = syms.get(f"?FuncParams@Z_Construct_UFunction_{cls}_{ufunction}_Statics@@2UFFunctionParams@UE4CodeGen_Private@@B")
    return int(rec[0], 16) if rec else None


def signature(dimg, base: int, syms: dict, ctor_class: dict, cls: str, ufunction: str) -> tuple | None:
    """(return type or None, const, flags) of a UFunction without parameters, or None."""
    rec = funcparams(syms, cls, ufunction)
    if rec is None:
        return None
    fflags, props, nprops = struct.unpack("<I12xQi", dimg.read(rec + 0x20, 0x1C))
    const = bool(fflags & FUNC_CONST)
    if nprops == 0:
        return None, const, fflags
    if nprops != 1:
        return None
    p = struct.unpack("<Q", dimg.read(props - base, 8))[0] - base
    ptype, pflags = struct.unpack("<I20xQ", dimg.read(p, 0x20))
    if not pflags & CPF_RETURNPARM or pflags & CPF_UOBJECTWRAPPER:
        return None
    extra = dimg.read(p + 0x30, 0x10)
    if ptype == BOOL:
        size, native = struct.unpack_from("<IB", extra)
        return ("bool", const, fflags) if (size, native) == (1, 1) else None
    if ptype == BYTE and struct.unpack_from("<Q", extra, 8)[0]:
        return None                    # enum: TEnumAsByte or an enum class, not decided here
    if ptype in PRIMITIVE:
        return PRIMITIVE[ptype], const, fflags
    if ptype == OBJECT:
        c = ctor_class.get(struct.unpack_from("<Q", extra, 8)[0] - base)
        return (f"{c}*", const, fflags) if c else None
    return None


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
    ctor_class = {int(c["constructor"], 16): n for n, c in classes.items() if c.get("constructor")}

    sigs: dict[tuple[str, str], tuple] = {}
    intro = defaultdict(dict)          # introducing class -> slot -> (name, owner, ufunction)
    owner_of = {}
    for e in nat["virtual_natives"]:
        owner_of[(e["class"], e["name"].split("::", 1)[1])] = e
    for s in vtj["slots"]:
        e = owner_of.get((s["ufunction_class"], s["name"]))
        if e is None:
            continue
        intro[s["class"]][s["slot"]] = (s["name"], s["ufunction_class"], e["ufunction"])
        sig = signature(dimg, base, syms, ctor_class, e["class"], e["ufunction"])
        if sig is not None:
            ret, const, fflags = sig
            if s["name"].endswith("_Validate"):
                ret = "bool"
            sigs[(s["ufunction_class"], s["name"])] = (ret, const, fflags)

    def sup(n: str) -> str | None:
        c = classes[n]
        s = c.get("super") if c.get("decoded") else None
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
                    ret, const, _ = sig
                    out.append(f"\tvirtual {ret or 'void'} {name}(){' const' if const else ''};  "
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
        fflags = sigs[(cls, names[0])][2]
        impl = next((nm for nm in names if not nm.endswith("_Validate")), None)
        val = next((nm for nm in names if nm.endswith("_Validate")), None)
        if impl is None or (val is not None) != bool(fflags & FUNC_NETVALIDATE) or len(names) != 1 + (val is not None):
            continue
        ret = sigs[(cls, impl)][0]
        body = ["\tP_FINISH;", "\tP_NATIVE_BEGIN;"]
        if val:
            body += [f"\tif (!P_THIS->{val}())", "\t{", f"\t\tRPC_ValidateFailed(TEXT(\"{val}\"));",
                     "\t\treturn;", "\t}"]
        body.append(f"\t{f'*({ret}*)Z_Param__Result=' if ret else ''}P_THIS->{impl}();")
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
            "stats": dict(stats)}
