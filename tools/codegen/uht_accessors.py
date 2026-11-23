"""Native accessors: natives whose whole body reads or writes one reflected member.

Forms (the native's class or a superclass owns the member; N is its reflected offset):
- scalar getter / setter: one load from [rcx+N] and `ret`, or one store of the argument to
  [rcx+N] and `ret`: `return Member;` / `Member = Value;`;
- struct getter by value: a copy of the struct at [rcx+N] to the hidden return pointer rdx, then
  `mov rax, rdx`: `return Member;`;
- struct getter through an out parameter: the same copy to the reference in rdx, no return
  value: `Out = Member;`;
- struct setter: a copy of the struct referenced by rdx to [rcx+N]: `Member = Value;`;
- bitfield getter / setter: the storage unit at [rcx+N] masked (and shifted) to one bit, or
  that bit replaced by the argument's low bit.

Each is accepted only when all of these agree:
- the member is a reflected property at that offset (or, for a bitfield, at that bit). A bool
  is located through its SetBit function: `mov byte ptr [rcx+N], 1` for a native bool,
  `or byte|dword ptr [rcx+N], mask` for a bitfield;
- the property's C++ type is the UFunction's return type, its only parameter type, or (a
  struct copied out) its only out parameter's type;
- the copy covers exactly the struct's reflected size (FStructParams), or the instruction
  width fits the scalar type, or the bitfield's storage width (its SetBit operand) is the access width.

Such natives are defined out of line, one translation unit per package
(Source/Generated/Natives/<Package>.natives.cpp). The reference compiles them in the class's own
.cpp, apart from the exec thunks, which therefore call them. Their members are declared at their
offsets in Classes.gen.h. A thunk's call then resolves through the accessor's exact match.

Only types with a plain MSVC decoration are accepted: bool, the sized integers, float, double,
pointers to reflected classes, enums, and structs the shims define with `struct`.
TEnumAsByte signatures are left out.
"""
from __future__ import annotations

import re
import struct
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHIMS = ROOT / "FortniteGameCode" / "Shims" / "FortniteGameCode"

LOAD = [  # scalar getter: (instruction pattern, register class)
    (r"movzx eax, byte ptr \[rcx \+ (0x[0-9a-f]+)\]", "b1"),
    (r"mov eax, dword ptr \[rcx \+ (0x[0-9a-f]+)\]", "i4"),
    (r"mov rax, qword ptr \[rcx \+ (0x[0-9a-f]+)\]", "i8"),
    (r"movss xmm0, dword ptr \[rcx \+ (0x[0-9a-f]+)\]", "f4"),
    (r"movsd xmm0, qword ptr \[rcx \+ (0x[0-9a-f]+)\]", "f8"),
]
STORE = [  # scalar setter
    (r"mov byte ptr \[rcx \+ (0x[0-9a-f]+)\], dl", "b1"),
    (r"mov word ptr \[rcx \+ (0x[0-9a-f]+)\], dx", "i2"),
    (r"mov dword ptr \[rcx \+ (0x[0-9a-f]+)\], edx", "i4"),
    (r"mov qword ptr \[rcx \+ (0x[0-9a-f]+)\], rdx", "i8"),
    (r"movss dword ptr \[rcx \+ (0x[0-9a-f]+)\], xmm1", "f4"),
    (r"movsd qword ptr \[rcx \+ (0x[0-9a-f]+)\], xmm1", "f8"),
]
SCALAR = {"bool": ("_N", "b1"), "int8": ("C", "b1"), "uint8": ("E", "b1"), "int16": ("F", "i2"),
          "uint16": ("G", "i2"), "int32": ("H", "i4"), "uint32": ("I", "i4"), "int64": ("_J", "i8"),
          "uint64": ("_K", "i8"), "float": ("M", "f4"), "double": ("N", "f8")}
