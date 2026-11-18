# Stage 1 status

| Check | Result |
| --- | --- |
| Reference | 82,298,304-byte AMD64 PE, SHA-256 `9731a6b5e1fab894c089849713c371182e357dcbefa7d8d4e71dc19eeb449102` |
| VS2019 build | `ClientShipping\|x64` comparison DLL built with 0 warnings and 0 errors |
| Historical compiler probe | v140 compiled and linked. Synthetic leaf, branch, large-frame, and SIMD-save functions matched the v142 output byte for byte |
| IDA 9.4 | Full local export completed with 76,746 entries. Targeted export ran against six reflection entries. The full count includes false positives from opaque code |
| Unwind audit | 153,169 supported file-backed prologues checked, including SIMD saves and handler records. Three agree with unwind data and two have complete bodies |
| Startup discovery | Static trace saved for 32 blocks, with 7 pending addresses. The directly called block at RVA `0x0005BAC5` has no saved IDA function boundary |
| Reference matching | 1 exact and 1 partial compiler-generated filter. 0 confirmed eligible functions and 6 unresolved native registration records |
| Whole-image equality | False for the comparison DLL |
| Git | `origin` is configured for the GitHub repository. The local engine and reference installations are ignored |

## Blocker and next evidence

Both toolchains reproduced all 42 bytes at RVA `0x02DAE780`, including the
trailing trap in the PE's recorded extent. The second filter at `0x02DAE750`
differs at byte offset `0x0C`, where the compiler chose a different stack
slot for the exception pointer. The eligibility rules exclude both generated
filters from the game and engine function progress numerator and denominator.

The six reflected entries have corroborated names and PE ranges, but their saved bytes do not implement the instructions expected from their x64 unwind records. One has no IDA function start at its registration address. Five produced pseudocode from implausible sequences, including privileged instructions and mismatched boundaries. None established an original class, signature, or gameplay implementation.

The targeted IDA export checked SEH parent entries `0x016138D0`,
`0x016138F0`, and `0x0165FEB0`. The first and third remain opaque, and the
middle entry has no function start in the saved database. Their Direct3D
ownership remains unconfirmed. The entry-point call path enters section 10,
spills integer and SIMD registers, then branches into disjoint blocks in
section 0. The bounded static trace records these edges and range hashes.

1. Continue the startup trace from RVA `0x0005BAC5` and the explicit pending addresses in `analysis/startup-flow.json`. Establish complete disjoint function boundaries and the purpose of the startup routine from further evidence.
2. Locate the implementation behind a reflected registration entry once available evidence establishes its ABI. Record its complete range and compare a C++ build with v140 and v142.
3. Audit chained unwind entries as evidence warrants. Keep handler ownership and any transformed code interpretation explicit. Any separately supplied comparison image requires its own fingerprint and results.
