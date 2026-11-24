"""Compare recovered functions with the reference image and record verified results.

For every analysis/functions.json entry that names an object file and symbol:

* raw bytes of the compiled function are compared with the reference bytes over the
  manifest range [start_rva, end_rva). A relocation field counts only when its symbol
  resolves through evidence independent of the bytes under test. Allowed sources are
  analysis/symbols.json, import tables, unique import thunks, unique data content
  (symbols_auto.py), or another function already matched exactly (iterated to a fixpoint).
  Unresolved fields are never treated as equal; a function that matches apart from them is
  ``relocation-equivalent``, not ``exact``;
* reference bytes come from the original file where they are plaintext on disk. Otherwise
  they come from the validated decrypted image (ingest_dump.py, local only), giving
  reference_state ``decrypted``. Without either, encrypted bodies are ``unknown``;
* the compiled unwind record and C scope table are compared with the reference
  records in plaintext .rdata. Scope entries are compared as offsets from the
  function start, and the handler RVA is reported, never assumed.

Usage:
  python tools/matching/compare.py [--build] [--check]
    --build   rebuild FortniteGameCode.sln (ClientShipping|x64) first
    --check   do not write; exit 1 if the manifest's recorded results are stale
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import manifest_io  # noqa: E402
import symbols_auto  # noqa: E402
from coff import REL_FIELD_SIZE, CoffObject  # noqa: E402
from dump import DecryptedImage  # noqa: E402
from pe import REPO_ROOT, PEImage  # noqa: E402
from unwind import UNW_FLAG_CHAININFO, parse_unwind, verify_prologue  # noqa: E402

MANIFEST = REPO_ROOT / "analysis" / "functions.json"
# Bulk manifests produced by generators (e.g. tools/codegen/uht_creators.py) share the denominator.
EXTRA_MANIFESTS = "functions-*.json"
SYMBOLS = REPO_ROOT / "analysis" / "symbols.json"
# Generated symbol evidence: {symbol: {rva, evidence}} files written by analysis/codegen tools.
# Literal elimination needs every copy enumerated; content with this many copies is skipped.
ELIMINATION_LIMIT = 4096
FOLD_LIMIT = 16   # longest relocation-free leaf body treated as ICF-folded (bytes)
GENERATED_SYMBOLS = ("uht-creator-symbols.json", "uht-struct-symbols.json", "uht-enum-symbols.json",
                     "uht-class-symbols.json", "uht-package-symbols.json")
SOLUTION = REPO_ROOT / "FortniteGameCode" / "FortniteGameCode.sln"
OBJ_ROOT = REPO_ROOT / "FortniteGameCode" / "Build" / "ClientShipping" / "obj"
DECRYPTED_REPORT = REPO_ROOT / "analysis" / "decrypted-reference.json"
DECRYPTED_IMAGE = REPO_ROOT / "local-output" / "reference-dump" / "FortniteClient-Win64-Shipping.decrypted.image"
DECRYPTED_PRESENT = DECRYPTED_IMAGE.with_suffix(".present")
COMPUTED = ("in_denominator", "reference_state", "match", "original_sha256", "decrypted_sha256",
            "candidate_sha256", "byte_diff", "structure", "compiler", "compare_note")
DECRYPTED_STATES = ("decrypted", "decrypted-unverified")


def hx(v: int) -> str:
    return f"0x{v:08X}"


def comp_id(obj: CoffObject) -> str | None:
    for s in obj.symbols:
        if s is not None and s.name == "@comp.id":
            return f"prodid {s.value >> 16} build {s.value & 0xFFFF}"
    return None


def load_decrypted(img: PEImage) -> DecryptedImage | None:
    if not DECRYPTED_REPORT.exists() or not DECRYPTED_IMAGE.exists():
        return None
    report = json.loads(DECRYPTED_REPORT.read_text(encoding="utf-8"))
    data = DECRYPTED_IMAGE.read_bytes()
    if (not report["validation"]["accepted"]
            or hashlib.sha256(data).hexdigest() != report["normalized_image"]["sha256"]):
        print("decrypted image not validated or hash mismatch; ignoring it", file=sys.stderr)
        return None
    present = DECRYPTED_PRESENT.read_bytes() if DECRYPTED_PRESENT.exists() else None
    return DecryptedImage(img, data, present)


class Resolver:
    """Symbol -> reference RVA, each with the evidence that established it."""

    def __init__(self, img: PEImage, dimg, manual: dict[str, tuple[int, str]]):
        self.known: dict[str, list[tuple[int, str]]] = {k: [v] for k, v in manual.items()}
        for k, lst in symbols_auto.build(img, dimg).items():
            self.known.setdefault(k, [(x["rva"], x["evidence"]) for x in lst])
        self.functions: dict[str, tuple[int, str]] = {}
        self.data_cache: dict[tuple[str, str], list[tuple[int, str]]] = {}
        self.data_notes: dict[tuple[str, str], str] = {}
        lo = symbols_auto._iat_rdata_extent(img)[1]
        exp_rva, exp_size = img.directory(0)
        self.hay_rva, self.hay = lo, img.read(lo, exp_rva + exp_size - lo)
        # Leave-one-out observations: symbol key -> {observed RVA: {manifest entry indices}},
        # and the same indexed by address: RVA -> {symbol key: {manifest entry indices}}.
        self.observations: dict = {}
        self.by_addr: dict = {}
        self._literal_copies: dict[bytes, list[int]] = {}
        self._groups: dict = {}
        # Per pass (reset with the observations): literal copies nobody observes, and the
        # addresses each entry observed.
        self._unobserved: dict = {}
        self._literal_copy_sets: dict = {}
        self.entry_addrs: dict = {}
        self.entry_names: dict[int, str] = {}
        self.entry_ranges: dict[int, tuple[int, int]] = {}   # reference RVA range per entry
        self.blocks: dict[str, dict] = {}
        self._name_index = None
        # ICF: (section name, body) of a relocation-free COMDAT function -> {address: entries}.
        self.folded_obs: dict = {}
        self._code_groups: dict = {}
        self._xrefs = None
        self._sg_ranges = None
        self.img, self.dimg = img, dimg

    @staticmethod
    def key(obj: CoffObject, objpath: str, symbol: str):
        """Internal-linkage symbols are only meaningful inside their own object file."""
        s = obj.symbol(symbol)
        return (objpath, symbol) if s is not None and s.storage == 3 else symbol

    def _observed(self, key, exclude: int | None) -> tuple[set[int], str]:
        vals, who, n = set(), [], 0
        for val, ents in self.observations.get(key, {}).items():
            others = ents - {exclude} if exclude in ents else ents
            if others:
                vals.add(val)
                n += len(others)
                if len(who) < 2:
                    who.extend(sorted(self.entry_names.get(i, str(i)) for i in list(others)[:2]))
        desc = ", ".join(who[:2]) + (f" and {n - len(who[:2])} more" if n > len(who[:2]) else "")
        return vals, desc

    def resolve(self, obj: CoffObject, objpath: str, symbol: str,
                exclude: int | None = None) -> list[tuple[int, str]]:
        """All independently evidenced reference addresses of `symbol` (usually one).

        `exclude` is the manifest entry under test. Observations made in that entry are
        never used to resolve its own fields.
        """
        if symbol in self.functions:
            return [self.functions[symbol]]
        if symbol in self.known:
            return self.known[symbol]
        dkey = (objpath, symbol)
        if dkey not in self.data_cache:
            rva, why = symbols_auto.resolve_data_symbol(obj, symbol, self.hay, self.hay_rva)
            self.data_cache[dkey] = [(rva, f"data symbol: {why}")] if rva is not None else []
            self.data_notes[dkey] = why
        if self.data_cache[dkey]:
            return self.data_cache[dkey]
        # Same symbol observed at one address by other relocation-equivalent-or-better functions.
        mykey = self.key(obj, objpath, symbol)
        vals, who = self._observed(mykey, exclude)
        if len(vals) == 1:
            return [(next(iter(vals)), "corroborated: same symbol at this address in " + who)]
        if len(vals) > 1:
            return []
        # ICF-folded body (leave-one-out). /OPT:ICF gives identical COMDAT functions one address,
        # so a relocation-free leaf body identifies its function as well as a name does: other
        # entries' observations of any function with the same body give its address.
        fb = self._folded_body(obj, symbol)
        if fb is not None:
            fvals, fwho = self._observed_folded(fb, exclude)
            if len(fvals) == 1:
                return [(next(iter(fvals)), f"ICF-folded body ({fb[1].hex()}): observed at this address in {fwho}")]
            if len(fvals) > 1:
                return []
        run = self._internal_constructor_run(obj, objpath, symbol, exclude)
        if run is not None:
            return run
        # Literal elimination (leave-one-out). Without /GF each use of a literal has its own
        # copy. If every copy but one is the observed target of a *different* symbol in other
        # relocation-equivalent-or-better functions, the remaining copy is this symbol's.
        lit = symbols_auto.literal_content(obj, symbol)
        if lit is not None:
            hits = self._literal_copies.get(lit)
            if hits is None:   # depends only on the content, so it is computed once
                hits = self._literal_copies[lit] = symbols_auto.literal_hits(
                    lit, self.hay, self.hay_rva, limit=ELIMINATION_LIMIT)
            if 1 < len(hits) < ELIMINATION_LIMIT:
                # A copy is free for this symbol unless a different symbol is observed there by an
                # entry other than the one under test. Copies nobody observes are free for every
                # query and are cached per pass; only copies observed under this symbol's key or by
                # the entry under test need checking per query.
                unobserved = self._unobserved.get(lit)
                if unobserved is None:
                    unobserved = self._unobserved[lit] = [h for h in hits if not self.by_addr.get(h)]
                # A copy no entry observes belongs to some other function. Two kinds of evidence
                # say whose, without the entry under test:
                # - exactly one `lea` outside the entry under test references it, so it is that
                #   code's copy. A copy referenced from several places is pooled (an inline
                #   function's COMDAT literal, such as StaticPackage()'s) and claims nothing;
                # - it lies inside another object's main .rdata, the span between two literals
                #   ($SG) that entries of that object observe. An object's literals are one
                #   contiguous section, so a copy there is not this object's;
                # - for the same reason, a literal another object's entries observe lies between
                #   it and this object's own observed literals (other entries' observations only).
                free = [h for h in unobserved
                        if not self._referenced_by_code(h, exclude)
                        and not self._inside_other_object(h, objpath)
                        and not self._beyond_own_block(h, objpath, exclude)]
                if len(free) <= 1:   # with two or more unobserved copies elimination cannot conclude
                    hitset = self._literal_copy_sets.setdefault(lit, set(hits))
                    check = set(self.observations.get(mykey, {})) | self.entry_addrs.get(exclude, set())
                    for h in sorted(check & hitset):
                        if h in unobserved:
                            continue
                        if not any(k != mykey and ents - {exclude} for k, ents in self.by_addr.get(h, {}).items()):
                            free.append(h)
                if len(free) == 1:
                    users = [self.entry_names.get(i, str(i)) for h in hits[:4] if h != free[0]
                             for k, ents in self.by_addr.get(h, {}).items() if k != mykey
                             for i in sorted(ents - {exclude})[:1]]
                    return [(free[0], f"literal elimination: {len(hits)} copies, the others used by "
                                      + ", ".join(users[:2]) + (f" and {len(hits) - 3} more" if len(hits) > 3 else ""))]
        # A declared block's members (StaticEnum singletons) come in an order of MSVC's own, often a
        # rotation of the source order, which the layout does not reproduce; their extent it
        # does. So slot elimination goes first for them, and section-relative is the fallback.
        if symbol in getattr(self, "blocks", {}):
            hit = self._slot_elimination(symbol, exclude)
            if hit:
                return hit
        # Section-relative: neighbours in the object's data layout (same section name, sections
        # in object order), observed by other functions. Local first: the nearest observed
        # neighbour on each side gives that side's prediction. If the two sides agree, or only
        # one side has an observed neighbour, that prediction is used; a gap in the layout model
        # elsewhere in a large unit then cannot outvote the immediate neighbours. If the sides
        # disagree (a gap next to the symbol), the prediction supported by the most neighbours
        # is used if it strictly outnumbers every alternative. The byte comparison decides, and
        # a failed prediction is reported as unresolved.
        sym = obj.symbol(symbol)
        if sym is None or sym.section <= 0:
            return self._slot_elimination(symbol, exclude)
        items, index = self._layout_group(obj, objpath, obj.sections[sym.section - 1].name)
        i = index.get(symbol)
        if i is None:
            return self._slot_elimination(symbol, exclude)
        mine = items[i][0]

        def observed_pred(j: int):
            off, name = items[j]
            if ("@GlobalVectorConstants@@" in name) != ("@GlobalVectorConstants@@" in symbol):
                # A unit's header constants sit in its plain .bss after UnityPrologue.h, a
                # stand-in whose size differs from the engine headers' statics: their offsets to
                # the unit's other statics are not modelled. Constants predict only each other;
                # their observations still count as occupied slots (_slot_elimination).
                return None
            ovals, owho = self._observed(self.key(obj, objpath, name), exclude)
            if len(ovals) == 1:
                return off, next(iter(ovals)) + mine - off, f"{name} (seen in {owho})"
            return None

        nearest, nearest_at = [], []
        for step in (-1, 1):
            j = i + step
            while 0 <= j < len(items):
                n = observed_pred(j)
                if n is not None:
                    nearest.append(n)
                    nearest_at.append(j)
                    break
                j += step
        local = local_prediction(mine, nearest)
        if local is not None:
            pred, basis = local
            extra = f" and {len(basis) - 1} more neighbours" if len(basis) > 1 else ""
            return [(pred, "section-relative (local) to " + basis[0] + extra)]
        bracket = self._record_bracket(symbol, exclude)
        if bracket:
            return bracket
        if len(nearest) < 2:
            return self._slot_elimination(symbol, exclude)
        # The sides disagree. A side whose neighbour is the symbol's rigid partner, directly
        # next to it in the layout, decides (rigid_successor).
        (_, lpred, ldesc), (_, rpred, rdesc) = nearest
        if nearest_at[0] == i - 1 and rigid_successor(items[i - 1][1], symbol):
            return [(lpred, "section-relative (rigid pair) to " + ldesc + " (the other side disagrees)")]
        if nearest_at[1] == i + 1 and rigid_successor(symbol, items[i + 1][1]):
            return [(rpred, "section-relative (rigid pair) to " + rdesc + " (the other side disagrees)")]
        # The sides disagree: a gap next to the symbol. Each side's run is the observed
        # neighbours that agree with its nearest one, up to the first that does not. The
        # strictly longer run's prediction is used; that side holds more of the symbol's own
        # contiguous block. Equal runs resolve nothing.
        runs = []
        for step, (_, first, desc) in zip((-1, 1), nearest):
            count, j = 0, i + step
            while 0 <= j < len(items):
                n = observed_pred(j)
                if n is not None:
                    if n[1] != first:
                        break
                    count += 1
                j += step
            runs.append((count, first, desc))
        (lc, lp, ld), (rc, rp, rd) = runs
        if lc == rc:
            return self._slot_elimination(symbol, exclude)
        count, pred, desc = max(runs)
        extra = f" and {count - 1} more neighbours" if count > 1 else ""
        return [(pred, "section-relative (longer run) to " + desc + extra + f" ({min(lc, rc)} dissenting)")]

    @staticmethod
    def _folded_body(obj: CoffObject, symbol: str) -> tuple[str, bytes] | None:
        """(section name, bytes) of a function that is a whole relocation-free COMDAT section of
        at most FOLD_LIMIT bytes, such as `return nullptr` or an empty function; else None."""
        index = getattr(obj, "function_index", None)
        hit = index().get(symbol) if index is not None else None
        if hit is None:
            return None
        start, end, sec = hit
        if not sec.chars & 0x20 or not sec.chars & 0x1000 or start != 0 or end != len(sec.data):
            return None
        if sec.relocs or not 0 < end <= FOLD_LIMIT:
            return None
        return sec.name, bytes(sec.data)

    def _observed_folded(self, fb, exclude: int | None) -> tuple[set[int], str]:
        vals, who, n = set(), [], 0
        for val, ents in getattr(self, "folded_obs", {}).get(fb, {}).items():
            others = ents - {exclude}
            if others:
                vals.add(val)
                n += len(others)
                if len(who) < 2:
                    who.extend(sorted(self.entry_names.get(i, str(i)) for i in list(others)[:2]))
        desc = ", ".join(who[:2]) + (f" and {n - len(who[:2])} more" if n > len(who[:2]) else "")
        return vals, desc

    def _internal_constructor_run(self, obj: CoffObject, objpath: str, symbol: str,
                                  exclude: int | None) -> list[tuple[int, str]] | None:
        """InternalConstructor<C> from the instances next to it in its unit's run (leave-one-out).

        Both compilers emit a unit's instances in first use order, that is, in the order of the
        object's GetPrivateStaticClass sections, each 16-byte aligned. Every run member's
        address comes from other entries' observations. A member's slot is its compiled size,
        or for an instance declared only here (an inlined constructor) the extent of the
        reference function at its observed address. A member is folded when another instance
        is observed at its address (ICF merges identical constructors' instances); its slot
        here is occupied only if that address is exactly where the walk has arrived.

        Each side walks from its nearest unfolded member to the symbol. With both sides, they
        must agree. With one side only (a run end, or the other side blocked), the reference at
        the prediction must hold this instance's compiled body outside its relocation, and no
        other symbol may be observed there."""
        if not symbol.startswith("??$InternalConstructor@"):
            return None
        groups = getattr(self, "_code_groups", None)
        if groups is None:
            groups = self._code_groups = {}
        g = groups.get(objpath)
        if g is None:
            first = {}
            for sym, sec in obj.functions():
                first.setdefault(sec.index, sym.name)
            items, bodies = [], {}
            for sec in obj.sections:
                if not sec.chars & 0x20 or sec.index not in first:
                    continue
                name = first[sec.index]
                if name.startswith("?GetPrivateStaticClass@"):
                    ic = next((r.symbol for r in sec.relocs if r.symbol.startswith("??$InternalConstructor@")), None)
                    if ic is not None and ic not in items:
                        items.append(ic)
                elif name.startswith("??$InternalConstructor@"):
                    bodies[name] = (bytes(sec.data), [r.offset for r in sec.relocs])
            g = groups[objpath] = (items, {n: k for k, n in enumerate(items)}, bodies)
        items, index, bodies = g
        i = index.get(symbol)
        if i is None:
            return None
        if getattr(self, "_rf_end", None) is None:
            img = getattr(self, "img", None)
            self._rf_end = {r.begin: r.end for r in img.runtime_functions()} if img is not None else {}

        def addr(f):
            vals, _ = self._observed(f, exclude)
            return next(iter(vals)) if len(vals) == 1 else None

        def folded(f, a):
            return any(k != f and isinstance(k, str) and k.startswith("??$InternalConstructor@") and ents - {exclude}
                       for k, ents in self.by_addr.get(a, {}).items())

        def slot(f, a):
            if f in bodies:
                return (len(bodies[f][0]) + 15) & ~15
            if a is not None and a in self._rf_end:
                return ((self._rf_end[a] + 15) & ~15) - a
            return None

        preds = {}
        j = i - 1
        while j >= 0 and addr(items[j]) is not None and folded(items[j], addr(items[j])):
            j -= 1
        if j >= 0 and addr(items[j]) is not None:
            a = addr(items[j])
            s = slot(items[j], a)
            cur = a + s if s else None
            for k in range(j + 1, i):
                af = addr(items[k])
                if cur is None or af is None:
                    cur = None
                    break
                if af == cur:
                    s = slot(items[k], af)
                    cur = cur + s if s else None
            if cur is not None:
                preds["left"] = (cur, items[j])
        j = i + 1
        while j < len(items) and addr(items[j]) is not None and folded(items[j], addr(items[j])):
            j += 1
        if j < len(items) and addr(items[j]) is not None:
            cur = addr(items[j])
            for k in range(j - 1, i, -1):
                af = addr(items[k])
                s = slot(items[k], af) if af is not None else None
                if s is None:
                    cur = None
                    break
                if af + s == cur:
                    cur = af
            mine = slot(symbol, preds["left"][0] if "left" in preds else None)
            if cur is not None and mine:
                preds["right"] = (cur - mine, items[j])
        if "left" in preds and "right" in preds:
            if preds["left"][0] != preds["right"][0]:
                return None
            return [(preds["left"][0], f"code layout (InternalConstructor run in GetPrivateStaticClass order) "
                                       f"between {preds['left'][1]} and {preds['right'][1]}")]
        if len(preds) != 1 or symbol not in bodies or getattr(self, "dimg", None) is None:
            return None
        side, (p, anchor) = next(iter(preds.items()))
        body, rels = bodies[symbol]
        ref = self.dimg.read(p, len(body))
        masked = {o + d for o in rels for d in range(4)}
        if any(body[k] != ref[k] for k in range(len(body)) if k not in masked):
            return None
        if any(ents - {exclude} for k, ents in self.by_addr.get(p, {}).items() if k != symbol):
            return None
        return [(p, f"code layout (InternalConstructor run, {side} side only, from {anchor}); "
                    "the reference holds this instance's body there")]

    def _referenced_by_code(self, addr: int, exclude: int | None = None) -> bool:
        """Whether exactly one `lea reg, [rip+disp]` in the reference's .text, outside the entry
        under test, targets `addr` or the same literal one character in (TEXT("C") + 1).
        Leave-one-out: the entry's own range is masked, never read. Two or more sites mean a
        pooled copy, which may be the entry's too."""
        if getattr(self, "img", None) is None:
            return False
        if getattr(self, "_xrefs", None) is None:
            import re as _re
            text = self.img.sections[0]
            code = self.dimg.read(text.rva, text.vsize) if self.dimg is not None else b""
            xr: dict = {}
            def _cls(bs):  # a regex class of the given bytes, each escaped
                return b"[" + b"".join(_re.escape(bytes([x])) for x in bs) + b"]"
            pat = _cls([0x48, 0x4C]) + _re.escape(bytes([0x8D])) + _cls([0x05, 0x0D, 0x15, 0x1D, 0x25, 0x2D, 0x35, 0x3D])
            for m in _re.finditer(pat, code):
                i = m.start()
                tgt = text.rva + i + 7 + int.from_bytes(code[i + 3:i + 7], "little", signed=True)
                xr.setdefault(tgt, []).append(text.rva + i)
            self._xrefs = xr
        lo, hi = getattr(self, "entry_ranges", {}).get(exclude, (0, 0))
        sites = [x for x in self._xrefs.get(addr, []) + self._xrefs.get(addr + 2, []) if not lo <= x < hi]
        return len(sites) == 1

    def _inside_other_object(self, addr: int, objpath: str) -> bool:
        """Whether `addr` lies strictly between two string literals ($SG) of one other object, as
        observed by that object's entries (its main .rdata is one contiguous section)."""
        if getattr(self, "_sg_ranges", None) is None:
            spans: dict = {}
            for k in self.observations:
                if isinstance(k, tuple) and k[1].startswith("$SG"):
                    for v in self.observations[k]:
                        lo, hi = spans.get(k[0], (v, v))
                        spans[k[0]] = (min(lo, v), max(hi, v))
            self._sg_ranges = spans
        return any(lo < addr < hi for p, (lo, hi) in self._sg_ranges.items() if p != objpath)

    def _beyond_own_block(self, addr: int, objpath: str, exclude: int | None) -> bool:
        """Whether a string literal ($SG) of another object, observed by its entries, lies
        between `addr` and the span of this object's literals that entries other than the one
        under test observe. One object's literals are contiguous, so `addr` is then not in it."""
        if getattr(self, "_sg_sorted", None) is None:
            allobs, own = [], {}
            for k, d in self.observations.items():
                if isinstance(k, tuple) and k[1].startswith("$SG"):
                    for v, ents in d.items():
                        allobs.append((v, k[0]))
                        own.setdefault(k[0], []).append((v, ents))
            allobs.sort()
            for lst in own.values():
                lst.sort(key=lambda t: t[0])
            self._sg_sorted, self._sg_own = allobs, own
            self._sg_addrs = [v for v, _ in allobs]
        mine = self._sg_own.get(objpath, [])
        lo = next((v for v, ents in mine if ents - {exclude}), None)
        if lo is None:
            return False
        hi = next(v for v, ents in reversed(mine) if ents - {exclude})
        if lo <= addr <= hi:
            return False
        a, b = (addr, lo) if addr < lo else (hi, addr)
        import bisect as _bisect
        i = _bisect.bisect_right(self._sg_addrs, a)
        while i < len(self._sg_sorted) and self._sg_sorted[i][0] < b:
            if self._sg_sorted[i][1] != objpath:
                return True
            i += 1
        return False

    def _slot_elimination(self, symbol: str, exclude: int | None) -> list[tuple[int, str]]:
        """A declared block of equal slots (analysis/uht-bss-blocks.json): a unit's StaticEnum
        singletons, the statics of its file-static functions. Every other member must be observed
        once, by entries other than the one under test. The symbol's slot is then the one they
        leave:
        1. the single one-slot gap between them that no other symbol is observed holding. A
           unit's singletons fill contiguous slots, so only the missing member can leave one;
        2. else an end of the symbol's own cluster. Members more than one slot apart start a new
           cluster: a unit whose singletons sit in several places (9 units). Each run (the
           .s<k> object of consecutive enums, numbered in source order) lies in one cluster,
           and the clusters are ascending ranges of runs. The symbol's cluster is that of its
           own run's other members, or of the runs on both sides (both clusters when those
           differ). Of those clusters' end slots that no other symbol is observed holding:
           - the lower end directly above an observed PrivateStaticClass, which closes a class's
             statics (the previous unit's last, or the class before the cluster's header). A
             cluster above one starts directly after it (76 of 76 measured);
           - else the only one.
        Anything else (two gaps, runs out of order, two or more candidates) resolves nothing.
        The byte comparison checks every prediction."""
        block = getattr(self, "blocks", {}).get(symbol)
        if not block:
            return []
        step, mates = block["slot"], []
        for m in block["symbols"]:
            if m == symbol:
                continue
            vals = self._observed_by_name(m, exclude)
            if len(vals) != 1:
                return []
            mates.append((next(iter(vals)), self._run_of(m)))
        mates.sort()
        a = [x for x, _ in mates]
        if not a or len(set(a)) != len(a) or any((y - x) % step for x, y in zip(a, a[1:])):
            return []
        where = f"{len(a)} other slots of {block['unit']}'s {len(block['symbols'])}-slot block"
        gaps = [x + step for x, y in zip(a, a[1:]) if y - x == 2 * step]
        if any(self._held_by_others(g, symbol, exclude) for g in gaps) or len(gaps) > 1:
            return []
        if gaps:
            return [(gaps[0], f"slot elimination: the gap between the {where}")]
        cluster, k = [], 0
        for i, x in enumerate(a):
            if i and x - a[i - 1] > step:
                k += 1
            cluster.append(k)
        if k == 0:
            mine = {0}
        else:
            runs: dict = {}
            for (_, run), c in zip(mates, cluster):
                if run is None or runs.setdefault(run, c) != c:
                    return []
            order = sorted(runs)
            if any(runs[x] > runs[y] for x, y in zip(order, order[1:])):
                return []
            run = self._run_of(symbol)
            below = [x for x in order if run is not None and x < run]
            above = [x for x in order if run is not None and x > run]
            if run in runs:
                mine = {runs[run]}
            elif below and above:
                mine = {runs[below[-1]], runs[above[0]]}
            else:
                return []
        cand = []
        for c in sorted(mine):
            ac = [x for x, cc in zip(a, cluster) if cc == c]
            for slot, lower in ((ac[0] - step, True), (ac[-1] + step, False)):
                if not self._held_by_others(slot, symbol, exclude):
                    cand.append((slot, lower))
        clusters = f" ({k + 1} clusters)" if k else ""
        after = [slot for slot, lower in cand if lower and self._private_static_class_at(slot - step, exclude)]
        if len(after) == 1:
            return [(after[0], f"slot elimination: the lower end, directly above a PrivateStaticClass, "
                               f"of the {where}{clusters}")]
        if after or len(cand) != 1:
            return []
        return [(cand[0][0], f"slot elimination: the free end of the {where}{clusters}")]

    def _run_of(self, member: str) -> int | None:
        """The run of a block member: k of the .s<k> object its StaticEnum is compiled in (runs
        are consecutive enums' records, numbered in source order by tools/codegen/uht_enums.py);
        0 for a unit's own object. None when the function is not known."""
        if "??" not in member or "@4" not in member:
            return None
        scope = member.split("??", 1)[1]
        objpath = getattr(self, "symbol_objects", {}).get("?" + scope[:scope.index("@4")])
        if objpath is None:
            return None
        m = re.search(r"\.s(\d+)\.gen\.obj$", objpath.replace("\\", "/"))
        return int(m.group(1)) if m else 0

    def _private_static_class_at(self, addr: int, exclude: int | None) -> bool:
        """Whether other entries observe exactly one symbol at `addr`, a class's PrivateStaticClass."""
        held = {k if isinstance(k, str) else k[1] for k, ents in self.by_addr.get(addr, {}).items() if ents - {exclude}}
        return len(held) == 1 and next(iter(held)).startswith("?PrivateStaticClass@")

    # Generated singletons with a parameter record in .data: (entry symbol suffix, record
    # symbol, static symbol), each formatted with the function's name.
    _RECORD_KINDS = (
        ("@@YAPEAVUFunction@@XZ", "?FuncParams@?4??{}@@YAPEAVUFunction@@XZ@4UFFunctionParams@UE4CodeGen_Private@@B",
         "?ReturnFunction@?1??{}@@YAPEAVUFunction@@XZ@4PEAV2@EA"),
        ("@@YAPEAVUEnum@@XZ", "?EnumParams@?4??{}@@YAPEAVUEnum@@XZ@4UFEnumParams@UE4CodeGen_Private@@B",
         "?ReturnEnum@?1??{}@@YAPEAVUEnum@@XZ@4PEAV2@EA"),
        ("@@YAPEAVUScriptStruct@@XZ",
         "?ReturnStructParams@?4??{}@@YAPEAVUScriptStruct@@XZ@4UFStructParams@UE4CodeGen_Private@@B",
         "?ReturnStruct@?1??{}@@YAPEAVUScriptStruct@@XZ@4PEAV2@EA"),
    )

    def _record_bracket(self, symbol: str, exclude: int | None) -> list[tuple[int, str]]:
        """A generated singleton's static (a creator's ReturnFunction, an enum's ReturnEnum, a
        struct's ReturnStruct) between the statics of the singletons whose parameter records
        (FFunctionParams, FEnumParams, FStructParams) directly precede and follow its own in its
        object.

        A singleton's record (.data) and its static (.bss) are function-local statics emitted
        together, so in the reference their orders agree, across all three kinds (203 of 203
        units). The static then lies strictly between the two neighbours' statics, which other
        entries observe. When exactly one 8-byte slot there is not observed holding a symbol by
        other entries, it is this one. Records come from analysis/uht-creator-symbols.json,
        uht-package-symbols.json, uht-enum-symbols.json and uht-struct-symbols.json (located
        by name); no .bss address of the singleton is read."""
        runs = getattr(self, "_record_runs", None)
        if runs is None:
            records = {}
            for f in ("uht-creator-symbols.json", "uht-package-symbols.json", "uht-enum-symbols.json",
                      "uht-struct-symbols.json"):
                p = REPO_ROOT / "analysis" / f
                if p.exists():
                    for k, v in json.loads(p.read_text(encoding="utf-8"))["symbols"].items():
                        records[k] = int(v[0], 16)
            by_obj: dict = {}
            for sym, objpath in getattr(self, "symbol_objects", {}).items():
                if not sym.startswith("?Z_Construct_U"):
                    continue
                for suffix, rec_t, static_t in self._RECORD_KINDS:
                    if sym.endswith(suffix):
                        name = sym[1:-len(suffix)]
                        rec = records.get(rec_t.format(name))
                        if rec is not None:
                            by_obj.setdefault(objpath, []).append((rec, static_t.format(name)))
                        break
            runs = {}
            for objpath, lst in by_obj.items():
                lst.sort()
                for i, (_, static) in enumerate(lst):
                    runs[static] = (lst[i - 1][1] if i else None, lst[i + 1][1] if i + 1 < len(lst) else None)
            self._record_runs = runs
        prev_next = runs.get(symbol)
        if not prev_next or None in prev_next:
            return []
        bounds = []
        for static in prev_next:
            vals = self._observed_by_name(static, exclude)
            if len(vals) != 1:
                return []
            bounds.append(next(iter(vals)))
        lo, hi = bounds
        free = [s for s in range(lo + 8, hi, 8)
                if not any(ents - {exclude} for ents in self.by_addr.get(s, {}).values())]
        if len(free) != 1:
            return []
        short = lambda st: st.split("??", 1)[1].split("@@", 1)[0]
        return [(free[0], f"record-bracketed slot: the one free slot between the statics of {short(prev_next[0])} "
                          f"and {short(prev_next[1])}, whose records bracket this one's")]

    def _observed_by_name(self, name: str, exclude: int | None) -> set[int]:
        if getattr(self, "_name_index", None) is None:
            self._name_index = defaultdict(list)
            for k in self.observations:
                self._name_index[k if isinstance(k, str) else k[1]].append(k)
        out = set()
        for k in self._name_index.get(name, []):
            for val, ents in self.observations[k].items():
                if ents - {exclude}:
                    out.add(val)
        return out

    def _held_by_others(self, addr: int, symbol: str, exclude: int | None) -> bool:
        """Whether entries other than the one under test observe a symbol other than `symbol` at `addr`."""
        for k, ents in self.by_addr.get(addr, {}).items():
            if (k if isinstance(k, str) else k[1]) != symbol and ents - {exclude}:
                return True
        return False

    def _layout_group(self, obj: CoffObject, objpath: str, secname: str):
        """([(offset, symbol)] sorted by offset, {symbol: index}) of one section group, cached."""
        k = (objpath, secname)
        g = self._groups.get(k)
        if g is None:
            items = sorted((off, name) for name, off, _ in obj.data_layout().get(secname, []))
            g = self._groups[k] = (items, {name: n for n, (_, name) in enumerate(items)})
        return g

    def observe(self, idx: int, obj: CoffObject, objpath: str, relocs, cand_raw: bytes, ref: bytes,
                start: int, image_base: int) -> None:
        """Record where each relocation of entry `idx` points in the reference."""
        for r in relocs:
            size = REL_FIELD_SIZE.get(r.kind)
            if not size or r.offset + size > len(ref):
                continue
            # The compiled field holds the addend; the reference field holds the linked value.
            addend = int.from_bytes(cand_raw[r.offset:r.offset + size], "little", signed=size == 4)
            val = int.from_bytes(ref[r.offset:r.offset + size], "little", signed=size == 4)
            if r.kind == "ADDR64":
                target = val - image_base - addend
            elif r.kind == "ADDR32NB":
                target = val - addend
            elif r.kind.startswith("REL32"):
                extra = 0 if r.kind == "REL32" else int(r.kind[-1])
                target = val + start + r.offset + 4 + extra - addend
            else:
                continue
            key = self.key(obj, objpath, r.symbol)
            self.observations.setdefault(key, {}).setdefault(target, set()).add(idx)
            fb = self._folded_body(obj, r.symbol)
            if fb is not None:
                self.folded_obs.setdefault(fb, {}).setdefault(target, set()).add(idx)
            self.by_addr.setdefault(target, {}).setdefault(key, set()).add(idx)
            self.entry_addrs.setdefault(idx, set()).add(target)


_OUTER_CLASS = re.compile(r"\?OuterClass@\?1\?\?Z_Construct_UClass_(\w+)@@YAPEAVUClass@@XZ@")


def rigid_successor(prev: str, nxt: str) -> bool:
    """Whether static `nxt` directly follows static `prev` in every reference unit's .bss:
    - a class's OuterClass, then its PrivateStaticClass (Z_Construct_UClass_C precedes C's
      IMPLEMENT_CLASS): 3,283 of 3,283 observed pairs;
    - a class's last creator's ReturnFunction, then its OuterClass (the creators precede the
      class constructor): 1,238 of 1,238.
    Used only to break a disagreement between the two sides of a section-relative prediction."""
    m = _OUTER_CLASS.match(prev)
    if m:
        return nxt.startswith(f"?PrivateStaticClass@?1??GetPrivateStaticClass@{m.group(1)}@@")
    m = _OUTER_CLASS.match(nxt)
    if m:
        c = re.escape(m.group(1))
        return re.match(rf"\?ReturnFunction@\?1\?\?Z_Construct_U(?:Delegate)?Function_{c}_", prev) is not None
    return False


def local_prediction(mine: int, neighbours: list[tuple[int, int, str]]) -> tuple[int, list[str]] | None:
    """Prediction from the agreeing runs of observed neighbours adjacent to offset `mine`.

    `neighbours` holds (layout offset, predicted address of the symbol, description). Each side's
    run starts at the nearest neighbour and continues while predictions agree. Returns None when
    there is no neighbour or when the two sides disagree.
    """
    def run(side):
        if not side:
            return None, []
        p, basis = side[0][1], []
        for _, q, desc in side:
            if q != p:
                break
            basis.append(desc)
        return p, basis

    lp, lb = run(sorted((n for n in neighbours if n[0] < mine), key=lambda n: -n[0]))
    rp, rb = run(sorted((n for n in neighbours if n[0] > mine), key=lambda n: n[0]))
    if lp is None and rp is None:
        return None
    if lp is None or rp is None:
        return (lp, lb) if rp is None else (rp, rb)
    return (lp, lb + rb) if lp == rp else None


def reference_state(img: PEImage, rf, ref: bytes, cand: bytes) -> str:
    if ref == cand:
        return "plaintext"
    if rf is None:
        return "unknown"
    verdict, _ = verify_prologue(img, rf.begin, parse_unwind(img, rf.unwind))
    return {"verified": "plaintext", "mismatch": "encrypted",
            "undecodable": "encrypted"}.get(verdict, "unknown")


def decrypted_state(dimg, rf, ref_file: bytes, ref_dec: bytes, cand: bytes) -> str:
    if ref_dec == cand:
        return "decrypted"
    if ref_dec == ref_file:
        return "encrypted"
    if rf is None:
        return "decrypted-unverified"
    verdict, _ = verify_prologue(dimg, rf.begin, parse_unwind(dimg.original, rf.unwind))
    return "decrypted" if verdict in ("verified", "no-codes") else "decrypted-unverified"


def _field_value(kind: str, target: int, addend: int, start: int, offset: int, image_base: int) -> int | None:
    if kind == "ADDR64":
        return image_base + target + addend
    if kind == "ADDR32NB":
        return target + addend
    if kind.startswith("REL32"):
        extra = 0 if kind == "REL32" else int(kind[-1])
        return target + addend - (start + offset + 4 + extra)
    return None


def resolve_fields(cand: bytes, relocs, start: int, image_base: int, resolver: Resolver,
                   obj: CoffObject, objpath: str, ref: bytes | None = None, exclude: int | None = None):
    """Apply resolvable relocations as the linker would at the original placement.

    When a symbol has several independently evidenced addresses (an import with both an
    original and a protector IAT slot), the one whose field equals the reference is used.
    The choice and its evidence are recorded. Any field that no candidate can produce stays
    a byte difference.
    """
    buf = bytearray(cand)
    unresolved, resolved = [], []
    for r in relocs:
        size = REL_FIELD_SIZE.get(r.kind)
        targets = resolver.resolve(obj, objpath, r.symbol, exclude) if size else []
        if not targets:
            unresolved.append((r.offset, size or 4, r.symbol, r.kind))
            continue
        addend = int.from_bytes(cand[r.offset:r.offset + size], "little", signed=size == 4)
        options = []
        for target, via in targets:
            val = _field_value(r.kind, target, addend, start, r.offset, image_base)
            if val is not None:
                options.append(((val & ((1 << (8 * size)) - 1)).to_bytes(size, "little"), target, via))
        if not options:
            unresolved.append((r.offset, size, r.symbol, r.kind))
            continue
        chosen = options[0]
        if ref is not None:
            chosen = next((o for o in options if o[0] == ref[r.offset:r.offset + size]), chosen)
            if chosen[0] != ref[r.offset:r.offset + size] and chosen[2].startswith("section-relative"):
                # A layout prediction that does not reproduce the reference is missing evidence,
                # not a code difference: report the field as unresolved.
                unresolved.append((r.offset, size, r.symbol, r.kind))
                continue
        buf[r.offset:r.offset + size] = chosen[0]
        resolved.append({"offset": hx(r.offset), "symbol": r.symbol, "rva": hx(chosen[1]), "evidence": chosen[2]})
    return bytes(buf), unresolved, resolved


def byte_diff(ref: bytes, cand: bytes, unresolved, resolved=()) -> dict:
    masked = set()
    for off, size, _, _ in unresolved:
        masked.update(range(off, off + size))
    n = min(len(ref), len(cand))
    diffs = [i for i in range(n) if ref[i] != cand[i] and i not in masked]
    masked_diff = [i for i in sorted(masked) if i < n and ref[i] != cand[i]]
    return {
        "reference_size": len(ref),
        "candidate_size": len(cand),
        "differing_bytes": len(diffs) + abs(len(ref) - len(cand)),
        "first_difference": hx(diffs[0]) if diffs else None,
        "resolved_relocations": list(resolved),
        "unresolved_relocations": [
            {"offset": hx(o), "size": s, "symbol": sym, "kind": k} for o, s, sym, k in unresolved],
        "bytes_differing_only_in_unresolved_fields": len(masked_diff),
    }


def classify(state: str, diff: dict) -> str:
    if state in ("encrypted", "unknown"):
        return "unknown"
    same_size = diff["reference_size"] == diff["candidate_size"]
    if same_size and diff["differing_bytes"] == 0:
        return "exact" if not diff["unresolved_relocations"] else "relocation-equivalent"
    return "partial" if diff["differing_bytes"] < diff["reference_size"] else "unmatched"


def obj_unwind(obj: CoffObject, symbol: str):
    """Locate the compiled UNWIND_INFO for `symbol` via the object's .pdata relocations."""
    for sec in obj.sections:
        if sec.name != ".pdata":
            continue
        by_off = {r.offset: r for r in sec.relocs}
        for base in range(0, len(sec.data), 12):
            r0, r8 = by_off.get(base), by_off.get(base + 8)
            if r0 is None or r8 is None or r0.symbol != symbol:
                continue
            for sym in obj.symbols:
                if sym is not None and sym.name == r8.symbol and sym.section > 0:
                    xsec = obj.sections[sym.section - 1]
                    add = struct.unpack_from("<I", sec.data, base + 8)[0]
                    return xsec, sym.value + add
    return None


def compare_structure(img: PEImage, rf, obj: CoffObject, symbol: str, start: int,
                      funclet_rvas: dict[str, int]) -> dict | None:
    loc = obj_unwind(obj, symbol)
    if loc is None or rf is None:
        return None
    xsec, xoff = loc
    d = xsec.data
    count = d[xoff + 2]
    hdr_len = 4 + 2 * count
    ref_ui = img.read(rf.unwind, hdr_len)
    # pdata_size_matches is filled in by the caller, which knows the candidate size.
    out = {"pdata_size_matches": None, "unwind_codes_identical": d[xoff:xoff + hdr_len] == ref_ui}
    flags = d[xoff] >> 3
    tail = xoff + 4 + 2 * (count + (count & 1))
    if flags & UNW_FLAG_CHAININFO or not flags & 3:
        return out
    rel = {r.offset: r for r in xsec.relocs}
    ref_tail = rf.unwind + 4 + 2 * (count + (count & 1))
    hsym = rel.get(tail)
    out["handler"] = {"candidate_symbol": hsym.symbol if hsym else None,
                      "reference_rva": hx(img.u32(ref_tail)),
                      "status": "unresolved-relocation (reported, not compared)"}
    if hsym is None or hsym.symbol not in ("__C_specific_handler",):
        return out
    n = struct.unpack_from("<I", d, tail + 4)[0]
    ref_n = img.u32(ref_tail + 4)
    entries, ok = [], n == ref_n
    for i in range(min(n, ref_n)):
        fo = tail + 8 + 16 * i
        cand_vals = struct.unpack_from("<IIII", d, fo)
        ref_vals = struct.unpack_from("<IIII", img.read(ref_tail + 8 + 16 * i, 16))
        e = {}
        for j, name in enumerate(("begin", "end", "handler", "target")):
            r = rel.get(fo + 4 * j)
            if r is None:  # absolute value, e.g. EXCEPTION_EXECUTE_HANDLER (1)
                e[name] = {"candidate": cand_vals[j], "reference": ref_vals[j],
                           "equal": cand_vals[j] == ref_vals[j]}
            elif r.symbol == symbol:
                c_off, r_off = cand_vals[j], ref_vals[j] - start
                e[name] = {"candidate_offset": hx(c_off), "reference_offset": hx(r_off),
                           "equal": c_off == r_off}
            else:
                want = funclet_rvas.get(r.symbol)
                e[name] = {"candidate_symbol": r.symbol, "reference_rva": hx(ref_vals[j]),
                           "resolves_to_manifest_rva": hx(want) if want is not None else None,
                           "equal": want is not None and want + cand_vals[j] == ref_vals[j]}
            ok = ok and e[name]["equal"]
        entries.append(e)
    out["scope_table"] = {"count_candidate": n, "count_reference": ref_n,
                          "identical": ok, "entries": entries}
    return out


_OBJ_CACHE: dict[str, CoffObject] = {}


def load_obj(objpath: str) -> CoffObject:
    obj = _OBJ_CACHE.get(objpath)
    if obj is None:
        obj = _OBJ_CACHE[objpath] = CoffObject(OBJ_ROOT / objpath)
    return obj


def compact_diff(diff: dict) -> dict:
    kinds = Counter(r["evidence"].split(":")[0].split(" (")[0].split(" to ")[0]
                    for r in diff.get("resolved_relocations", []))
    if diff["differing_bytes"] == 0 and not diff.get("unresolved_relocations") \
            and diff["reference_size"] == diff["candidate_size"]:
        return {"differing_bytes": 0, "resolved_by": dict(sorted(kinds.items()))}
    return {
        "reference_size": diff["reference_size"], "candidate_size": diff["candidate_size"],
        "differing_bytes": diff["differing_bytes"], "first_difference": diff.get("first_difference"),
        "resolved_relocations": len(diff.get("resolved_relocations", [])),
        "resolved_by": dict(sorted(kinds.items())),
        "unresolved_relocations": [{"offset": u["offset"], "symbol": u["symbol"]}
                                   for u in diff.get("unresolved_relocations", [])],
    }


def evaluate(idx: int, entry: dict, img: PEImage, dimg, rfmap: dict, resolver: Resolver,
             funclet_rvas: dict) -> dict:
    res: dict = {}
    compact = bool(entry.get("compact"))
    if not entry.get("object") or not entry.get("symbol"):
        res["match"] = "unimplemented"
        return res
    sources = [(entry["object"], entry["symbol"])] + [
        (s["object"], s["symbol"]) for s in entry.get("folded_sources", [])]
    start = int(entry["start_rva"], 16) if entry.get("start_rva") else None
    if start is None:
        obj = load_obj(entry["object"])
        res["compiler"] = comp_id(obj)
        cand, _ = obj.function_bytes(entry["symbol"])
        res["candidate_sha256"] = hashlib.sha256(cand).hexdigest()
        res["match"] = "unknown"
        res["reference_state"] = "not-located"
        return res
    end = int(entry["end_rva"], 16)
    ref_file = img.read(start, end - start)
    if not compact:
        res["original_sha256"] = hashlib.sha256(ref_file).hexdigest()
    rf = rfmap.get(start)
    worst = None
    order = ["exact", "relocation-equivalent", "partial", "unmatched", "unknown"]
    file_state = reference_state(img, rf, ref_file, b"")
    ref_dec = dimg.read(start, end - start) if dimg is not None and file_state != "plaintext" else None
    if ref_dec is not None and not compact:
        res["decrypted_sha256"] = hashlib.sha256(ref_dec).hexdigest()
    for objpath, symbol in sources:
        try:
            obj = load_obj(objpath)
        except FileNotFoundError:
            return {"match": "unimplemented", "compare_note": f"object {objpath} not built"}
        try:
            cand_raw, relocs = obj.function_bytes(symbol)
        except KeyError:
            # A reconstruction whose symbol the build did not produce (a declaration or mangling
            # mismatch): this entry is not compiled; the rest of the comparison goes on.
            return {"match": "unimplemented", "compare_note": f"symbol {symbol} not defined in {objpath}"}
        ref = ref_dec if ref_dec is not None else ref_file
        cand, unresolved, resolved = resolve_fields(cand_raw, relocs, start, img.image_base,
                                                    resolver, obj, objpath, ref, idx)
        if ref_dec is not None:
            state = decrypted_state(dimg, rf, ref_file, ref_dec, cand)
        else:
            state = "plaintext" if ref_file == cand else file_state
        diff = byte_diff(ref, cand, unresolved, resolved)
        status = classify(state, diff)
        if status in ("exact", "relocation-equivalent"):
            res.setdefault("_observe", []).append((obj, objpath, relocs, cand_raw, ref, start))
        if (objpath, symbol) == sources[0]:
            if not compact:
                res["compiler"] = comp_id(obj)
            digest = hashlib.sha256(cand).hexdigest()
            res["candidate_sha256"] = digest[:16] if compact else digest
            res["reference_state"] = state
            if state in ("encrypted", "unknown"):
                res["byte_diff"] = {"reference_size": len(ref), "candidate_size": len(cand),
                                    "note": "reference body is encrypted on disk and no decrypted image is available"}
            else:
                res["byte_diff"] = compact_diff(diff) if compact else diff
            if not compact:
                st = compare_structure(img, rf, obj, symbol, start, funclet_rvas)
                if st is not None:
                    st["pdata_size_matches"] = len(cand) == end - start
                    res["structure"] = st
        if worst is None or order.index(status) > order.index(worst):
            worst = status
    res["match"] = worst
    return res


def load_blocks() -> dict[str, dict]:
    """Declared slot blocks, by member symbol (analysis/uht-bss-blocks.json)."""
    path = REPO_ROOT / "analysis" / "uht-bss-blocks.json"
    out = {}
    if path.exists():
        for b in json.loads(path.read_text(encoding="utf-8")).get("blocks", []):
            for m in b["symbols"]:
                out[m] = b
    return out


def load_manual_symbols() -> dict[str, tuple[int, str]]:
    manual: dict[str, tuple[int, str]] = {}
    if SYMBOLS.exists():
        for k, v in json.loads(SYMBOLS.read_text(encoding="utf-8")).get("symbols", {}).items():
            manual[k] = (int(v["rva"], 16), v.get("evidence", "analysis/symbols.json"))
    for name in GENERATED_SYMBOLS:
        path = REPO_ROOT / "analysis" / name
        if path.exists():
            doc = json.loads(path.read_text(encoding="utf-8"))
            codes = doc.get("evidence_codes", {})
            for k, v in doc.get("symbols", {}).items():
                rva, ev = (v["rva"], v["evidence"]) if isinstance(v, dict) else (v[0], codes.get(v[1], v[1]))
                manual.setdefault(k, (int(rva, 16), f"{name}: {ev}"))
    return manual


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="print a summary instead of every entry")
    ap.add_argument("--dump-observations", metavar="PATH",
                    help="also write the final leave-one-out observations (symbol -> addresses -> entries) "
                         "as JSON, for offline layout studies")
    args = ap.parse_args()
    if args.build:
        import msvc
        r = msvc.build_solution(SOLUTION)
        print(r.stdout[-3000:])
        if r.returncode:
            return r.returncode
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    extra = [(p, json.loads(p.read_text(encoding="utf-8")))
             for p in sorted((REPO_ROOT / "analysis").glob(EXTRA_MANIFESTS))]
    entries = list(manifest["functions"])
    owner = [MANIFEST] * len(entries)
    for p, m in extra:
        entries += manifest_io.expand(m)
        owner += [p] * len(m["functions"])
    img = PEImage()
    if img.sha256() != manifest["reference"]["sha256"]:
        print("reference SHA-256 differs from manifest", file=sys.stderr)
        return 2
    dimg = load_decrypted(img)
    resolver = Resolver(img, dimg, load_manual_symbols())
    resolver.blocks = load_blocks()
    rfs = img.runtime_functions()
    rfmap = {rf.begin: rf for rf in rfs}
    text = img.sections[0]
    primary_set = {rf.begin for rf in rfs if text.contains_rva(rf.begin)
                   and not parse_unwind(img, rf.unwind).flags & UNW_FLAG_CHAININFO}
    primary = len(primary_set)
    funclet_rvas = {}
    for e in entries:
        if e.get("start_rva") and e.get("symbol"):
            funclet_rvas[e["symbol"]] = int(e["start_rva"], 16)
            for s in e.get("folded_sources", []):
                funclet_rvas[s["symbol"]] = int(e["start_rva"], 16)

    # Entries verified against the decrypted image can only be re-checked where it exists.
    skip = {i for i, e in enumerate(entries)
            if dimg is None and e.get("reference_state") in DECRYPTED_STATES}
    if dimg is None:
        for i in skip:  # their recorded exact matches still resolve callers
            e = entries[i]
            if e.get("match") == "exact":
                resolver.functions[e["symbol"]] = (int(e["start_rva"], 16),
                                                   f"recorded exact match of manifest entry {e['start_rva']}")

    # Evaluate to a fixpoint. An exact function's symbol may resolve its callers' relocations,
    # and relocation-equivalent-or-better functions contribute observations that resolve
    # *other* entries' fields (leave-one-out). Observations are gathered between passes only.
    resolver.symbol_objects = {e["symbol"]: e["object"] for e in entries if e.get("symbol") and e.get("object")}
    for i, e in enumerate(entries):
        resolver.entry_names[i] = e["name"]
        if e.get("start_rva") and e.get("end_rva"):
            resolver.entry_ranges[i] = (int(e["start_rva"], 16), int(e["end_rva"], 16))

    def snapshot() -> int:
        return hash(frozenset((repr(k), v, frozenset(ents))
                              for k, d in resolver.observations.items() for v, ents in d.items()))

    results: dict = {}
    import time
    for npass in range(1, 33):
        t0 = time.perf_counter()
        results = {i: evaluate(i, e, img, dimg, rfmap, resolver, funclet_rvas)
                   for i, e in enumerate(entries) if i not in skip}
        print(f"pass {npass}: {sum(r.get('match') == 'exact' for r in results.values())} exact, "
              f"{time.perf_counter() - t0:.1f}s", file=sys.stderr)
        for i, res in results.items():
            e = entries[i]
            res["in_denominator"] = bool(e.get("start_rva")) and int(e["start_rva"], 16) in primary_set
        before = snapshot()
        resolver.observations = {}
        resolver.by_addr = {}
        resolver.entry_addrs = {}
        resolver._unobserved = {}
        resolver._name_index = None
        resolver._sg_ranges = None
        resolver._sg_sorted = None
        resolver.folded_obs = {}
        for i, res in results.items():
            for obj, objpath, relocs, cand_raw, ref, start in res.pop("_observe", []):
                resolver.observe(i, obj, objpath, relocs, cand_raw, ref, start, img.image_base)
        added = before != snapshot()
        for i, res in results.items():
            e = entries[i]
            if res.get("match") == "exact" and e.get("start_rva"):
                for sym in [e["symbol"]] + [s["symbol"] for s in e.get("folded_sources", [])]:
                    if sym not in resolver.functions:
                        resolver.functions[sym] = (int(e["start_rva"], 16),
                                                   f"exact match of manifest entry {e['start_rva']}")
                        added = True
        if not added:
            break

    if args.dump_observations:
        obs = []
        for k, d in sorted(resolver.observations.items(), key=lambda kv: repr(kv[0])):
            objpath, sym = (k[0], k[1]) if isinstance(k, tuple) else ("", k)
            obs.append({"object": objpath, "symbol": sym,
                        "at": {f"0x{a:08X}": sorted(entries[i]["name"] for i in ents) for a, ents in sorted(d.items())}})
        Path(args.dump_observations).write_text(json.dumps({"observations": obs}, indent=0), encoding="utf-8")

    stale = []
    for i, res in results.items():
        e = entries[i]
        for k in COMPUTED:
            if e.get(k) != res.get(k):
                stale.append((e.get("start_rva") or e.get("name"), k))
            if k in res:
                e[k] = res[k]
            else:
                e.pop(k, None)
    denom = manifest["denominator"]
    if denom.get("count") != primary:
        stale.append(("denominator", "count"))
    denom["count"] = primary
    if args.quiet:
        for path in [MANIFEST] + [p for p, _ in extra]:
            st = Counter(e.get("match") for e, o in zip(entries, owner) if o == path)
            print(f"{path.name}: {dict(sorted(st.items()))}")
    else:
        for e in entries:
            print(f"{e.get('start_rva') or '(unlocated)':>12}  {e.get('match', '?'):22} "
                  f"{e.get('reference_state', '-'):21} {e['name']}")
    if skip:
        print(f"note: {len(skip)} entries verified against the decrypted image were not re-checked "
              "(local decrypted image not present)")
    if args.check:
        if stale:
            print(f"stale manifest fields ({len(stale)}):", stale[:20], file=sys.stderr)
            return 1
        print("manifest up to date")
        return 0
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for p, m in extra:
        manifest_io.strip(m)
        manifest_io.dump_compact(p, m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