SIZE = {"b1": (1, 1), "i2": (2, 2), "i4": (4, 4), "i8": (8, 8), "f4": (4, 4), "f8": (8, 8)}
WIDTH = {"byte": 1, "word": 2, "dword": 4, "qword": 8, "xmmword": 16}
COPY_OPS = ("mov", "movzx", "movss", "movsd", "movups", "movaps", "movdqu", "movdqa", "movq", "movd")
MEM = r"(byte|word|dword|qword|xmmword) ptr \[(rcx|rdx)(?: \+ (0x[0-9a-f]+|\d+))?\]"


FAMILY = {}
for _b in ("ax", "bx", "cx", "dx"):
    for _r in (_b[0] + "l", _b[0] + "h", _b, "e" + _b, "r" + _b):
        FAMILY[_r] = "r" + _b
for _b in ("si", "di", "bp", "sp"):
    for _r in (_b + "l", _b, "e" + _b, "r" + _b):
        FAMILY[_r] = "r" + _b
for _n in range(8, 16):
    for _s in ("", "d", "w", "b"):
        FAMILY[f"r{_n}{_s}"] = f"r{_n}"
NUM = r"(-?0x[0-9a-f]+|-?\d+)"


def family(reg: str) -> str:
    """Register family: al/ax/eax/rax -> rax, r8b/r8d -> r8; xmm registers as they are."""
    return FAMILY.get(reg, reg)


_KEYWORDS: dict[str, str] | None = None


def record_keyword(name: str) -> str | None:
    """'U' for a type the shims define with `struct`, 'V' with `class`, None if not defined."""
    global _KEYWORDS
    if _KEYWORDS is None:
        _KEYWORDS = {}
        for h in SHIMS.glob("*.h"):
            for kw, n in re.findall(r"^(struct|class)\s+(?:alignas\(\d+\)\s+)?(F\w+)\b[^;]*$",
                                    h.read_text(encoding="utf-8"), re.M):
                _KEYWORDS.setdefault(n, "U" if kw == "struct" else "V")
    return _KEYWORDS.get(name)


def width_class(ctype: str, enums: dict[str, int]) -> str | None:
    """The register class a type is loaded or stored with, or None if not supported."""
    if ctype in SCALAR:
        return SCALAR[ctype][1]
    if re.fullmatch(r"[AUI][A-Za-z0-9_]+\*", ctype):
        return "i8"
    if ctype in enums:
        return {1: "b1", 2: "i2", 4: "i4", 8: "i8"}.get(enums[ctype])
    return None


def mangle(cls: str, name: str, ret: str | None, params: list[str], const: bool, enums: dict[str, int]) -> str:
    """MSVC (x64) decorated name of a public non-virtual member function with the types above."""
    table: list[str] = []

    def qual(parts: list[str]) -> str:      # innermost first, each a name or a back-reference
        out = ""
        for p in parts:
            if p in table:
                out += str(table.index(p))
            else:
                out += p + "@"
                if len(table) < 10:
                    table.append(p)
        return out + "@"

    def typ(t: str) -> str:
        if t in SCALAR:
            return SCALAR[t][0]
        m = re.fullmatch(r"(const )?(F\w+)&", t)
        if m and record_keyword(m.group(2)):
            return ("AEB" if m.group(1) else "AEA") + record_keyword(m.group(2)) + qual([m.group(2)])
        if re.fullmatch(r"F\w+", t) and record_keyword(t):
            return record_keyword(t) + qual([t])
        if t.endswith("*"):
            return "PEAV" + qual([t[:-1]])
        if t in enums:
            return "W4" + qual(list(reversed(t.split("::"))))
        raise ValueError(t)

    head = "?" + qual([name, cls])
    # A returned enum or struct (a user-defined type, not a pointer) carries the ?A storage prefix.
    udt = ret is not None and (ret in enums or (re.fullmatch(r"F\w+", ret) and record_keyword(ret)))
    rcode = ("?A" if udt else "") + typ(ret) if ret else "X"
    return (head + "QE" + ("B" if const else "A") + "A" + rcode
            + ("".join(typ(p) for p in params) + "@" if params else "X") + "Z")


