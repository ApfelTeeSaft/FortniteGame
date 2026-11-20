# Reverse-engineering method and findings

## Coordinates

All addresses are RVAs relative to image base `0x140000000`. Main `.text` maps
RVA `0x1000` to file offset `0x600`, so for RVAs in that section
`file offset = RVA - 0xA00`. Manifest ranges are `.pdata` `[BeginAddress, EndAddress)`,
which is the extent the compiler recorded, including any trailing `int3`.

## Code protection

Survey method (`tools/matching/survey.py`): every `RUNTIME_FUNCTION` is decoded, and
its `UNWIND_INFO` prologue codes are checked against a linear decode of the on-disk
bytes. The check covers push register, allocation size, frame register and register saves.

| Population | Count | Prologue agrees with unwind record |
| --- | --- | --- |
| `.pdata` entries | 253,131 | 11 |
| primary (non-chained) entries in main `.text` | 157,719 | 3: entry stub `0x02D996CC`, filters `0x02DAE750`, `0x02DAE780` |
| chained fragments | 95,412 | 8 |

Further observations:

* Inside low-entropy pages the `0xCC` inter-function padding is intact, but function
  bodies decode as random instructions. Encryption is therefore per function, not per page.
* Bytes outside every `.pdata` range (leaf code) are encrypted in the same way.
* `.rdata`, `.xdata` (unwind and scope tables), `.pdata`, imports and resources are plaintext.
* The entry point `0x02D996CC` (18 bytes, the shape of `mainCRTStartup`) keeps
  `sub rsp,28h`, but its first call targets RVA `0x04DDF2FC` in a second `.text` section
  (`0x04DDD000`, 3.5 MB, no `.pdata`). The rest of the stub is encrypted. The entry is
  therefore not matchable as on disk.
* Even exception-handler thunks are encrypted, so handler identities must come from usage
  patterns, not bytes.

## Matching rules (`tools/matching/compare.py`)

* `exact`: the reference range is plaintext, sizes are equal, and every byte is identical.
  Relocation fields count only if resolved through `analysis/symbols.json`, whose entries
  need independent evidence. Nothing is masked.
* `relocation-equivalent`: identical except for unresolved relocation fields. Not exact.
* `partial` / `unmatched`: some or no bytes agree.
* `unknown`: the reference body is encrypted (or the range is not located).
  Structural evidence is recorded alongside but never upgrades the state.

Structural evidence compares plaintext metadata with the compiled object: the `.pdata`
size, the `UNWIND_INFO` header and codes, and C scope-table entries. Scope entries are
compared as offsets from the function start; filter fields are compared through the
manifest RVA of an exactly matched funclet. Handler RVAs are reported, not compared,
until their identity is independently established.

## Denominator

The denominator is the 157,719 primary `.pdata` functions in the main `.text`. It
includes compiler-generated funclets, CRT and third-party code because encrypted
bodies make finer classification impossible. Leaf functions without `.pdata` are not
counted. Exact matches are broken down by category in the progress image.

## First reconstructed family: delay-load SEH guards (D3D11RHI / D3D12RHI)

Parents were found through C scope tables whose filter field points at the two
plaintext funclets:

| RVA | Function | Result |
| --- | --- | --- |
| `0x02DAE750` | filter of `SafeTestD3D11CreateDevice` | exact, 42/42 bytes |
| `0x02DAE780` | filter of `SafeCreateDXGIFactory` (ICF-folded, two parents) | exact, 42/42 bytes. The D3D12 source compiles to the same bytes |
| `0x016138D0` | `SafeCreateDXGIFactory` (D3D11) | unknown (encrypted); size, unwind and scope identical |
| `0x016138F0` | `SafeTestD3D11CreateDevice` | unknown (encrypted); size 0x13E, all 6 unwind codes, handler kind and scope `[+0xBD,+0x126)` identical |
| `0x0165FEB0` | second `SafeCreateDXGIFactory`-shaped parent | unknown (encrypted); owner unconfirmed |

The structural matches pinned down two differences from public 4.20.0 (see
[ENGINE_DIFFERENCES.md](ENGINE_DIFFERENCES.md)). They also showed that
`D3D11RHI_ShouldCreateWithD3DDebug` is inlined across files, i.e. a unity build.

## Naming confidence

`confirmed` needs direct evidence such as an exported symbol, reflection string or
debug data. Names inferred from engine source plus unique structural agreement are
`high-confidence inferred`. Shape-only agreement is `low-confidence inferred`.
