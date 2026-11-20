"""Regression tests for the matching tools.

Part 1 needs nothing proprietary: synthetic unwind records and prologues.
Part 2 runs only when the reference EXE and built objects are present. It
re-verifies the manifest (compare.py --check) and the progress image
(generate.py --verify).

Usage: python tools/matching/selftest.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pe import DEFAULT_REFERENCE, REPO_ROOT  # noqa: E402
from unwind import parse_unwind, verify_prologue  # noqa: E402


class FakeImage:
    def __init__(self, blobs: dict[int, bytes]):
        self.blobs = blobs

    def read(self, rva: int, n: int) -> bytes:
        for base, b in self.blobs.items():
            if base <= rva and rva + n <= base + len(b):
                return b[rva - base:rva - base + n]
        raise ValueError("unmapped")

    def u32(self, rva: int) -> int:
        return int.from_bytes(self.read(rva, 4), "little")


def test_unwind() -> None:
    # push rbp; sub rsp,0x20; mov rbp,rdx  (a funclet prologue)
    code = bytes.fromhex("4055 4883ec20 488bea") + b"\xcc" * 8
    # UNWIND_INFO v1, no flags, prolog 6, 2 codes: (6, ALLOC_SMALL 0x20), (2, PUSH_NONVOL rbp)
    ui = bytes([0x01, 0x06, 0x02, 0x00, 0x06, 0x32, 0x02, 0x50])
    img = FakeImage({0x1000: code, 0x2000: ui})
    info = parse_unwind(img, 0x2000)
    assert [c.op for c in info.codes] == [2, 0] and info.codes[0].value == 0x20
    assert verify_prologue(img, 0x1000, info)[0] == "verified"
    # Same record against random bytes must not verify.
    img2 = FakeImage({0x1000: bytes.fromhex("d6a76744 5edd0c47 6662"), 0x2000: ui})
    assert verify_prologue(img2, 0x1000, info)[0] != "verified"
    # Wrong allocation size must be reported as a mismatch.
    img3 = FakeImage({0x1000: bytes.fromhex("4055 4883ec28 488bea"), 0x2000: ui})
    assert verify_prologue(img3, 0x1000, info)[0] == "mismatch"
    # mov [rsp+8],rbx; push rdi; sub rsp,0x20 -- small decimal displacement in capstone output
    code4 = bytes.fromhex("48895c2408 57 4883ec20")
    ui4 = bytes([0x01, 0x0A, 0x04, 0x00, 0x0A, 0x34, 0x06, 0x00, 0x0A, 0x32, 0x06, 0x70])
    img4 = FakeImage({0x1000: code4, 0x2000: ui4})
    assert verify_prologue(img4, 0x1000, parse_unwind(img4, 0x2000))[0] == "verified"
    print("unwind: ok")


def test_literals() -> None:
    from symbols_auto import _string_literal
    wide = "d3ddebug".encode("utf-16le") + b"\0\0" + b"\0" * 6
    assert _string_literal(wide) == "d3ddebug".encode("utf-16le") + b"\0\0"
    assert _string_literal(b"abc\0\0\0\0\0") == b"abc\0"
    assert _string_literal(bytes.fromhex("78ae0a776ff2ba4d")) is None  # GUID bytes are not a literal
    from symbols_auto import literal_hits
    w = "Entry".encode("utf-16le") + b"\0\0"
    hay = b"idx\0" + w + b"\0\0" + w + "Big".encode("utf-16le") + w
    # After a narrow string, after wide NULs, and as a suffix of a wide string: all three count.
    assert literal_hits(w, hay, 0x1000) == [0x1004, 0x1012, 0x1024], literal_hits(w, hay, 0x1000)
    assert literal_hits(b"dx\0", b"\0idx\0\0dx\0", 0) == [6]  # a narrow suffix is not a start
    print("literals: ok")


def run(*args: str) -> None:
    r = subprocess.run([sys.executable, *args], cwd=REPO_ROOT, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode:
        sys.stderr.write(r.stderr)
        raise SystemExit(f"FAILED: {' '.join(args)}")


def test_leave_one_out() -> None:
    from compare import Resolver
    r = Resolver.__new__(Resolver)
    # symbol key -> {observed RVA: {observing manifest entries}}
    r.observations = {"?F@@YAXXZ": {0x1000: {1}}, "?G@@YAXXZ": {0x2000: {1}, 0x3000: {2}}}
    r.entry_names = {1: "A", 2: "B"}
    assert r._observed("?F@@YAXXZ", exclude=1)[0] == set()                # never self-corroborated
    assert r._observed("?F@@YAXXZ", exclude=2)[0] == {0x1000}
    assert r._observed("?G@@YAXXZ", exclude=None)[0] == {0x2000, 0x3000}  # conflict is visible
    assert r._observed("?G@@YAXXZ", exclude=2)[0] == {0x2000}             # leave-one-out drops B
    print("leave-one-out: ok")


def test_literal_elimination() -> None:
    """A literal with N copies resolves only when the other N-1 are used by other functions."""
    from types import SimpleNamespace as NS
    from compare import Resolver
    lit = "Entry".encode("utf-16le") + b"\0\0"
    sym = NS(name="$SG1", section=1, value=0, storage=3)
    obj = NS(symbols=[sym], sections=[NS(name=".rdata", data=lit, chars=0x40000040, relocs=[])],
             symbol=lambda name: sym if name == "$SG1" else None, data_layout=lambda: {})
    r = Resolver.__new__(Resolver)
    r.functions, r.known, r.data_cache, r.data_notes = {}, {}, {}, {}
    r.hay_rva, r.hay = 0x1000, b"\0\0" + lit + b"\0\0" + lit + b"\0\0" + lit
    copies = [0x1002, 0x1010, 0x101E]
    r.entry_names, r.observations = {1: "A", 2: "B", 3: "T"}, {}
    r.by_addr = {copies[0]: {"$SGx": {1}}}
    assert r.resolve(obj, "o", "$SG1", exclude=3) == []                  # two copies still free
    r.by_addr[copies[2]] = {"??_C@lit": {2}}
    got = r.resolve(obj, "o", "$SG1", exclude=3)
    assert [g[0] for g in got] == [copies[1]] and "elimination" in got[0][1], got
    assert r.resolve(obj, "o", "$SG1", exclude=2) == []                  # B's own copy is not evidence for B
    print("literal elimination: ok")


def main() -> int:
    test_unwind()
    test_literals()
    test_leave_one_out()
    test_literal_elimination()
    if not DEFAULT_REFERENCE.exists():
        print("reference EXE not present: skipping manifest verification")
        return 0
    run(str(HERE / "compare.py"), "--build", "--check", "--quiet")
    run(str(REPO_ROOT / "tools" / "progress" / "generate.py"), "--verify")
    print("selftest: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