def bool_offset(dimg, base: int, p: dict) -> int | None:
    """Offset of a native (non-bitfield) bool from its SetBit function: mov byte ptr [rcx+N], 1."""
    if not p["func2"]:
        return None
    try:
        b = dimg.read(p["func2"] - base, 8)
    except ValueError:
        return None
    if b[:2] == b"\xc6\x41" and b[3] == 1 and b[4] == 0xC3:
        return b[2]
    if b[:2] == b"\xc6\x81" and b[6] == 1 and b[7] == 0xC3:
        return struct.unpack_from("<I", b, 2)[0]
    return None


def bitfield_bit(dimg, base: int, md, p: dict) -> tuple[int, int] | None:
    """(absolute bit index, storage width) of a bitfield bool, from its SetBit function:
    `or byte|dword ptr [rcx+N], mask; ret` with a single-bit mask. The operand width is the
    storage unit's (uint8 or uint32); FBoolPropertyParams.ElementSize is 1 for both."""
    if not p["func2"]:
        return None
    try:
        b = dimg.read(p["func2"] - base, 16)
    except ValueError:
        return None
    ins = []
    for i in md.disasm(b, p["func2"]):
        ins.append(i)
        if len(ins) == 2:
            break
    if len(ins) != 2 or ins[1].mnemonic != "ret":
        return None
    m = re.fullmatch(r"(byte|word|dword) ptr \[rcx(?: \+ (0x[0-9a-f]+|\d+))?\], (0x[0-9a-f]+|\d+)", ins[0].op_str)
    if ins[0].mnemonic != "or" or not m:
        return None
    mask = int(m.group(3), 0)
    if mask & (mask - 1):
        return None
    return int(m.group(2) or "0", 0) * 8 + mask.bit_length() - 1, WIDTH[m.group(1)]


def copy_shape(ins) -> dict | None:
    """A body (without its ret) that only copies bytes between [rcx+...] and [rdx+...]: the
    source and destination bases, the constant src - dst offset, the copied size and whether
    rdx is returned. None unless the destination is covered exactly once from offset 0."""
    regs, stores, ret_rdx = {}, [], False
    for i in ins:
        mn, ops = i.mnemonic, i.op_str
        if mn == "mov" and ops == "rax, rdx":
            ret_rdx = True
            continue
        m = re.fullmatch(r"(\w+), " + MEM, ops)
        if mn in COPY_OPS and m:
            reg, w, b, off = m.groups()
            regs[family(reg)] = (b, int(off or "0", 0), WIDTH[w])
            continue
        m = re.fullmatch(MEM + r", (\w+)", ops)
        if mn in COPY_OPS and m:
            w, b, off, reg = m.groups()
            src = regs.get(family(reg))
            if src is None or src[2] != WIDTH[w] or src[0] == b:
                return None
            stores.append((b, int(off or "0", 0), WIDTH[w], src[0], src[1]))
            continue
        return None
    if not stores:
        return None
    dst = {s[0] for s in stores}
    srcb = {s[3] for s in stores}
    delta = {s[4] - s[1] for s in stores}
    if len(dst) != 1 or len(srcb) != 1 or len(delta) != 1:
        return None
    cover = sorted((s[1], s[1] + s[2]) for s in stores)
    at = 0
    for lo, hi in cover:
        if lo != at:
            return None
        at = hi
    return {"dst": dst.pop(), "src": srcb.pop(), "delta": delta.pop(), "size": at, "ret_rdx": ret_rdx}


