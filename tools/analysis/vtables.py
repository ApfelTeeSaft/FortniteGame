"""Recover the primary vtable of every reflected class and name its UFunction slots.

Locating vtables (the build has no RTTI, /GR-). GetPrivateStaticClass passes
InternalConstructor<C>, which runs C::C(const FObjectInitializer&) on X.GetObj(): either a
(conditional) tail jump to the constructor or the constructor inlined. A constructor
calls its superclass's constructor and then stores C's vtable at [this]. The last store
of a .rdata address to [this+0] on that path is C's primary vtable. Without hot reload,
InternalVTableHelperCtorCaller<C> returns nullptr for every class and gives no vtable.

Slot counts. Vtables are packed in .rdata, so a vtable's run of code pointers may continue
into the next one. Every UObject-derived vtable repeats most of UObject's slots 1..70 (the
destructor in slot 0 differs). Positions where at least half of those slots match are taken
as vtable starts, and a run ends at the next start. A class has no more slots than its own
run or any descendant's run: the "upper" count. A run that ends before a non-UObject
vtable still overruns, so the count used is a lower bound from evidence:
  * the superclass's count;
  * a virtual native of the class (analysis/native-implementations.json) at slot i: i + 1;
  * a descendant whose vtable differs inheriting the class's entry at slot i (below the
    upper count) unchanged: i + 1. Functions that occur at more than one slot index (stubs
    folded by /OPT:ICF) are not evidence.
Interface UFunctions (CLASS_Interface) call through the I-class's own vtable; their slots are
listed separately and not part of the UObject model.
A class whose lower count exceeds its upper count is reported, not adjusted.

Slot names. A virtual native names slot i of its class C, and so the slot in every
descendant. The slot is introduced by the topmost ancestor whose lower count exceeds i.
Each descendant's entry at slot i is that function's implementation, named after the
topmost class on the path from C whose entry is that pointer (<Class>::<CppImplName>). An
address that receives more than one name, or occurs at several slot indexes, is reported as
folded and not named; so is one that natives.py names differently with high confidence.

Usage: python tools/analysis/vtables.py   (after tools/analysis/natives.py)
       -> analysis/vtables.json. Publishes names, RVAs and slot indexes only.
"""
from __future__ import annotations

import json
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

import capstone
from capstone import x86

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "matching"))
sys.path.insert(0, str(ROOT / "tools" / "codegen"))
from compare import load_decrypted  # noqa: E402
from pe import PEImage  # noqa: E402
from uht_classes import decode_gpsc  # noqa: E402

OUT = ROOT / "analysis" / "vtables.json"
UNITY_ORDER = ROOT / "analysis" / "unity-order.json"
NATIVES = ROOT / "analysis" / "native-implementations.json"
UOBJECT_PREFIX = 71            # UObject's slot count; checked against its children below
START_MATCHES = 35             # of UObject's slots 1..70, for a UObject-derived vtable start
SCAN_LIMIT = 0x600
CLASS_INTERFACE = 0x00004000

_SUB = {}
for _full, _subs in {"rax": "eax ax al", "rbx": "ebx bx bl", "rcx": "ecx cx cl", "rdx": "edx dx dl",
                     "rsi": "esi si sil", "rdi": "edi di dil", "rbp": "ebp bp bpl"}.items():
    _SUB[_full] = _full
    for _s in _subs.split():
        _SUB[_s] = _full
for _i in range(8, 16):
    for _suf in ("", "d", "w", "b"):
        _SUB[f"r{_i}{_suf}"] = f"r{_i}"
VOLATILE = ("rax", "rcx", "rdx", "r8", "r9", "r10", "r11")


def class_hierarchy(img, dimg, allrf) -> dict[str, dict]:
    """Every class of the initializer table with its decoded GetPrivateStaticClass and superclass."""
    order = json.loads(UNITY_ORDER.read_text(encoding="utf-8"))
    classes = {it["name"]: dict(it) for u in order["units"] for it in u["items"] if it["kind"] == "class"}
    by_static_class = {int(c["static_class"], 16): n for n, c in classes.items()}
    for c in classes.values():
        sc = int(c["static_class"], 16)
        b = dimg.read(sc, 5)
        g = sc + 5 + struct.unpack_from("<i", b, 1)[0] if b[0] == 0xE9 else None
        c["decoded"] = decode_gpsc(dimg.read(g, 0x200), g) if g in allrf else None
    bodies = Counter(c["decoded"]["body"] for c in classes.values() if c["decoded"])
    body = bodies.most_common(1)[0][0]
    for c in classes.values():
        f = c["decoded"]
        if f and f["body"] != body:
            c["decoded"] = f = None
        c["super"] = by_static_class.get(f["super"]) if f else None
    return classes


