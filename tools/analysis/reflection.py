"""Recover UE4.20 reflection registration data: names for native functions and their classes.

Sources (plaintext .rdata of the original file plus code references in the validated
decrypted image):

* FNameNativePtrPair arrays {const char* NameUTF8; FNativeFuncPtr Pointer;}, one per class,
  built by UHT in StaticRegisterNatives<Class>(). Each pairs a UFunction name with its exec
  thunk (<Class>::exec<Name>).
  A thunk with nothing to do after P_FINISH but a tail call is a leaf function without a
  .pdata entry. Such an entry is accepted when its pointer is to code starting with
  P_FINISH's load of Stack.Code; otherwise it would split the array and hide its start.
* FClassFunctionLinkInfo arrays {UFunction* (*CreateFuncPtr)(); const char* FuncNameUTF8;},
  which pair every UFunction (including events and delegate signatures) with its
  Z_Construct_UFunction_<Class>_<Name> creator.

The two layouts interleave the same two pointer kinds, so one kind of array read at an
8-byte offset looks like the other with one entry fewer. Each run is assigned the reading
with the longer run.

Class attribution, all through RIP-relative LEA references in the decrypted code:
  native array <- StaticRegisterNatives<Class> (the function containing the LEA)
  StaticRegisterNatives<Class> <- GetPrivateStaticClass, which also takes
  TEXT("<Class>") + 1, i.e. a LEA to a wide string + 2.
Function-link arrays are attributed when their creators' common prefix names a class seen
above, or left unattributed.

Usage: python tools/analysis/reflection.py      -> analysis/reflection-natives.json
Publishes names and RVAs only.
"""
from __future__ import annotations

import bisect
import json
import re
import struct
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "matching"))
from compare import load_decrypted  # noqa: E402
from pe import PEImage  # noqa: E402

IDENT = re.compile(rb"[A-Za-z_][A-Za-z0-9_]{0,200}\x00")
LEAF_THUNK = re.compile(rb"[\x48\x4c]\x8b[\x42\x4a\x52\x5a\x62\x6a\x72\x7a]\x20")
OUT = ROOT / "analysis" / "reflection-natives.json"