def bit_shape(ins) -> dict | None:
    """Bitfield getter (load the unit at [rcx+N], optional shift, `and 1`) or setter (clear the
    bit, take the argument's low bit, optional shift, `or` it in). Returns kind, N, width, bit."""
    t = [(i.mnemonic, i.op_str) for i in ins]
    m = re.fullmatch(r"(eax|al), (byte|dword) ptr \[rcx(?: \+ (0x[0-9a-f]+|\d+))?\]", t[0][1]) if t else None
    if m and t[0][0] in ("mov", "movzx"):
        width = WIDTH[m.group(2)]
        off = int(m.group(3) or "0", 0)
        rest, bit = t[1:], 0
        if rest and rest[0][0] == "shr" and re.fullmatch(r"(eax|al), " + NUM, rest[0][1]):
            bit, rest = int(rest[0][1].split(", ")[1], 0), rest[1:]
        if [x for x in rest] in ([("and", "eax, 1")], [("and", "al, 1")]) and bit < 8 * width:
            # For a uint32 unit, `return b;` masks eax and `return b ? true : false;` masks al
            # (v140, probed); a uint8 unit masks al either way.
            ternary = width == 4 and rest[0][1].startswith("al")
            return {"kind": "get", "offset": off, "width": width, "bit": bit, "ternary": ternary}
        return None
    m = re.fullmatch(r"(byte|dword) ptr \[rcx(?: \+ (0x[0-9a-f]+|\d+))?\], " + NUM, t[0][1]) if t else None
    if m and t[0][0] == "and" and t[-1][0] == "or":
        width = WIDTH[m.group(1)]
        off = int(m.group(2) or "0", 0)
        clear = int(m.group(3), 0)
        last = re.fullmatch(r"(byte|dword) ptr \[rcx(?: \+ (0x[0-9a-f]+|\d+))?\], (\w+)", t[-1][1])
        if not last or WIDTH[last.group(1)] != width or int(last.group(2) or "0", 0) != off:
            return None
        bit = 0
        for mn, ops in t[1:-1]:
            if mn == "shl" and re.fullmatch(r"\w+, " + NUM, ops):
                bit = int(ops.split(", ")[1], 0)
            elif not ((mn == "movzx" and ops.endswith(", dl")) or (mn == "and" and ops.endswith(", 1"))
                      or (mn == "mov" and ops.endswith(", edx"))):
                return None
        full = (1 << (8 * width)) - 1
        if clear & full != full ^ (1 << bit):
            return None
        return {"kind": "set", "offset": off, "width": width, "bit": bit}
    return None