def constructor_vtable(md, dimg, allrf, rdata, ctor: int) -> tuple[int | None, int | None, list]:
    """(vtable, constructor) reached from InternalConstructor<C>, and secondary vtable stores."""

    def scan(rva: int, this: set[str], deref_obj: bool):
        end = allrf[rva].end if rva in allrf else rva + 0x40
        code = dimg.read(rva, min(end - rva, SCAN_LIMIT))
        vals: dict[str, int] = {}
        stores, tail = [], None
        for ins in md.disasm(code, rva):
            m, ops = ins.mnemonic, ins.operands
            if m == "ret":
                break
            if m.startswith("j") and ops[0].type == x86.X86_OP_IMM and not rva <= ops[0].imm < rva + len(code):
                if tail is None:
                    tail = (ops[0].imm, "rcx" in this)
                if m == "jmp":
                    break
                continue
            if m == "lea" and ops[0].type == x86.X86_OP_REG and ops[1].mem.base == x86.X86_REG_RIP:
                d = _SUB.get(ins.reg_name(ops[0].reg))
                t = ins.address + ins.size + ops[1].mem.disp
                this.discard(d)
                if rdata.contains_rva(t):
                    vals[d] = t
                else:
                    vals.pop(d, None)
                continue
            if m == "mov" and len(ops) == 2:
                if (ops[0].type == x86.X86_OP_MEM and ops[1].type == x86.X86_OP_REG and ops[0].size == 8
                        and ops[0].mem.index == 0 and ops[0].mem.base
                        and _SUB.get(ins.reg_name(ops[0].mem.base)) in this):
                    s = _SUB.get(ins.reg_name(ops[1].reg))
                    if s in vals:
                        stores.append((ops[0].mem.disp, vals[s]))
                    continue
                if ops[0].type == x86.X86_OP_REG and ops[0].size == 8:
                    d = _SUB.get(ins.reg_name(ops[0].reg))
                    if ops[1].type == x86.X86_OP_REG:
                        s = _SUB.get(ins.reg_name(ops[1].reg))
                        this.discard(d)
                        vals.pop(d, None)
                        if s in this:
                            this.add(d)
                        if s in vals:
                            vals[d] = vals[s]
                        continue
                    if (deref_obj and not this and ops[1].type == x86.X86_OP_MEM and ops[1].mem.disp == 0
                            and ops[1].mem.index == 0 and _SUB.get(ins.reg_name(ops[1].mem.base)) == "rcx"):
                        this.add(d)          # X.GetObj(): the object under construction
                        vals.pop(d, None)
                        continue
            try:
                written = ins.regs_access()[1]
            except capstone.CsError:
                written = []
            for r in written:
                n = _SUB.get(ins.reg_name(r))
                this.discard(n)
                vals.pop(n, None)
            if m == "call":
                for k in VOLATILE:
                    this.discard(k)
                    vals.pop(k, None)
        return stores, tail

    stores, tail = scan(ctor, set(), True)
    where = ctor
    if not [s for s in stores if s[0] == 0] and tail and tail[1]:
        where = tail[0]
        stores, _ = scan(where, {"rcx"}, False)
    primary = [v for off, v in stores if off == 0]
    secondary = sorted({(off, v) for off, v in stores if off != 0})
    return (primary[-1], where, secondary) if primary else (None, None, secondary)


