"""Read AMD64 runtime-function ranges and corroborate integer stack prologues."""

from dataclasses import dataclass
from struct import Struct

from capstone.x86_const import X86_OP_IMM, X86_OP_MEM, X86_OP_REG, X86_REG_RSP

from tools.matching.pe import code_at, file_range


RUNTIME_FUNCTION = Struct("<III")
UWOP_PUSH_NONVOL = 0
UWOP_ALLOC_LARGE = 1
UWOP_ALLOC_SMALL = 2
UWOP_SET_FPREG = 3
UWOP_SAVE_NONVOL = 4
UWOP_SAVE_NONVOL_FAR = 5
NONVOLATILE = {
    3: "rbx", 5: "rbp", 6: "rsi", 7: "rdi",
    12: "r12", 13: "r13", 14: "r14", 15: "r15",
}


@dataclass(frozen=True)
class Prologue:
    size: int
    frame_register: str | None
    frame_offset: int
    operations: dict


def runtime_entries(image):
    directories = image.OPTIONAL_HEADER.DATA_DIRECTORY
    if len(directories) < 4 or not directories[3].Size:
        return []
    directory = directories[3]
    if not directory.VirtualAddress or directory.VirtualAddress % 4:
        raise ValueError("Misaligned exception directory")
    if directory.Size % RUNTIME_FUNCTION.size:
        raise ValueError("Incomplete exception directory entry")
    _, raw = file_range(image, directory.VirtualAddress, directory.Size)
    return list(RUNTIME_FUNCTION.iter_unpack(raw))


def read_prologue(image, entry):
    """Parse the supported version-1 operations without inferring missing slots."""
    start, end, unwind_rva = entry
    if not 0 < start < end or not unwind_rva or unwind_rva % 4:
        return None
    try:
        _, header = file_range(image, unwind_rva, 4)
        version_flags, size, slots, frame = header
        if version_flags != 1 or not slots or not 0 < size < end - start:
            return None
        _, codes = file_range(image, unwind_rva + 4, (slots + slots % 2) * 2)
    except ValueError:
        return None
    frame_register = NONVOLATILE.get(frame & 0xF)
    if frame and frame_register is None:
        return None
    frame_offset = (frame >> 4) * 16
    operations = {}
    previous = size
    slot = 0
    while slot < slots:
        offset, encoded = codes[2 * slot:2 * slot + 2]
        if not 0 < offset <= previous:
            return None
        previous = offset
        kind, info = encoded & 0xF, encoded >> 4
        slot += 1
        if kind == UWOP_ALLOC_SMALL:
            operations.setdefault(offset, []).append(("allocate", info * 8 + 8))
            continue
        if kind == UWOP_SET_FPREG and info == 0 and frame_register:
            operations.setdefault(offset, []).append(("frame", frame_register, frame_offset))
            continue

        register = NONVOLATILE.get(info)
        if kind == UWOP_PUSH_NONVOL and register:
            operations.setdefault(offset, []).append(("push", register))
            continue
        if kind == UWOP_ALLOC_LARGE and info in (0, 1):
            extra_slots, scale = (1, 8) if info == 0 else (2, 1)
        elif kind in (UWOP_SAVE_NONVOL, UWOP_SAVE_NONVOL_FAR) and register:
            extra_slots, scale = (1, 8) if kind == UWOP_SAVE_NONVOL else (2, 1)
        else:
            return None
        if slot + extra_slots > slots:
            return None
        value = int.from_bytes(codes[slot * 2:(slot + extra_slots) * 2], "little") * scale
        slot += extra_slots
        if value % 8 or (kind == UWOP_ALLOC_LARGE and not value):
            return None
        operations.setdefault(offset, []).append(
            ("allocate", value) if kind == UWOP_ALLOC_LARGE else ("save", register, value)
        )

    frame_count = sum(op[0] == "frame" for group in operations.values() for op in group)
    if frame_count != bool(frame_register):
        return None
    return Prologue(size, frame_register, frame_offset, operations)