def find(dimg, base: int, md, natives: list[dict], class_props, sup, names, uht_props, signature) -> dict:
    """Accessors among `natives` (native-implementations.json entries).

    class_props(cls) -> decoded reflected properties of cls; sup(cls) -> superclass or None;
    signature(cls, ufunction, exec_rva) -> uht_exec.signature result. Each accessor carries its
    declaration, definition head and body, MSVC symbol and member: {"kind": "plain", "offset",
    "ctype", "name", "size"} or {"kind": "bit", "offset", "width", "bit", "name"}.
    """
    rejected = defaultdict(int)
    enum_sizes: dict[str, int] = {}
    out = []
    execs = defaultdict(int)
    for n in natives:
        execs[n["exec_rva"]] += 1

    def member_at(cls: str, off: int):
        c = cls
        while c:
            for p in class_props(c):
                if p["type"] == "Bool":
                    if bool_offset(dimg, base, p) == off:
                        return c, p, "bool"
                    continue
                if p["offset"] != off or p["dim"] != 1:
                    continue
                if p["type"] == "Byte" and p["func"]:
                    e = names.enum(p["func"], base, "uint8")
                    if e is None:
                        return None
                    enum_sizes[e["cpp"]] = 1
                    return c, p, (e["cpp"] if e["form"] == uht_props.ENUM_CLASS else f"TEnumAsByte<{e['cpp']}>")
                q = uht_props.parameter(dict(p, flags=0), names, base)
                if q is None:
                    return None
                ctype = q["decl"].rsplit(" ", 1)[0]
                if p["type"] == "Enum":
                    enum_sizes[ctype] = {"Byte": 1, "UInt16": 2, "Int16": 2, "Int": 4, "UInt32": 4,
                                         "Int64": 8, "UInt64": 8}.get(p["inner"][0]["type"] if p["inner"] else "", 0)
                return c, p, ctype
            c = sup(c)
        return None

    def bit_at(cls: str, absbit: int, width: int):
        c = cls
        while c:
            for p in class_props(c):
                if p["type"] == "Bool" and bitfield_bit(dimg, base, md, p) == (absbit, width):
                    return c, p
            c = sup(c)
        return None

    for n in natives:
        if n.get("confidence") != "high-confidence inferred" or n.get("call") not in ("call", "jmp"):
            rejected["not a high-confidence direct native"] += 1
            continue
        if execs[n["exec_rva"]] != 1:
            rejected["thunk shared"] += 1
            continue
        r = int(n["rva"], 16)
        try:
            code = dimg.read(r, 64)
        except ValueError:
            continue
        ins = []
        for i in md.disasm(code, r):
            ins.append(i)
            if i.mnemonic in ("ret", "jmp", "call") or len(ins) > 10:
                break
        if not ins or ins[-1].mnemonic != "ret" or ins[-1].op_str:
            rejected["not a short body ending in ret"] += 1
            continue
        cls, uf = n["class"], n["ufunction"]
        name = n["name"].split("::", 1)[1]
        const_of = lambda s: " const" if s["const"] else ""   # noqa: E731
        rec = None
        if len(ins) == 2:
            text = f"{ins[0].mnemonic} {ins[0].op_str}"
            kind = off = wc = None
            for pat, w in LOAD:
                m = re.fullmatch(pat, text)
                if m:
                    kind, off, wc = "get", int(m.group(1), 16), w
            for pat, w in STORE:
                m = re.fullmatch(pat, text)
                if m:
                    kind, off, wc = "set", int(m.group(1), 16), w
            if kind is None:
                rejected["other shape"] += 1
                continue
            hit = member_at(cls, off)
            if hit is None:
                rejected["no reflected member at the offset"] += 1
                continue
            owner, prop, mtype = hit
            sig = signature(cls, uf, int(n["exec_rva"], 16))
            if sig is None:
                rejected["signature not recovered"] += 1
                continue
            ptypes = [d.rsplit(" ", 1)[0] for d, _, _ in sig["params"]]
            bare = mtype.replace("TEnumAsByte<", "")[:-1]
            if kind == "get":
                ok = not ptypes and sig["ret"] is not None and sig["ret"] in (mtype, bare)
                vtype = sig["ret"]
            else:
                ok = sig["ret"] is None and len(ptypes) == 1 and ptypes[0] in (mtype, bare)
                vtype = ptypes[0] if ptypes else None
            if not ok:
                rejected["signature disagrees with the member"] += 1
                continue
            if width_class(vtype, enum_sizes) != wc or (mtype.startswith("TEnumAsByte<") and wc != "b1"):
                rejected["width disagrees"] += 1
                continue
            size, align = SIZE[width_class(mtype if not mtype.startswith("TEnumAsByte<") else "uint8", enum_sizes) or wc]
            member = {"kind": "plain", "offset": off, "ctype": mtype, "name": prop["name"], "size": size, "align": align}
            if kind == "get":
                decl, body = f"{sig['ret']} {name}(){const_of(sig)}", f"\treturn {prop['name']};"
            else:
                pdecl = sig["params"][0][0]
                decl, body = f"void {name}({pdecl}){const_of(sig)}", f"\t{prop['name']} = {pdecl.rsplit(' ', 1)[1]};"
            rec = (owner, member, sig, ptypes, decl, body, kind)
        else:
            body_ins = ins[:-1]
            shape = copy_shape(body_ins)
            bits = None if shape else bit_shape(body_ins)
            if shape is None and bits is None:
                rejected["other shape"] += 1
                continue
            sig = signature(cls, uf, int(n["exec_rva"], 16))
            if sig is None:
                rejected["signature not recovered"] += 1
                continue
            ptypes = [d.rsplit(" ", 1)[0] for d, _, _ in sig["params"]]
            if shape is not None:
                if shape["src"] == "rcx" and shape["dst"] == "rdx":
                    kind = "get" if shape["ret_rdx"] else "out"
                    off = shape["delta"]
                elif shape["src"] == "rdx" and shape["dst"] == "rcx" and not shape["ret_rdx"]:
                    kind, off = "set", -shape["delta"]
                else:
                    rejected["other copy"] += 1
                    continue
                hit = member_at(cls, off) if off > 0 else None
                if hit is None or hit[1]["type"] != "Struct":
                    rejected["no reflected struct member at the offset"] += 1
                    continue
                owner, prop, mtype = hit
                info = names.structs.get(prop["func"] - base) if prop["func"] else None
                if not info or info[1] != shape["size"] or not record_keyword(mtype):
                    rejected["struct size or model disagrees"] += 1
                    continue
                if kind == "get":
                    ok = not ptypes and sig["ret"] == mtype
                    decl, body = f"{mtype} {name}(){const_of(sig)}", f"\treturn {prop['name']};"
                elif kind == "out":
                    ok = sig["ret"] is None and ptypes == [f"{mtype}&"]
                    pdecl = sig["params"][0][0] if ok else ""
                    decl, body = f"void {name}({pdecl}){const_of(sig)}", f"\t{pdecl.rsplit(' ', 1)[-1]} = {prop['name']};"
                else:
                    ok = sig["ret"] is None and len(ptypes) == 1 and ptypes[0] in (f"const {mtype}&", mtype)
                    pdecl = sig["params"][0][0] if ok else ""
                    decl, body = f"void {name}({pdecl}){const_of(sig)}", f"\t{prop['name']} = {pdecl.rsplit(' ', 1)[-1]};"
                if not ok:
                    rejected["signature disagrees with the member"] += 1
                    continue
                member = {"kind": "plain", "offset": off, "ctype": mtype, "name": prop["name"], "size": info[1],
                          "align": info[2]}
            else:
                kind, off, width = bits["kind"], bits["offset"], bits["width"]
                if off % width:
                    rejected["misaligned"] += 1
                    continue
                hit = bit_at(cls, off * 8 + bits["bit"], width)
                if hit is None:
                    rejected["no reflected bitfield at the bit"] += 1
                    continue
                owner, prop = hit
                if kind == "get":
                    ok = not ptypes and sig["ret"] == "bool"
                    value = f"{prop['name']} ? true : false" if bits.get("ternary") else prop["name"]
                    decl, body = f"bool {name}(){const_of(sig)}", f"\treturn {value};"
                else:
                    ok = sig["ret"] is None and ptypes == ["bool"]
                    pdecl = sig["params"][0][0] if ok else ""
                    decl, body = f"void {name}({pdecl}){const_of(sig)}", f"\t{prop['name']} = {pdecl.rsplit(' ', 1)[-1]};"
                if not ok:
                    rejected["signature disagrees with the member"] += 1
                    continue
                member = {"kind": "bit", "offset": off, "width": width, "bit": bits["bit"], "name": prop["name"],
                          "size": width, "align": width}
            rec = (owner, member, sig, ptypes, decl, body, kind)
        owner, member, sig, ptypes, decl, body, kind = rec
        if any("TEnumAsByte" in t for t in ptypes + [sig["ret"] or ""]):
            rejected["TEnumAsByte signature"] += 1
            continue
        try:
            symbol = mangle(cls, name, sig["ret"], ptypes, sig["const"], enum_sizes)
        except ValueError:
            rejected["type not mangled"] += 1
            continue
        if member["offset"] % member["align"]:
            rejected["misaligned"] += 1
            continue
        out.append({"class": cls, "ufunction": uf, "name": name, "rva": r, "end": ins[-1].address + 1,
                    "exec_rva": n["exec_rva"], "kind": kind, "member": member["name"], "owner": owner,
                    "offset": member["offset"], "size": member["size"], "mspec": member,
                    "decl": decl, "head": decl.replace(f"{name}(", f"{cls}::{name}(", 1), "body": body,
                    "symbol": symbol, "pdata": bool(n.get("pdata"))})
    return {"natives": out, "rejected": dict(rejected), "enum_sizes": enum_sizes}
