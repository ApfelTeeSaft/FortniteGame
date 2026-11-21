"""Identify the native C++ implementation each UHT exec thunk calls.

UHT 4.20 generates, for every native UFunction, a thunk

  DECLARE_FUNCTION(exec<Name>)   // static void exec<Name>(UObject* Context, FFrame& Stack, RESULT_DECL)
  {
      P_GET_...;                 // parameters: FFrame::Step / StepExplicitProperty calls
      P_FINISH;                  // Stack.Code += !!Stack.Code
      P_NATIVE_BEGIN;            // empty in shipping
      [if (!P_THIS->CppValidationImplName(...)) { RPC_ValidateFailed(TEXT("...")); return; }]
      [*(RetType*)Z_Param__Result =] P_THIS->CppImplName(...);   // or ThisClass::CppImplName
      P_NATIVE_END;
  }

with CppImplName chosen by the rules in UnrealHeaderTool's ParserHelper.h:
  FUNC_Native|FUNC_Net (not FUNC_NetResponse)  -> <Name>_Implementation, and
                                                 <Name>_Validate when FUNC_NetValidate;
  FUNC_Native|FUNC_BlueprintEvent              -> <Name>_Implementation;
  otherwise                                    -> <Name>.

The thunks (analysis/reflection-natives.json) are disassembled in the decrypted image. P_FINISH
is the first store to Stack.Code ([Stack+0x20], Stack being rdx on entry or a copy of it).
After it, the native call is:
  * a direct call or tail jump whose target no other exec thunk calls (helpers such as the
    FString copy or FMemory are shared by many thunks), or
  * an indirect call through Context's vtable (a virtual native): only its vtable offset is
    recorded, since the vtable's address is not identified here.
A thunk is named only when exactly the calls its flags predict are found (one, or two for
a validated RPC, in that order). The validated RPC's RPC_ValidateFailed literal, when
present, must spell the predicted _Validate name. Thunks shared by several UFunctions
(identical code folded by the linker), thunks without flags (FFunctionParams record not
identified) and natives inlined into the thunk stay unresolved, with the reason counted.
A target already recorded as a generated function in a manifest is a conflict and is not
named. A member native must be called with Context in rcx (P_THIS); otherwise it was
inlined and the call is to one of its callees. A static native has no such check: one
outside its module's code range (the generated code nearest to it belongs to another
package) may be inlined or folded with identical code elsewhere, and is low-confidence.

The UFunction names are confirmed (registration data). The C++ names are high-confidence
inferred: they follow from the flags, except where a Server(ImplName)/Client(ImplName)
specifier overrode them, which the binary does not show.

Usage: python tools/analysis/natives.py   -> analysis/native-implementations.json
Publishes names, RVAs and vtable offsets only.
"""
from __future__ import annotations

import bisect
import json
import re
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

import capstone
from capstone import x86

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "matching"))
from compare import load_decrypted  # noqa: E402
from pe import PEImage  # noqa: E402

OUT = ROOT / "analysis" / "native-implementations.json"
REFLECTION = ROOT / "analysis" / "reflection-natives.json"
CREATOR_SYMBOLS = ROOT / "analysis" / "uht-creator-symbols.json"

FUNC_NET, FUNC_NATIVE, FUNC_NETRESPONSE = 0x40, 0x400, 0x1000
FUNC_STATIC, FUNC_BLUEPRINTEVENT, FUNC_NETVALIDATE = 0x2000, 0x08000000, 0x80000000
LEAF_LIMIT = 64          # a leaf thunk (no .pdata) is P_FINISH plus a tail call

_SUB = {}
for full, subs in {
    "rax": "eax ax al ah", "rbx": "ebx bx bl bh", "rcx": "ecx cx cl ch", "rdx": "edx dx dl dh",
    "rsi": "esi si sil", "rdi": "edi di dil", "rbp": "ebp bp bpl", "rsp": "esp sp spl",
}.items():
    _SUB[full] = full
    for s in subs.split():
        _SUB[s] = full
for i in range(8, 16):
    for suf in ("", "d", "w", "b"):
        _SUB[f"r{i}{suf}"] = f"r{i}"
VOLATILE = {"rax", "rcx", "rdx", "r8", "r9", "r10", "r11"}


def impl_names(name: str, flags: int) -> tuple[str, str | None]:
    """(CppImplName, CppValidationImplName) per UnrealHeaderTool 4.20 ParserHelper.h."""
    impl, validate = name, None
    if flags & FUNC_NATIVE and flags & FUNC_NET:
        if not flags & FUNC_NETRESPONSE:
            impl = f"{name}_Implementation"
            if flags & FUNC_NETVALIDATE:
                validate = f"{name}_Validate"
    if flags & FUNC_NATIVE and flags & FUNC_BLUEPRINTEVENT:
        impl = f"{name}_Implementation"
    return impl, validate


