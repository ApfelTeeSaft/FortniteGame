"""x64 UNWIND_INFO decoding and on-disk prologue verification.

A function's unwind codes are stored in plaintext ``.rdata``. Comparing them
with the instructions actually present at the function's start gives strong,
independent evidence about whether the on-disk body is plaintext code: a
random (encrypted) byte stream essentially never decodes into the exact push,
stack-allocation and save sequence the unwind record describes.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

REGS = ["rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi",
        "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15"]

UWOP_PUSH_NONVOL, UWOP_ALLOC_LARGE, UWOP_ALLOC_SMALL, UWOP_SET_FPREG = 0, 1, 2, 3
UWOP_SAVE_NONVOL, UWOP_SAVE_NONVOL_FAR = 4, 5
UWOP_EPILOG, UWOP_SPARE = 6, 7
UWOP_SAVE_XMM128, UWOP_SAVE_XMM128_FAR, UWOP_PUSH_MACHFRAME = 8, 9, 10

UNW_FLAG_EHANDLER, UNW_FLAG_UHANDLER, UNW_FLAG_CHAININFO = 1, 2, 4

_md = Cs(CS_ARCH_X86, CS_MODE_64)


@dataclass
class UnwindCode:
    offset: int
    op: int
    info: int
    value: int | None = None  # decoded operand (size / stack offset)


@dataclass
class UnwindInfo:
    rva: int
    version: int
    flags: int
    prolog_size: int
    frame_reg: int
    frame_off: int
    codes: list[UnwindCode] = field(default_factory=list)
    handler: int | None = None
    chained: tuple[int, int, int] | None = None


def parse_unwind(img, rva: int) -> UnwindInfo:
    hdr = img.read(rva, 4)
    ver, flags = hdr[0] & 7, hdr[0] >> 3
    ui = UnwindInfo(rva, ver, flags, hdr[1], hdr[3] & 15, hdr[3] >> 4)
    count = hdr[2]
    slots = struct.unpack("<%dH" % count, img.read(rva + 4, 2 * count)) if count else ()
    i = 0
    while i < count:
        s = slots[i]
        code = UnwindCode(s & 0xFF, (s >> 8) & 15, s >> 12)
        i += 1
        if code.op == UWOP_ALLOC_LARGE:
            if code.info == 0:
                code.value = slots[i] * 8; i += 1
            else:
                code.value = slots[i] | (slots[i + 1] << 16); i += 2
        elif code.op == UWOP_ALLOC_SMALL:
            code.value = code.info * 8 + 8
        elif code.op == UWOP_SAVE_NONVOL:
            code.value = slots[i] * 8; i += 1
        elif code.op == UWOP_SAVE_NONVOL_FAR:
            code.value = slots[i] | (slots[i + 1] << 16); i += 2
        elif code.op == UWOP_SAVE_XMM128:
            code.value = slots[i] * 16; i += 1
        elif code.op == UWOP_SAVE_XMM128_FAR:
            code.value = slots[i] | (slots[i + 1] << 16); i += 2
        elif code.op in (UWOP_EPILOG, UWOP_SPARE):
            # Version 2 epilog descriptors occupy one slot; skip conservatively.
            pass
        ui.codes.append(code)
    tail = rva + 4 + 2 * (count + (count & 1))
    if flags & UNW_FLAG_CHAININFO:
        ui.chained = struct.unpack("<III", img.read(tail, 12))
    elif flags & (UNW_FLAG_EHANDLER | UNW_FLAG_UHANDLER):
        ui.handler = img.u32(tail)
    return ui


_SAVE_RE = re.compile(r"qword ptr \[(?:rsp|rax|r11|rbp)(?: [+-] 0x[0-9a-f]+)?\], (\w+)$")
_XMM_RE = re.compile(r"xmmword ptr \[(?:rsp|rax|r11|rbp)(?: [+-] 0x[0-9a-f]+)?\], (xmm\d+)$")


def _imm(text: str) -> int | None:
    try:
        return int(text, 0)
    except ValueError:
        return None


def verify_prologue(img, begin: int, ui: UnwindInfo) -> tuple[str, str]:
    """Return (verdict, detail). verdict in verified/mismatch/no-codes/undecodable."""
    codes = [c for c in ui.codes if c.op not in (UWOP_EPILOG, UWOP_SPARE)]
    if not codes:
        return "no-codes", "unwind record has no prologue codes"
    try:
        raw = img.read(begin, max(ui.prolog_size, 1))
    except ValueError:
        return "undecodable", "prologue not file-backed"
    insns = []
    pos = 0
    for ins in _md.disasm(raw, begin):
        insns.append((pos, pos + ins.size, ins.mnemonic, ins.op_str))
        pos += ins.size
    if pos < ui.prolog_size:
        return "undecodable", f"linear decode stopped at +{pos:#x} of {ui.prolog_size:#x}"
    by_end = {e: (m, o) for (_, e, m, o) in insns}
    for c in codes:
        if c.op in (UWOP_PUSH_NONVOL, UWOP_ALLOC_SMALL, UWOP_ALLOC_LARGE, UWOP_SET_FPREG):
            if c.offset not in by_end:
                return "mismatch", f"code offset +{c.offset:#x} is not an instruction boundary"
            m, o = by_end[c.offset]
            if c.op == UWOP_PUSH_NONVOL:
                if not (m == "push" and o == REGS[c.info]):
                    return "mismatch", f"+{c.offset:#x}: expected push {REGS[c.info]}, found {m} {o}"
            elif c.op in (UWOP_ALLOC_SMALL, UWOP_ALLOC_LARGE):
                ok = False
                if m == "sub" and o.startswith("rsp, "):
                    arg = o[5:]
                    ok = arg == "rax" or _imm(arg) == c.value
                if not ok:
                    return "mismatch", f"+{c.offset:#x}: expected sub rsp, {c.value:#x}, found {m} {o}"
            else:
                fr = REGS[ui.frame_reg]
                want = ui.frame_off * 16
                ok = (m == "mov" and o == f"{fr}, rsp" and want == 0) or (
                    m == "lea" and (o == f"{fr}, [rsp + {want:#x}]" or (want == 0 and o == f"{fr}, [rsp]")))
                if not ok:
                    return "mismatch", f"+{c.offset:#x}: expected frame setup of {fr}, found {m} {o}"
        elif c.op in (UWOP_SAVE_NONVOL, UWOP_SAVE_NONVOL_FAR):
            reg = REGS[c.info]
            if not any(m == "mov" and (mm := _SAVE_RE.search(o)) and mm.group(1) == reg
                       for (_, _, m, o) in insns):
                return "mismatch", f"no save of {reg} in prologue"
        elif c.op in (UWOP_SAVE_XMM128, UWOP_SAVE_XMM128_FAR):
            reg = f"xmm{c.info}"
            if not any(m in ("movaps", "movdqa", "movups", "vmovaps", "vmovdqa")
                       and (mm := _XMM_RE.search(o)) and mm.group(1) == reg
                       for (_, _, m, o) in insns):
                return "mismatch", f"no save of {reg} in prologue"
    return "verified", f"{len(codes)} unwind codes agree with on-disk prologue"
