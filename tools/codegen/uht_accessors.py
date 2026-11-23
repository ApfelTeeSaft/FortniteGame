"""Trivial native accessors: natives whose whole body reads or writes one reflected member.

A native whose body is one load from [rcx+N] and `ret` (getter), or one store of its argument to
[rcx+N] and `ret` (setter), is `return Member;` or `Member = Value;` when all of these agree:
- N is the offset of a reflected property of the native's class or a superclass. Native bools
  are located through their SetBit function (`mov byte ptr [rcx+N], 1`); bitfields are skipped.
- The property's C++ type is the UFunction's return type (getter, no parameters) or its only
  parameter type (setter, no return value).
- The instruction's width and register class fit that type.

Such natives are defined out of line, one translation unit per package
(Source/Generated/Natives/<Package>.natives.cpp). The reference compiles them in the class's own
.cpp, apart from the exec thunks, which therefore call them. Their members are declared at their
offsets in Classes.gen.h. A thunk's call then resolves through the accessor's exact match.

Only types with a plain MSVC mangling are accepted: bool, the sized integers, float, double,
pointers to reflected classes, and enums. TEnumAsByte signatures are left out.
"""
from __future__ import annotations

import re
import struct
from collections import defaultdict

LOAD = [  # getter: (instruction pattern, accepted C++ type predicate)
    (r"movzx eax, byte ptr \[rcx \+ (0x[0-9a-f]+)\]", "b1"),
    (r"mov eax, dword ptr \[rcx \+ (0x[0-9a-f]+)\]", "i4"),
    (r"mov rax, qword ptr \[rcx \+ (0x[0-9a-f]+)\]", "i8"),
    (r"movss xmm0, dword ptr \[rcx \+ (0x[0-9a-f]+)\]", "f4"),
    (r"movsd xmm0, qword ptr \[rcx \+ (0x[0-9a-f]+)\]", "f8"),
]
STORE = [  # setter
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
        if t.endswith("*"):
            return "PEAV" + qual([t[:-1]])
        if t in enums:
            return "W4" + qual(list(reversed(t.split("::"))))
        raise ValueError(t)

    head = "?" + qual([name, cls])
    # A returned enum (a user-defined type, not a pointer) carries the ?A storage prefix.
    rcode = ("?A" if ret in enums else "") + typ(ret) if ret else "X"
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


def find(dimg, base: int, md, natives: list[dict], class_props, sup, names, uht_props, signature) -> dict:
    """Accessors among `natives` (native-implementations.json entries).

    class_props(cls) -> decoded reflected properties of cls; sup(cls) -> superclass or None;
    signature(cls, ufunction, exec_rva) -> uht_exec.signature result. Returns {"natives": [...],
    "members": {owner: {offset: (ctype, name)}}, "rejected": Counter-like dict}.
    """
    rejected = defaultdict(int)
    enum_sizes: dict[str, int] = {}
    members: dict[str, dict[int, tuple[str, str]]] = defaultdict(dict)
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

    for n in natives:
        if n.get("confidence") != "high-confidence inferred" or n.get("call") not in ("call", "jmp"):
            rejected["not a high-confidence direct native"] += 1
            continue
        if execs[n["exec_rva"]] != 1:
            rejected["thunk shared"] += 1
            continue
        r = int(n["rva"], 16)
        try:
            code = dimg.read(r, 16)
        except ValueError:
            continue
        ins = []
        for i in md.disasm(code, r):
            ins.append(i)
            if len(ins) == 2:
                break
        if len(ins) != 2 or ins[1].mnemonic != "ret" or ins[1].op_str:
            rejected["not two instructions"] += 1
            continue
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
        cls, uf = n["class"], n["ufunction"]
        name = n["name"].split("::", 1)[1]
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
        if kind == "get":
            ok = not ptypes and sig["ret"] is not None and sig["ret"] in (mtype, mtype.replace("TEnumAsByte<", "")[:-1])
            vtype = sig["ret"]
        else:
            ok = sig["ret"] is None and len(ptypes) == 1 and ptypes[0] in (mtype, mtype.replace("TEnumAsByte<", "")[:-1])
            vtype = ptypes[0] if ptypes else None
        if not ok:
            rejected["signature disagrees with the member"] += 1
            continue
        if width_class(vtype, enum_sizes) != wc or (mtype.startswith("TEnumAsByte<") and wc != "b1"):
            rejected["width disagrees"] += 1
            continue
        if any("TEnumAsByte" in t for t in ptypes + [sig["ret"] or ""]):
            rejected["TEnumAsByte signature"] += 1
            continue
        try:
            symbol = mangle(cls, name, sig["ret"], ptypes, sig["const"], enum_sizes)
        except ValueError:
            rejected["type not mangled"] += 1
            continue
        size, align = SIZE[width_class(mtype if not mtype.startswith("TEnumAsByte<") else "uint8", enum_sizes) or wc]
        if off % align:
            rejected["misaligned"] += 1
            continue
        prev = members[owner].get(off)
        if prev is not None and prev != (mtype, prop["name"]):
            rejected["member conflict"] += 1
            continue
        members[owner][off] = (mtype, prop["name"])
        pname = sig["params"][0][0].rsplit(" ", 1)[1] if kind == "set" else None
        out.append({"class": cls, "ufunction": uf, "name": name, "rva": r, "end": ins[1].address + 1,
                    "exec_rva": n["exec_rva"], "kind": kind, "member": prop["name"], "owner": owner,
                    "offset": off, "mtype": mtype, "ret": sig["ret"], "param": (ptypes[0], pname) if pname else None,
                    "const": sig["const"], "symbol": symbol, "size": size, "pdata": bool(n.get("pdata"))})
    return {"natives": out, "members": {k: dict(v) for k, v in members.items()}, "rejected": dict(rejected),
            "enum_sizes": enum_sizes}