class _State:
    """Aliases of Stack (rdx on entry), Context (rcx) and Context's vtable pointer, in
    registers and in stack slots (keyed by offset from the entry rsp)."""

    def __init__(self):
        self.stack, self.ctx, self.vt = {"rdx"}, {"rcx"}, set()
        self.slots: dict[str, set[int]] = {"stack": set(), "ctx": set(), "vt": set()}
        self.sp = 0
        self.fp: int | None = None      # rbp as an offset from the entry rsp, once set up

    def copy(self) -> "_State":
        c = _State()
        c.stack, c.ctx, c.vt, c.sp, c.fp = set(self.stack), set(self.ctx), set(self.vt), self.sp, self.fp
        c.slots = {k: set(v) for k, v in self.slots.items()}
        return c

    def meet(self, o: "_State") -> "_State":
        c = self.copy()
        c.stack &= o.stack
        c.ctx &= o.ctx
        c.vt &= o.vt
        c.slots = {k: v & o.slots[k] for k, v in self.slots.items()}
        return c

    def sets(self):
        return {"stack": self.stack, "ctx": self.ctx, "vt": self.vt}

    def kill(self, reg: str) -> None:
        for a in (self.stack, self.ctx, self.vt):
            a.discard(reg)


class Thunk:
    """Calls of one exec thunk, in address order, relative to P_FINISH.

    The alias state follows branches: it is saved at each jump to a later address in the
    thunk and restored at that address when the code before it cannot fall through."""

    def __init__(self, md, dimg, rva: int, end: int | None):
        self.rva, self.leaf = rva, end is None
        code = dimg.read(rva, (end - rva) if end else LEAF_LIMIT)
        limit = rva + len(code)
        st = _State()
        saved: dict[int, _State] = {}
        dead = False
        self.finish = None
        self.calls: list[dict] = []      # {at, kind: direct|virtual|indirect, target|offset, post}
        self.literals: list[tuple[int, int]] = []   # (address, target) of every RIP-relative lea

        def save(t: int) -> None:
            saved[t] = st.copy() if t not in saved else saved[t].meet(st)

        def reg(r) -> str | None:
            return _SUB.get(md.reg_name(r))

        def slot(mem) -> int | None:
            if mem.base == x86.X86_REG_RSP and mem.index == 0:
                return st.sp + mem.disp
            if mem.base == x86.X86_REG_RBP and mem.index == 0 and st.fp is not None:
                return st.fp + mem.disp
            return None

        for ins in md.disasm(code, rva):
            m, ops = ins.mnemonic, ins.operands
            if ins.address in saved:
                o = saved.pop(ins.address)
                st = o if dead else st.meet(o)
            elif dead:
                if self.leaf and not any(a > ins.address for a in saved):
                    break
                st = _State()          # unreachable from above and not a known target
                st.ctx, st.stack = set(), set()
            dead = False
            if m == "lea" and ops[1].type == x86.X86_OP_MEM and ops[1].mem.base == x86.X86_REG_RIP:
                self.literals.append((ins.address, ins.address + ins.size + ops[1].mem.disp))
            if (m == "lea" and ops[0].reg == x86.X86_REG_RBP and ops[1].mem.base == x86.X86_REG_RSP
                    and ops[1].mem.index == 0):
                st.fp = st.sp + ops[1].mem.disp
                st.kill("rbp")
                continue
            if (self.finish is None and m == "mov" and ops[0].type == x86.X86_OP_MEM
                    and ops[0].mem.disp == 0x20 and ops[0].mem.index == 0 and ops[0].mem.base
                    and reg(ops[0].mem.base) in st.stack):
                self.finish = ins.address
            post = self.finish is not None
            if m.startswith("j") and ops and ops[0].type == x86.X86_OP_IMM and rva <= ops[0].imm < limit:
                save(ops[0].imm)
                if m == "jmp":
                    dead = True
                continue
            if m in ("call", "jmp"):
                op = ops[0]
                if op.type == x86.X86_OP_IMM:
                    self.calls.append({"at": ins.address, "kind": "direct", "target": op.imm,
                                       "tail": m == "jmp", "post": post, "this": "rcx" in st.ctx})
                elif op.type == x86.X86_OP_MEM and op.mem.base:
                    virt = reg(op.mem.base) in st.vt and op.mem.index == 0 and "rcx" in st.ctx
                    self.calls.append({"at": ins.address, "kind": "virtual" if virt else "indirect",
                                       "offset": op.mem.disp, "tail": m == "jmp", "post": post})
                if m == "jmp":
                    dead = True
                    continue
            if m == "ret":
                dead = True
                continue
            # stack pointer
            if m == "push":
                st.sp -= 8
            elif m == "pop":
                st.sp += 8
                st.kill(reg(ops[0].reg))
                continue
            elif m in ("sub", "add") and ops[0].type == x86.X86_OP_REG and ops[0].reg == x86.X86_REG_RSP                     and ops[1].type == x86.X86_OP_IMM:
                st.sp += -ops[1].imm if m == "sub" else ops[1].imm
                continue
            if m == "mov" and len(ops) == 2 and ops[0].size == 8:
                if ops[0].type == x86.X86_OP_MEM:
                    k = slot(ops[0].mem)
                    if k is not None:
                        src = reg(ops[1].reg) if ops[1].type == x86.X86_OP_REG else None
                        for name, a in st.sets().items():
                            st.slots[name].discard(k)
                            if src in a:
                                st.slots[name].add(k)
                    continue
                if ops[0].type == x86.X86_OP_REG:
                    d = reg(ops[0].reg)
                    if ops[1].type == x86.X86_OP_REG:
                        src = reg(ops[1].reg)
                        for a in st.sets().values():
                            a.discard(d)
                            if src in a:
                                a.add(d)
                        continue
                    if ops[1].type == x86.X86_OP_MEM:
                        mem = ops[1].mem
                        k = slot(mem)
                        st.kill(d)
                        if k is not None:
                            for name, a in st.sets().items():
                                if k in st.slots[name]:
                                    a.add(d)
                        elif mem.index == 0 and mem.disp == 0 and mem.base and reg(mem.base) in st.ctx:
                            st.vt.add(d)
                        continue
            try:
                written = ins.regs_access()[1]
            except capstone.CsError:
                written = []
            for r in written:
                st.kill(reg(r))
            if m == "call":
                for a in st.sets().values():
                    a -= VOLATILE