def main() -> int:
    img = PEImage()
    dimg = load_decrypted(img)
    if dimg is None:
        print("needs the validated decrypted image (tools/matching/ingest_dump.py)", file=sys.stderr)
        return 1
    base = img.image_base
    text = img.sections[0]
    rfs = sorted((rf.begin, rf.end) for rf in img.runtime_functions() if text.contains_rva(rf.begin))
    begins = [b for b, _ in rfs]
    starts = set(begins)
    rd = next(s for s in img.sections if s.name == ".rdata")
    lo = rd.rva
    hi = img.directory(0)[0] + img.directory(0)[1]   # validated linker extent end
    data = img.read(lo, hi - lo)

    name_cache: dict[int, str | None] = {}

    def ident_at(rva: int) -> str | None:
        if rva in name_cache:
            return name_cache[rva]
        res = None
        if lo <= rva < hi:
            m = IDENT.match(data, rva - lo)
            if m:
                res = m.group(0)[:-1].decode()
        name_cache[rva] = res
        return res

    def ptr(off: int) -> int | None:
        v = struct.unpack_from("<Q", data, off)[0]
        return v - base if base <= v < base + img.size_of_image else None

    # Candidate pairs at every 8-byte position: (name, func) and (func, name).
    nf, fn = {}, {}
    for off in range(0, len(data) - 16, 8):
        a, b = ptr(off), ptr(off + 8)
        if a is None or b is None:
            continue
        # Exec thunks may be leaf functions (P_FINISH then a tail call) without a .pdata
        # entry. Such a thunk reads no parameter (that would call FFrame::Step), so it starts
        # with P_FINISH's load of Stack.Code: mov r64, [rdx+0x20].
        if (b in starts or (text.contains_rva(b) and LEAF_THUNK.match(dimg.read(b, 4)))) and ident_at(a):
            nf[off] = (ident_at(a), b)
        if a in starts and ident_at(b):
            fn[off] = (a, ident_at(b))

    def runs(cands: dict) -> list[list[int]]:
        out, cur = [], []
        for off in sorted(cands):
            if cur and off == cur[-1] + 16:
                cur.append(off)
            else:
                if cur:
                    out.append(cur)
                cur = [off]
        if cur:
            out.append(cur)
        return out

    native_runs, link_runs = runs(nf), runs(fn)

    def keep(own: list[list[int]], other: list[list[int]]) -> list[list[int]]:
        # An array of one kind read 8 bytes off looks like the other kind, one entry shorter,
        # or in fragments where a leaf exec thunk is not a .pdata start. A run is kept only
        # when it is longer than every run of the other kind overlapping its shifted reading.
        length = {o: len(r) for r in other for o in r}
        out = []
        for r in own:
            shadow = max((length.get(o + d, 0) for o in r for d in (-8, 8)), default=0)
            if len(r) > shadow:
                out.append(r)
        return out

    natives, links = keep(native_runs, link_runs), keep(link_runs, native_runs)

    # RIP-relative LEA index over the decrypted main .text: target -> [site RVA].
    code = dimg.read(text.rva, text.rawsize)
    lea_sites: dict[int, list[int]] = defaultdict(list)
    for m in re.finditer(rb"[\x48\x4c]\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d]", code):
        p = m.start()
        if p + 7 <= len(code):
            tgt = text.rva + p + 7 + struct.unpack_from("<i", code, p + 3)[0]
            lea_sites[tgt].append(text.rva + p)

    def owner(rva: int) -> int | None:
        j = bisect.bisect_right(begins, rva) - 1
        return begins[j] if j >= 0 and rfs[j][0] <= rva < rfs[j][1] else None

    def wide_at(rva: int) -> str | None:
        if not (lo <= rva < hi):
            return None
        m = re.match(rb"((?:[A-Za-z0-9_]\x00){2,200})\x00\x00", data[rva - lo:rva - lo + 404])
        return m.group(1).decode("utf-16le") if m else None

    classes = []
    for r in natives:
        arr = lo + r[0]
        regs = {owner(s) for s in lea_sites.get(arr, [])} - {None}
        entry = {
            "array_rva": f"0x{arr:08X}",
            "functions": [{"name": nf[o][0], "exec_rva": f"0x{nf[o][1]:08X}"} for o in r],
            "static_register_natives_rva": None, "get_private_static_class_rva": None,
            "class": None, "evidence": None,
        }
        if len(regs) == 1:
            reg = next(iter(regs))
            entry["static_register_natives_rva"] = f"0x{reg:08X}"
            gpscs = {owner(s) for s in lea_sites.get(reg, [])} - {None}
            names = set()
            if len(gpscs) == 1:
                g = next(iter(gpscs))
                entry["get_private_static_class_rva"] = f"0x{g:08X}"
                # wide string literal referenced as TEXT("UClass") + 1 inside that function
                gend = rfs[bisect.bisect_right(begins, g) - 1][1]
                body = dimg.read(g, gend - g)
                for m in re.finditer(rb"[\x48\x4c]\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d]", body):
                    p = m.start()
                    if p + 7 > len(body):
                        continue
                    tgt = g + p + 7 + struct.unpack_from("<i", body, p + 3)[0]
                    w = wide_at(tgt - 2)
                    if w and w[0] in "UAFI" and len(w) > 1:
                        names.add(w)
                if len(names) == 1:
                    entry["class"] = names.pop()
                    entry["evidence"] = ("array referenced only by StaticRegisterNatives, whose address is "
                                         "referenced only by GetPrivateStaticClass, which passes "
                                         "TEXT(\"<class>\") + 1")
        classes.append(entry)

    def class_from_gpsc(g: int) -> str | None:
        j = bisect.bisect_right(begins, g) - 1
        if j < 0 or rfs[j][0] != g:
            return None
        body = dimg.read(g, rfs[j][1] - g)
        names = set()
        for m in re.finditer(rb"[\x48\x4c]\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d]", body):
            p = m.start()
            if p + 7 <= len(body):
                w = wide_at(g + p + 7 + struct.unpack_from("<i", body, p + 3)[0] - 2)
                if w and w[0] in "UAFI" and len(w) > 1:
                    names.add(w)
        return names.pop() if len(names) == 1 else None

    # FClassParams {ClassNoRegisterFunc, DependencySingletons, Num, ClassFlags, FunctionLinkArray, ...}:
    # find the record whose +0x18 points at the link array; ClassNoRegisterFunc is the
    # StaticClass thunk, a `jmp GetPrivateStaticClass`.
    link_refs: dict[int, list[int]] = defaultdict(list)
    link_vas = {base + lo + r[0] for r in links}
    for sec in img.sections:
        if sec.name not in (".rdata", ".data"):
            continue
        blob = img.data[sec.raw:sec.raw + sec.rawsize]
        for off in range(0, len(blob) - 8, 8):
            v = struct.unpack_from("<Q", blob, off)[0]
            if v in link_vas:
                link_refs[v - base].append(sec.rva + off)

    link_arrays = []
    for r in links:
        arr = lo + r[0]
        entry = {
            "array_rva": f"0x{arr:08X}",
            "class_params_rva": None, "static_class_rva": None, "get_private_static_class_rva": None,
            "class": None,
            "functions": [{"name": fn[o][1], "construct_rva": f"0x{fn[o][0]:08X}"} for o in r],
        }
        refs = link_refs.get(arr, [])
        if len(refs) == 1:
            rec = refs[0] - 0x18
            entry["class_params_rva"] = f"0x{rec:08X}"
            sc = struct.unpack("<Q", img.read(rec, 8))[0] - base
            code5 = dimg.read(sc, 5)
            if code5[0] == 0xE9:
                g = sc + 5 + struct.unpack_from("<i", code5, 1)[0]
                entry["static_class_rva"] = f"0x{sc:08X}"
                entry["get_private_static_class_rva"] = f"0x{g:08X}"
                entry["class"] = class_from_gpsc(g)
        link_arrays.append(entry)

    named_execs = sum(len(c["functions"]) for c in classes)
    named = {int(f["exec_rva"], 16) for c in classes for f in c["functions"]}
    named |= {int(c[k], 16) for c in classes if c["class"]
              for k in ("static_register_natives_rva", "get_private_static_class_rva")}
    named |= {int(f["construct_rva"], 16) for a in link_arrays for f in a["functions"]}
    out = {
        "schema_version": 1,
        "generated_by": "tools/analysis/reflection.py",
        "reference_sha256": img.sha256(),
        "summary": {
            "native_arrays": len(classes),
            "native_functions": named_execs,
            "native_arrays_with_class": sum(1 for c in classes if c["class"]),
            "function_link_arrays": len(link_arrays),
            "function_link_arrays_with_class": sum(1 for a in link_arrays if a["class"]),
            "function_link_entries": sum(len(a["functions"]) for a in link_arrays),
            "distinct_exec_rvas": len({f["exec_rva"] for c in classes for f in c["functions"]}),
            "distinct_construct_rvas": len({f["construct_rva"] for a in link_arrays for f in a["functions"]}),
            "distinct_named_function_rvas": len(named),
        },
        "native_classes": classes,
        "function_link_arrays": link_arrays,
    }
    OUT.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