def main() -> int:
    img = PEImage()
    dimg = load_decrypted(img)
    if dimg is None:
        print("needs the validated decrypted image (tools/matching/ingest_dump.py)", file=sys.stderr)
        return 1
    base, text = img.image_base, img.sections[0]
    allrf = {rf.begin: rf for rf in img.runtime_functions()}
    rd = next(s for s in img.sections if s.name == ".rdata")
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    classes = class_hierarchy(img, dimg, allrf)
    stats = Counter()

    vt: dict[str, int] = {}
    info: dict[str, dict] = {}
    for n, c in sorted(classes.items()):
        f = c["decoded"]
        if not f or not f.get("ctor"):
            stats["GetPrivateStaticClass not decoded"] += 1
            continue
        v, where, secondary = constructor_vtable(md, dimg, allrf, rd, f["ctor"])
        info[n] = {"internal_constructor": f["ctor"], "constructor": where, "secondary": secondary}
        if v is None:
            stats["no vtable store found"] += 1
            continue
        vt[n] = v
    stats["vtables located"] = len(vt)

    blob = img.read(rd.rva, rd.rawsize)
    words = struct.unpack_from(f"<{len(blob) // 8}Q", blob)

    def entry(v: int, i: int) -> int:
        return words[(v - rd.rva) // 8 + i] - base

    def is_code(rva: int) -> bool:
        return 0 <= rva < img.size_of_image and text.contains_rva(rva)

    uo = vt.get("UObject")
    if uo is None:
        print("UObject's vtable not located", file=sys.stderr)
        return 1
    prefix = [words[(uo - rd.rva) // 8 + i] for i in range(UOBJECT_PREFIX)]
    where_val = defaultdict(list)
    for i in range(1, UOBJECT_PREFIX):
        where_val[prefix[i]].append(i)
    score = Counter()
    for j, w in enumerate(words):
        for i in where_val.get(w, ()):
            if j >= i:
                score[j - i] += 1
    starts = {rd.rva + 8 * j for j, s in score.items() if s >= START_MATCHES} | set(vt.values())
    upper: dict[int, int] = {}
    for v in set(vt.values()):
        k = 0
        while (k == 0 or v + 8 * k not in starts) and is_code(entry(v, k)):
            k += 1
        upper[v] = k
    stats["UObject-derived vtable starts"] = len(starts)

    children = defaultdict(list)
    for n, c in classes.items():
        if c["super"] and c["super"] != n:
            children[c["super"]].append(n)

    def subtree(n: str):
        out, todo = [], list(children.get(n, ()))
        while todo:
            x = todo.pop()
            out.append(x)
            todo += children.get(x, ())
        return out

    # Functions at more than one slot index anywhere are folded stubs: no evidence.
    slots_of = defaultdict(set)
    for v, k in upper.items():
        for i in range(k):
            slots_of[entry(v, i)].add(i)

    nat = json.loads(NATIVES.read_text(encoding="utf-8"))
    named = defaultdict(dict)          # owner class -> slot -> CppImplName
    interface_slots = []
    for e in nat["virtual_natives"]:
        c = classes.get(e["class"])
        slot, name = int(e["vtable_offset"], 16) // 8, e["name"].split("::", 1)[1]
        if c and c["decoded"] and c["decoded"]["flags"] & CLASS_INTERFACE:
            # P_THIS of an interface UFunction is the I-class: the slot is in its vtable.
            interface_slots.append({"interface": "I" + e["class"][1:], "slot": slot,
                                    "offset": e["vtable_offset"], "name": name})
            continue
        named[e["class"]][slot] = name
    stats["interface slots (I-class vtables, not modelled)"] = len(interface_slots)

    lower: dict[str, int] = {}
    depth_order, seen = [], set()

    def visit(n: str, d: int = 0):
        if n in seen or d > 64:
            return
        s = classes[n]["super"]
        if s and s != n and s in classes:
            visit(s, d + 1)
        seen.add(n)
        depth_order.append(n)

    for n in sorted(classes):
        visit(n)
    # A class has no more slots than any descendant's vtable run.
    cap: dict[str, int | None] = {}
    for n in reversed(depth_order):
        vals = [upper[vt[n]]] if n in vt else []
        vals += [cap[k] for k in children.get(n, ()) if cap.get(k) is not None]
        cap[n] = min(vals) if vals else None
    evidence = {}
    for n in depth_order:
        s = classes[n]["super"]
        low = lower.get(s, 0) if s and s != n else 0
        why = "superclass"
        if named.get(n):
            k = max(named[n]) + 1
            if k > low:
                low, why = k, "virtual native"
        v = vt.get(n)
        if v is not None:
            for d in subtree(n):
                dv = vt.get(d)
                if dv is None or dv == v:
                    continue
                for i in range(min(cap[n], upper[dv]) - 1, low - 1, -1):
                    e = entry(v, i)
                    if e == entry(dv, i) and len(slots_of[e]) == 1:
                        low, why = i + 1, "inherited by a descendant"
                        break
        lower[n] = low
        evidence[n] = why
    if lower.get("UObject") != UOBJECT_PREFIX:
        print(f"UObject lower count {lower.get('UObject')} != {UOBJECT_PREFIX}", file=sys.stderr)
        return 1
    over = sorted(n for n in classes if cap.get(n) is not None and lower[n] > cap[n])
    stats["lower count exceeds upper count"] = len(over)

    # Slot introductions and implementations.
    def chain(n: str) -> list[str]:
        out = [n]
        while classes[out[-1]]["super"] and classes[out[-1]]["super"] != out[-1] and len(out) < 64:
            out.append(classes[out[-1]]["super"])
        return out[::-1]               # root first

    intro: dict[tuple[str, int], dict] = {}
    conflicts = []
    for owner, slots in sorted(named.items()):
        if owner not in classes:
            continue
        for i, name in sorted(slots.items()):
            at = next(a for a in chain(owner) if lower[a] > i)
            key = (at, i)
            if key in intro and intro[key]["name"] != name:
                conflicts.append({"class": at, "slot": i, "names": sorted({intro[key]["name"], name}),
                                  "owners": sorted({intro[key]["owner"], owner})})
                intro[key]["conflict"] = True
                continue
            intro.setdefault(key, {"class": at, "slot": i, "name": name, "owner": owner})
    for e in conflicts:
        stats["slot named differently by two UFunctions"] += 1

    names_at = defaultdict(set)
    impl_rows = []
    for (at, i), s in sorted(intro.items()):
        if s.get("conflict"):
            continue
        owner = s["owner"]
        for x in [owner] + subtree(owner):
            xv = vt.get(x)
            if xv is None or i >= upper[xv]:
                continue
            imp = entry(xv, i)
            # Named after the topmost class from the owner down to x with this entry.
            path = chain(x)[chain(x).index(owner):] if owner in chain(x) else [x]
            first = next((p for p in path if vt.get(p) is not None and i < upper[vt[p]] and entry(vt[p], i) == imp), x)
            names_at[imp].add(f"{first}::{s['name']}")
            impl_rows.append((imp, f"{first}::{s['name']}", i, first))
    # A direct native (called by name from its thunk) at the same address with another name:
    # identical code folded by the linker, unless that name is itself low-confidence.
    direct = {int(e["rva"], 16): e for e in nat["natives"]}
    implementations, folded = [], []
    for imp, names in sorted(names_at.items()):
        multi_slot = len(slots_of[imp]) > 1
        dn = direct.get(imp)
        if dn and dn["name"] not in names and dn["confidence"].startswith("high"):
            names = names | {dn["name"]}
            stats["implementation also a direct native with another name"] += 1
        if len(names) == 1 and not multi_slot:
            (nm,) = names
            cls = nm.split("::")[0]
            implementations.append({"rva": f"0x{imp:08X}", "name": nm, "class": cls,
                                    "slot": next(r[2] for r in impl_rows if r[0] == imp),
                                    "pdata": imp in allrf, "confidence": "high-confidence inferred"})
        else:
            folded.append({"rva": f"0x{imp:08X}", "names": sorted(names)[:8], "name_count": len(names),
                           "slot_indexes": len(slots_of[imp])})
    stats["implementations named"] = len(implementations)
    stats["implementations folded or ambiguous"] = len(folded)

    rows = []
    for n in sorted(classes):
        v = vt.get(n)
        i = info.get(n, {})
        rows.append({"class": n, "super": classes[n]["super"],
                     "vtable": f"0x{v:08X}" if v is not None else None,
                     "constructor": f"0x{i['constructor']:08X}" if i.get("constructor") else None,
                     "slots_lower": lower.get(n), "slots_upper": cap.get(n),
                     "lower_evidence": evidence.get(n),
                     "secondary_vtables": [[f"0x{o:X}", f"0x{x:08X}"] for o, x in i.get("secondary", [])]})
    slots = [{"class": s["class"], "slot": s["slot"], "offset": f"0x{8 * s['slot']:X}", "name": s["name"],
              "ufunction_class": s["owner"]} for (_, _), s in sorted(intro.items()) if not s.get("conflict")]
    summary = dict(stats)
    summary["classes"] = len(classes)
    summary["named_slots"] = len(slots)
    out = {
        "schema_version": 1,
        "generated_by": "tools/analysis/vtables.py",
        "reference_sha256": img.sha256(),
        "evidence": ("Primary vtable from the [this] store of C::C(const FObjectInitializer&) reached through "
                     "InternalConstructor<C>; slot counts bounded by UObject-derived vtable starts (upper) and "
                     "by inherited entries and virtual natives (lower); slot names from virtual natives."),
        "summary": summary,
        "classes": rows,
        "slots": slots,
        "implementations": implementations,
        "folded": folded,
        "conflicts": conflicts,
        "interface_slots": sorted(interface_slots, key=lambda e: (e["interface"], e["slot"])),
        "lower_exceeds_upper": over,
    }
    lines = ["{"]
    keys = list(out)
    for j, k in enumerate(keys):
        val, comma = out[k], "," if j < len(keys) - 1 else ""
        if isinstance(val, list):
            lines.append(f" {json.dumps(k)}: [")
            lines += [f"  {json.dumps(x)}" + ("," if q < len(val) - 1 else "") for q, x in enumerate(val)]
            lines.append(f" ]{comma}")
        else:
            lines.append(f" {json.dumps(k)}: {json.dumps(val)}{comma}")
    lines.append("}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
