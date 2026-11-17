# Stage 1 status

| Check | Result |
| --- | --- |
| Reference | 82,298,304-byte AMD64 PE, SHA-256 `9731a6b5e1fab894c089849713c371182e357dcbefa7d8d4e71dc19eeb449102` |
| VS2019 build | `ClientShipping\|x64` comparison DLL built with 0 warnings and 0 errors |
| Historical compiler probe | v140 compiled and linked. A synthetic leaf and a synthetic branching function both matched the v142 output byte for byte |
| IDA 9.4 | Full local export completed with 76,746 entries. Targeted export ran against six reflection entries. The full count includes false positives from opaque code |
| Unwind audit | 47,239 supported file-backed prologues checked. Only the entry point matched its unwind record, and its body failed validation |
| Reference matching | 0 exact matches, 0 confirmed eligible functions, 6 unresolved native registration records |
| Whole-image equality | False for the comparison DLL |
| Git | `origin` is configured for the GitHub repository. The local engine and reference installations are ignored |

## Blocker and next evidence

The six reflected entries have corroborated names and PE ranges, but their saved bytes do not implement the instructions expected from their x64 unwind records. One has no IDA function start at its registration address. Five produced pseudocode from implausible sequences, including privileged instructions and mismatched boundaries. None established an original class, signature, or gameplay implementation.

1. Use the retained local IDA database to look for coherent bodies with independently verified boundaries outside the audited unwind form.
2. Locate the implementation behind a reflected registration entry once available evidence establishes its ABI. Record its complete range and compare a C++ build with v140 and v142.
3. Extend range validation for additional unwind operations as evidence warrants. Keep split functions and relocated bytes outside exact counts until their complete raw ranges are independently verified. Any separately supplied comparison image requires its own fingerprint and results.