def instruction_operation(instruction, frame_base, frame_offset, remaining_stack):
    operands = instruction.operands
    name = instruction.mnemonic
    if name == "push" and operands[0].type == X86_OP_REG:
        return ("push", instruction.reg_name(operands[0].reg))
    if len(operands) != 2:
        return None
    dest, source = operands
    if name == "sub" and dest.type == X86_OP_REG and dest.reg == X86_REG_RSP:
        if source.type == X86_OP_IMM:
            return ("allocate", source.imm)
    if name == "mov" and dest.type == X86_OP_MEM and source.type == X86_OP_REG:
        address = dest.mem
        if dest.size == 8 and not (address.index or address.segment):
            register = instruction.reg_name(source.reg)
            base = instruction.reg_name(address.base)
            if base == "rsp":
                return ("save", register, address.disp + remaining_stack)
            if frame_base and base == frame_base:
                return ("save", register, address.disp + frame_offset)
    if dest.type == X86_OP_REG and dest.reg != X86_REG_RSP:
        register = instruction.reg_name(dest.reg)
        if name == "mov" and source.type == X86_OP_REG and source.reg == X86_REG_RSP:
            return ("frame", register, remaining_stack)
        if name == "lea" and source.type == X86_OP_MEM:
            address = source.mem
            if address.base == X86_REG_RSP and not (address.index or address.segment):
                return ("frame", register, address.disp + remaining_stack)
    return None


def prologue_matches(decoder, data, prologue):
    annotated_offsets = set()
    saves = {}
    for offset, operations in prologue.operations.items():
        for op in operations:
            if op[0] == "save":
                if op in saves:
                    return False
                saves[op] = offset
    decoded_size = 0
    frame_base = None
    remaining_stack = sum(
        8 if op[0] == "push" else op[1]
        for group in prologue.operations.values()
        for op in group
        if op[0] in {"push", "allocate"}
    )
    for instruction in decoder.disasm(data[:prologue.size], 0):
        decoded_size = instruction.address + instruction.size
        actual = instruction_operation(
            instruction, frame_base, prologue.frame_offset, remaining_stack
        )
        if decoded_size in prologue.operations:
            annotated_offsets.add(decoded_size)
        expected = [op for op in prologue.operations.get(decoded_size, ()) if op[0] != "save"]
        if expected:
            if expected != [actual] or instruction.operands[0].size != 8:
                return False
            if actual[0] == "frame":
                frame_base = prologue.frame_register
            elif actual[0] == "push":
                remaining_stack -= 8
            elif actual[0] == "allocate":
                remaining_stack -= actual[1]
        elif actual and actual[0] == "save" and actual[1] in NONVOLATILE.values():
            # MSVC may record a save at the end of the prologue even when the
            # store precedes the stack allocation. The stack slot must agree.
            declared_offset = saves.pop(actual, 0)
            if decoded_size > declared_offset:
                return False
        else:
            # Argument homes, register moves and instruction padding can appear
            # between annotated operations. An unrecorded stack change cannot.
            _, written = instruction.regs_access()
            if instruction.mnemonic not in {"mov", "lea", "nop"} or any(
                instruction.reg_name(reg) in {"rsp", "esp", "sp", "spl"} for reg in written
            ):
                return False
            if actual and actual[0] == "frame" and actual[1] == prologue.frame_register:
                return False
    return (
        decoded_size == prologue.size
        and not saves
        and annotated_offsets == prologue.operations.keys()
    )


def checked_runtime_range(image, entries, start, decoder):
    matching = [entry for entry in entries if entry[0] == start]
    if len(matching) != 1:
        raise ValueError(f"Expected one runtime-function record at RVA {start:#x}")
    entry = matching[0]
    _, end, unwind_rva = entry
    prologue = read_prologue(image, entry)
    if prologue is None:
        raise ValueError(f"Unsupported or invalid unwind prologue at RVA {start:#x}")
    if any(
        first < end and start < last and first < last and first != start
        for first, last, _ in entries
    ):
        raise ValueError(f"Overlapping runtime-function ranges at RVA {start:#x}")
    _, data = code_at(image, start, end - start)
    if not prologue_matches(decoder, data, prologue):
        raise ValueError(f"Code disagrees with unwind prologue at RVA {start:#x}")
    return end, unwind_rva
