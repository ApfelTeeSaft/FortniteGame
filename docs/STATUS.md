# Stage 1 status

| Check | Result |
| --- | --- |
| Reference | 82,298,304-byte AMD64 PE, SHA-256 `9731a6b5e1fab894c089849713c371182e357dcbefa7d8d4e71dc19eeb449102` |
| VS2019 build | `ClientShipping\|x64` comparison DLL built with 0 warnings and 0 errors |
| Historical compiler probe | v140 compiled and linked. Synthetic leaf, branch, and large-frame functions matched the v142 output byte for byte |
| IDA 9.4 | Full local export completed with 76,746 entries. Targeted export ran against six reflection entries. The full count includes false positives from opaque code |
| Unwind audit | 138,213 supported file-backed prologues checked. Three agree with unwind data and two have complete bodies |
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

1. Use the retained local IDA database to look for coherent bodies with independently verified boundaries outside the audited unwind form.
2. Locate the implementation behind a reflected registration entry once available evidence establishes its ABI. Record its complete range and compare a C++ build with v140 and v142.
3. Follow the verified SEH scope references into the enclosing routines and look for code or reflection metadata that confirms their Direct3D ownership. Extend unwind coverage to other records as evidence warrants. Any separately supplied comparison image requires its own fingerprint and results.
