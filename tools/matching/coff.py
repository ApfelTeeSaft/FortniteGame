"""Extract relocation-free x64 COFF code using its own runtime-function extent."""

from struct import Struct


HEADER = Struct("<HHIIIHH")
SECTION = Struct("<8sIIIIIIHHI")
SYMBOL = Struct("<8sIhHBB")
RELOCATION = Struct("<IIH")
RUNTIME_FUNCTION = Struct("<III")
IMAGE_REL_AMD64_ADDR32NB = 3


def read_range(data, offset, size):
    if not 0 <= offset <= offset + size <= len(data):
        raise ValueError("Truncated COFF range")
    return data[offset:offset + size]


def funclet_code(path, symbol_name):
    return funclet_bytes(path.read_bytes(), symbol_name)


def funclet_bytes(data, symbol_name):
    machine, section_count, _, symbols_at, symbol_count, optional, _ = HEADER.unpack(
        read_range(data, 0, HEADER.size)
    )
    if machine != 0x8664 or optional or not symbols_at or not symbol_count:
        raise ValueError("Expected a standard AMD64 COFF object with symbols")
    read_range(data, HEADER.size, section_count * SECTION.size)
    read_range(data, symbols_at, symbol_count * SYMBOL.size)
    strings_at = symbols_at + symbol_count * SYMBOL.size
    strings_size = int.from_bytes(read_range(data, strings_at, 4), "little")
    strings = read_range(data, strings_at, strings_size)

    symbols = {}
    index = 0
    while index < symbol_count:
        name, value, section, _, _, aux = SYMBOL.unpack_from(data, symbols_at + index * SYMBOL.size)
        if name[:4] == bytes(4):
            offset = int.from_bytes(name[4:], "little")
            end = strings.find(b"\0", offset)
            if offset < 4 or end < 0:
                raise ValueError("Invalid COFF symbol name offset")
            name = strings[offset:end]
        else:
            name = name.rstrip(b"\0")
        symbols[index] = (name, value, section)
        index += aux + 1
    if index != symbol_count:
        raise ValueError("Incomplete auxiliary symbol records")

    def symbol_for(name):
        hits = [(index, value, section) for index, (n, value, section) in symbols.items()
                if n == name and 0 < section <= section_count]
        if len(hits) != 1:
            raise ValueError(f"Expected one defined symbol {name!r}")
        return hits[0]

    def section_data(number):
        name, _, _, raw_size, raw_at, reloc_at, _, reloc_count, _, flags = SECTION.unpack_from(
            data, HEADER.size + (number - 1) * SECTION.size,
        )
        if flags & 0x01000000:
            raise ValueError("COFF relocation overflow is unsupported")
        raw = read_range(data, raw_at, raw_size)
        relocations = read_range(data, reloc_at, reloc_count * RELOCATION.size)
        return name.rstrip(b"\0"), raw, list(RELOCATION.iter_unpack(relocations)), flags

    name = symbol_name.encode("ascii")
    code_index, code_start, code_section = symbol_for(name)
    unwind_index, _, _ = symbol_for(b"$unwind$" + name)
    _, pdata_at, pdata_section = symbol_for(b"$pdata$" + name)
    section_name, pdata, relocations, _ = section_data(pdata_section)
    if section_name != b".pdata":
        raise ValueError("Runtime-function record is not in .pdata")
    begin, end, unwind = RUNTIME_FUNCTION.unpack(read_range(pdata, pdata_at, RUNTIME_FUNCTION.size))
    expected = [
        (pdata_at, code_index, IMAGE_REL_AMD64_ADDR32NB),
        (pdata_at + 4, code_index, IMAGE_REL_AMD64_ADDR32NB),
        (pdata_at + 8, unwind_index, IMAGE_REL_AMD64_ADDR32NB),
    ]
    within_record = [row for row in relocations if pdata_at <= row[0] < pdata_at + 12]
    if sorted(within_record) != expected or begin != 0 or unwind != 0 or end <= begin:
        raise ValueError("Runtime-function record does not define the named funclet")

    _, code, relocations, flags = section_data(code_section)
    size = end - begin
    if not (flags & 0x20000000) or relocations:
        raise ValueError("Expected executable COFF code with no relocations in its section")
    return read_range(code, code_start, size)
