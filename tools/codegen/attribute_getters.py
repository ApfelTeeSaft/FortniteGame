"""Generate GameplayAbilities attribute getters (GAMEPLAYATTRIBUTE_PROPERTY_GETTER) from the image.

Each attribute set class declares, per attribute, an inline static getter that caches the
property in a thread-safe static and returns it as an FGameplayAttribute:

    static FGameplayAttribute Get<Property>Attribute()
    {
        static UProperty* Prop = FindFieldChecked<UProperty>(<Class>::StaticClass(), FName(TEXT("<Property>")));
        return Prop;
    }

The reference keeps one out-of-line copy of each instance (COMDAT). They are located by their
162-byte shape (that of RVA 0x00C26F50 with every call, rip-relative and immediate displacement
masked). The class comes from the GetPrivateStaticClass they call (StaticClass() inlined), the
property from the wide literal they pass to FName. Each class's getters are emitted in one unit,
in the order of the properties' offsets (their declaration order). The offsets are read from the
class's FClassParams property array (analysis/uht-creator-symbols.json locates the record), never
from the getters' .bss statics, which are the fields the comparison checks.

Inputs: the decrypted image, analysis/functions-uht-gpsc.json (GetPrivateStaticClass RVAs by class),
analysis/uht-creator-symbols.json (FClassParams records).
Outputs: FortniteGameCode/Source/Generated/AttributeGetters/<Class>.gen.cpp and
analysis/functions-attribute-getters.json. Publishes names and RVAs only.
"""
from __future__ import annotations

import json
import re
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "matching"))
sys.path.insert(0, str(ROOT / "tools" / "codegen"))
import capstone  # noqa: E402
from compare import load_decrypted  # noqa: E402
from genio import sync_tree  # noqa: E402
from manifest_io import dump_compact, expand  # noqa: E402
from pe import PEImage  # noqa: E402

OUT_DIR = ROOT / "FortniteGameCode" / "Source" / "Generated" / "AttributeGetters"
MANIFEST = ROOT / "analysis" / "functions-attribute-getters.json"
TEMPLATE_RVA = 0x00C26F50          # UFortDamageSet::GetOutgoingBaseDamageAttribute
TEMPLATE_SIZE = 162
CLASSPARAMS = "?ClassParams@Z_Construct_UClass_{}_Statics@@2UFClassParams@UE4CodeGen_Private@@B"
PROPS_OFF, NPROPS_OFF = 0x28, 0x30  # FClassParams: PropertyArray, NumProperties
REC_NAME, REC_OFFSET = 0x08, 0x30   # FStructPropertyParams: NameUTF8, Offset (after Type)


