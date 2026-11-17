"""Read file-backed executable ranges by RVA, without virtual zero fill."""

from hashlib import file_digest, sha256
from pathlib import Path

import pefile


REFERENCE = Path("2.5/2.5/FortniteGame/Binaries/Win64/FortniteClient-Win64-Shipping.exe")


def file_hash(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def open_image(path):
    image = pefile.PE(str(path), fast_load=True)
    if image.FILE_HEADER.Machine != 0x8664 or image.OPTIONAL_HEADER.Magic != 0x20B:
        image.close()
        raise ValueError(f"{path.name} is not an AMD64 PE32+ image")
    return image


def code_at(image, start, size):
    return file_range(image, start, size, executable=True)


def file_range(image, start, size, *, executable=False):
    if size <= 0:
        raise ValueError("RVA range size must be positive")
    for section in image.sections:
        displacement = start - section.VirtualAddress
        if executable and not (section.Characteristics & 0x20000000):
            continue
        if 0 <= displacement and displacement + size <= min(
            section.SizeOfRawData, section.Misc_VirtualSize
        ):
            offset = section.PointerToRawData + displacement
            data = image.__data__[offset:offset + size]
            if len(data) == size:
                return offset, data
    kind = "executable range" if executable else "range"
    raise ValueError(f"RVA {start:#x} + {size:#x} is not a file-backed {kind}")


def digest(data):
    return sha256(data).hexdigest()