def wide_at(img, dimg, rva: int) -> str | None:
    try:
        b = dimg.read(rva, 260)
    except ValueError:
        return None
    m = re.match(rb"((?:[A-Za-z0-9_]\x00){1,128})\x00\x00", b)
    return m.group(1).decode("utf-16le") if m else None


def known_functions() -> tuple[set[int], dict[str, str], list[tuple[int, str]]]:
    """Start RVAs of every manifest function; class -> package, and (RVA, package) of every
    generated function with a package, from the UHT manifests."""
    out, cls_pkg, points = set(), {}, []
    for p in sorted((ROOT / "analysis").glob("functions*.json")):
        for e in json.loads(p.read_text(encoding="utf-8")).get("functions", []):
            v = e.get("start_rva") if isinstance(e, dict) else None
            if v is None:
                continue
            r = int(v, 16) if isinstance(v, str) else int(v)
            out.add(r)
            if e.get("package"):
                points.append((r, e["package"]))
                if e.get("class"):
                    cls_pkg.setdefault(e["class"], e["package"])
    points.sort()
    return out, cls_pkg, points


def dump_compact(path: Path, obj: dict) -> None:
    lines = ["{"]
    keys = list(obj)
    for i, k in enumerate(keys):
        v, comma = obj[k], "," if i < len(keys) - 1 else ""
        if isinstance(v, list):
            lines.append(f" {json.dumps(k)}: [")
            lines += [f"  {json.dumps(x, sort_keys=False)}" + ("," if j < len(v) - 1 else "") for j, x in enumerate(v)]
            lines.append(f" ]{comma}")
        else:
            lines.append(f" {json.dumps(k)}: {json.dumps(v, indent=None)}{comma}")
    lines.append("}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    img = PEImage()
    dimg = load_decrypted(img)
    if dimg is None:
        print("needs the validated decrypted image (tools/matching/ingest_dump.py)", file=sys.stderr)
        return 1
    refl = json.loads(REFLECTION.read_text(encoding="utf-8"))
    syms = json.loads(CREATOR_SYMBOLS.read_text(encoding="utf-8"))["symbols"]
    rfs = {rf.begin: rf.end for rf in img.runtime_functions()}
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True

    owners: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for nc in refl["native_classes"]:
        if nc["class"]:
            for f in nc["functions"]:
                owners[int(f["exec_rva"], 16)].append((nc["class"], f["name"]))
    thunks = {r: Thunk(md, dimg, r, rfs.get(r)) for r in sorted(owners)}
    callers = Counter()
    for t in thunks.values():
        for tgt in {c["target"] for c in t.calls if c["kind"] == "direct"}:
            callers[tgt] += 1
    known, cls_pkg, points = known_functions()
    xs = [r for r, _ in points]

    def in_module(cls: str, rva: int) -> bool | None:
        """Whether the generated code nearest below or above rva is the class's package's.
        A monolithic link keeps each module's objects together, so its natives lie in or
        next to its generated code."""
        pkg = cls_pkg.get(cls)
        if pkg is None:
            return None
        i = bisect.bisect_left(xs, rva)
        return pkg in {points[j][1] for j in (i - 1, i) if 0 <= j < len(points)}

    def flags_of(cls: str, name: str) -> int | None:
        rec = syms.get(f"?FuncParams@Z_Construct_UFunction_{cls}_{name}_Statics@@2UFFunctionParams@UE4CodeGen_Private@@B")
        return struct.unpack("<I", dimg.read(int(rec[0], 16) + 0x20, 4))[0] if rec else None

    natives, virtuals, unresolved = [], [], Counter()
    named_at: dict[int, str] = {}
    for r, t in thunks.items():
        if len(owners[r]) > 1:
            unresolved["thunk shared by several UFunctions (linker-folded)"] += 1
            continue
        cls, name = owners[r][0]
        flags = flags_of(cls, name)
        if flags is None:
            unresolved["FFunctionParams record not identified (flags unknown)"] += 1
            continue
        if t.finish is None:
            unresolved["no P_FINISH store found (hand-written CustomThunk?)"] += 1
            continue
        impl, validate = impl_names(name, flags)
        cands = [c for c in t.calls if c["post"] and (
            c["kind"] == "virtual" or (c["kind"] == "direct" and callers[c["target"]] == 1))]
        want = [validate, impl] if validate else [impl]
        if len(cands) != len(want):
            reason = ("no native call after P_FINISH (inlined, or calls a shared function)" if not cands
                      else f"{len(cands)} candidate calls, {len(want)} expected")
            unresolved[reason] += 1
            continue
        if validate:
            lits = [wide_at(img, dimg, tgt) for _, tgt in t.literals]
            if validate not in lits and any(x and x.endswith("_Validate") for x in lits):
                unresolved["RPC_ValidateFailed literal differs from the predicted _Validate name"] += 1
                continue
        conflict = [c for c in cands if c["kind"] == "direct" and c["target"] in known]
        if conflict:
            unresolved["target already recorded as a generated function"] += 1
            continue
        if not flags & FUNC_STATIC and any(c["kind"] == "direct" and not c["this"] for c in cands):
            # P_THIS->Native() passes Context in rcx. A member native called otherwise was
            # inlined into the thunk (the call is to its callee) or is reached through
            # another object.
            unresolved["member call without Context in rcx (inlined native?)"] += 1
            continue
        for c, cpp in zip(cands, want):
            ev = {"class": cls, "ufunction": name, "exec_rva": f"0x{r:08X}", "flags": f"0x{flags:08X}"}
            if c["kind"] == "direct":
                tgt = c["target"]
                if tgt in named_at and named_at[tgt] != f"{cls}::{cpp}":
                    unresolved["target named by two thunks"] += 1
                    continue
                named_at[tgt] = f"{cls}::{cpp}"
                mod = in_module(cls, tgt)
                natives.append({"rva": f"0x{tgt:08X}", "name": f"{cls}::{cpp}", **ev,
                                "call": "tail jump" if c["tail"] else "call",
                                "pdata": tgt in rfs, "module_range": mod,
                                "confidence": "high-confidence inferred" if mod else "low-confidence inferred"})
            else:
                virtuals.append({"name": f"{cls}::{cpp}", "vtable_offset": f"0x{c['offset']:X}", **ev,
                                 "call": "tail jump" if c["tail"] else "call",
                                 "confidence": "high-confidence inferred"})

    natives.sort(key=lambda e: int(e["rva"], 16))
    virtuals.sort(key=lambda e: (e["class"], int(e["vtable_offset"], 16), e["name"]))
    summary = {
        "exec_thunks": len(thunks),
        "leaf_exec_thunks": sum(1 for t in thunks.values() if t.leaf),
        "direct_natives_named": len(natives),
        "direct_natives_without_pdata": sum(1 for e in natives if not e["pdata"]),
        "direct_natives_high_confidence": sum(1 for e in natives if e["confidence"].startswith("high")),
        "direct_natives_outside_module_range": sum(1 for e in natives if e["module_range"] is False),
        "virtual_natives_located": len(virtuals),
        "unresolved": dict(sorted(unresolved.items(), key=lambda kv: -kv[1])),
    }
    dump_compact(OUT, {
        "schema_version": 1,
        "generated_by": "tools/analysis/natives.py",
        "reference_sha256": img.sha256(),
        "evidence": ("Exec thunk of the UFunction (analysis/reflection-natives.json): the call after P_FINISH "
                     "that no other exec thunk makes; C++ name from the UFunction name and its FFunctionParams "
                     "flags by UnrealHeaderTool 4.20's CppImplName rules. Virtual natives: the offset of the "
                     "call through Context's vtable."),
        "summary": summary,
        "natives": natives,
        "virtual_natives": virtuals,
    })
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
