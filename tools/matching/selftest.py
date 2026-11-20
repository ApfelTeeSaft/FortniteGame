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
    print("unwind: ok")


def run(*args: str) -> None:
    r = subprocess.run([sys.executable, *args], cwd=REPO_ROOT, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode:
        sys.stderr.write(r.stderr)
        raise SystemExit(f"FAILED: {' '.join(args)}")


def main() -> int:
    test_unwind()
    if not DEFAULT_REFERENCE.exists():
        print("reference EXE not present: skipping manifest verification")
        return 0
    run(str(HERE / "compare.py"), "--build", "--check")
    run(str(REPO_ROOT / "tools" / "progress" / "generate.py"), "--verify")
    print("selftest: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
