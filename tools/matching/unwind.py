"""Read AMD64 runtime-function ranges and validate simple stack prologues."""

from struct import Struct

from tools.matching.pe import code_at, file_range


RUNTIME_FUNCTION = Struct("<III")
UWOP_ALLOC_SMALL = 2


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


def small_stack_prologue(image, entry):
    """Return the expected prologue for a single version-1 UWOP_ALLOC_SMALL."""
    start, end, unwind_rva = entry
    if not 0 < start < end or not unwind_rva or unwind_rva % 4:
        return None
    try:
        _, info = file_range(image, unwind_rva, 8)
    except ValueError:
        return None
    version_flags, length, slots, frame, code_offset, operation = info[:6]
    if (version_flags, slots, frame) != (1, 1, 0):
        return None
    if not 0 < length < end - start or code_offset != length or operation & 0xf != UWOP_ALLOC_SMALL:
        return None
    stack_size = (operation >> 4) * 8 + 8
    if length == 4 and stack_size < 128:
        return bytes((0x48, 0x83, 0xec, stack_size))
    if length == 7:
        return b"\x48\x81\xec" + stack_size.to_bytes(4, "little")
    return None


def checked_runtime_range(image, entries, start):
    matching = [entry for entry in entries if entry[0] == start]
    if len(matching) != 1:
        raise ValueError(f"Expected one runtime-function record at RVA {start:#x}")
    entry = matching[0]
    _, end, unwind_rva = entry
    expected_prologue = small_stack_prologue(image, entry)
    if expected_prologue is None:
        raise ValueError(f"Unsupported or invalid unwind prologue at RVA {start:#x}")
    if any(
        first < end and start < last and first < last and first != start
        for first, last, _ in entries
    ):
        raise ValueError(f"Overlapping runtime-function ranges at RVA {start:#x}")
    _, data = code_at(image, start, end - start)
    if not data.startswith(expected_prologue):
        raise ValueError(f"Code disagrees with unwind prologue at RVA {start:#x}")
    return end, unwind_rva