def main() -> int:
    img = PEImage()
    dimg = load_decrypted(img)
    if dimg is None:
        print("needs the validated decrypted image (tools/matching/ingest_dump.py)", file=sys.stderr)
        return 1
    base = img.image_base
    text = img.sections[0]
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True

    def masked(rva: int, n: int):
        out, fields = bytearray(), []
        for ins in md.disasm(dimg.read(rva, n), rva):
            bs = bytearray(ins.bytes)
            if ins.mnemonic in ("call", "jmp") and len(bs) == 5:
                fields.append(("call", int(ins.op_str, 16)))
                bs[1:5] = b"\0" * 4
            elif "rip" in ins.op_str and ins.disp_offset:
                m = re.search(r"rip ([+-]) (0x[0-9a-f]+)", ins.op_str)
                t = ins.address + ins.size + (int(m.group(2), 16) if m.group(1) == "+" else -int(m.group(2), 16))
                fields.append((ins.mnemonic, t))
                bs[ins.disp_offset:ins.disp_offset + 4] = b"\0" * 4
            out += bs
        return bytes(out), fields

    template, _ = masked(TEMPLATE_RVA, TEMPLATE_SIZE)
    gpsc_class = {int(e["start_rva"], 16): e["class"]
                  for e in expand(json.loads((ROOT / "analysis" / "functions-uht-gpsc.json").read_text(encoding="utf-8")))}
    creator_syms = json.loads((ROOT / "analysis" / "uht-creator-symbols.json").read_text(encoding="utf-8"))["symbols"]
    stats = Counter()

    getters = defaultdict(list)   # class -> [(rva, end, property)]
    for rf in img.runtime_functions():
        if rf.end - rf.begin != TEMPLATE_SIZE or not text.contains_rva(rf.begin):
            continue
        shape, fields = masked(rf.begin, TEMPLATE_SIZE)
        if shape != template:
            continue
        calls = [t for k, t in fields if k == "call"]
        cls = gpsc_class.get(calls[2])   # FGameplayAttribute ctor, header, GetPrivateStaticClass, FName, FindField, footer
        lits = [t for k, t in fields if k == "lea" and img.section_of(t) and img.section_of(t).name == ".rdata"]
        if cls is None or len(lits) != 1:
            stats["shape matched, class or literal not identified"] += 1
            continue
        prop = img.read(lits[0], 256).decode("utf-16le", "replace").split("\0")[0]
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", prop):
            stats["literal not an identifier"] += 1
            continue
        getters[cls].append((rf.begin, rf.end, prop))
        stats["getters"] += 1

    def ptr(rva: int) -> int:
        return struct.unpack("<Q", img.read(rva, 8))[0] - base

    files, entries = {}, []
    for cls in sorted(getters):
        rec = creator_syms.get(CLASSPARAMS.format(cls))
        if rec is None:
            stats["class skipped: FClassParams not located"] += 1
            continue
        cp = int(rec[0], 16)
        props, nprops = ptr(cp + PROPS_OFF), struct.unpack("<i", img.read(cp + NPROPS_OFF, 4))[0]
        offset = {}
        for k in range(nprops):
            p = ptr(props + 8 * k)
            name = img.read(ptr(p + REC_NAME), 256).split(b"\0")[0].decode("latin1")
            offset[name] = struct.unpack("<i", img.read(p + REC_OFFSET, 4))[0]
        mine = [g for g in getters[cls] if g[2] in offset]
        stats["getters without their class's property"] += len(getters[cls]) - len(mine)
        mine.sort(key=lambda g: offset[g[2]])
        stats["classes"] += 1
        decls = " \\\n".join(f"\tstatic FGameplayAttribute Get{p}Attribute();" for _, _, p in mine)
        body = [
            "// Generated by tools/codegen/attribute_getters.py from FortniteClient-Win64-Shipping.exe",
            "// (++Fortnite+Release-2.5-CL-3889387). Do not edit by hand.",
            f"// {cls}'s GameplayAbilities attribute getters (GAMEPLAYATTRIBUTE_PROPERTY_GETTER), in the order of",
            "// their properties' offsets in the class's FClassParams property array (declaration order).",
            "// UStruct is UClass's primary base; the shims declare the two unrelated, so the upcast the",
            "// original makes implicitly is spelled out (it does not change the code).",
            "",
            f"#define FNGC_EXTRA_MEMBERS_{cls} \\",
            decls,
            "",
            '#include "FortniteGameCode/UHTRecovered.h"',
            '#include "FortniteGameCode/RecoveryHarness.h"',
            "",
        ]
        for rva, end, p in mine:
            body += [
                f"// Original FortniteClient-Win64-Shipping.exe: RVA 0x{rva:08X} (end 0x{end:08X})",
                f"// Original VA: 0x{base + rva:016X} | File offset: 0x{img.rva_to_off(rva):08X}",
                f"// Recovery: high-confidence inferred (attribute getter of {cls}::{p}, offset 0x{offset[p]:X}) | Matching: see analysis/functions-attribute-getters.json",
                f"inline FGameplayAttribute {cls}::Get{p}Attribute()",
                "{",
                f"\tstatic UProperty* Prop = FindFieldChecked<UProperty>((const UStruct*){cls}::StaticClass(), FName(TEXT(\"{p}\")));",
                "\treturn Prop;",
                "}",
                "",
            ]
            entries.append({"start_rva": f"0x{rva:08X}", "end_rva": f"0x{end:08X}", "name": f"{cls}::Get{p}Attribute",
                            "class": cls, "property": p,
                            "symbol": f"?Get{p}Attribute@{cls}@@SA?AUFGameplayAttribute@@XZ"})
        body += ["#if FNGC_MATCHING_HARNESS",
                 f"FNGC_ANCHOR_TABLE(GFngcAnchors_{cls}_AttributeGetters)",
                 "{"]
        body += [f"\t(const void*)&{cls}::Get{p}Attribute," for _, _, p in mine]
        body += ["};", "#endif", ""]
        files[OUT_DIR / f"{cls}.gen.cpp"] = "\r\n".join(body)

    written, removed = sync_tree(OUT_DIR, files)
    entries.sort(key=lambda e: e["start_rva"])
    old = {}
    if MANIFEST.exists():
        for e in expand(json.loads(MANIFEST.read_text(encoding="utf-8"))):
            old[e["start_rva"]] = e
    for e in entries:   # keep the comparison's results until compare.py rewrites them
        for k in ("match", "candidate_sha256", "byte_diff", "reference_state"):
            if k in old.get(e["start_rva"], {}):
                e[k] = old[e["start_rva"]][k]
    manifest = {
        "schema_version": 1,
        "generated_by": "tools/codegen/attribute_getters.py",
        "evidence": "GAMEPLAYATTRIBUTE_PROPERTY_GETTER instances: the 162-byte shape of RVA 0x00C26F50 (displacements masked); "
                    "class from the GetPrivateStaticClass called, property from the FName literal, order from the property "
                    "offsets in the class's FClassParams.",
        "entry_defaults": {"category": "attribute-getter", "in_denominator": True, "name_confidence": "high-confidence inferred",
                           "source": "FortniteGameCode/Source/Generated/AttributeGetters/{class}.gen.cpp",
                           "object": "Source/Generated/AttributeGetters/{class}.gen.obj", "module": "FortniteGame"},
        "functions": entries,
    }
    from manifest_io import strip
    strip(manifest)
    dump_compact(MANIFEST, manifest)
    stats["files written"], stats["files removed"] = written, removed
    print(dict(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
