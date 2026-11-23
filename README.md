# Fortnite 2.5 (Win64) decompilation

Evidence-driven reconstruction of the Fortnite 2.5 Windows client
(`++Fortnite+Release-2.5-CL-3889387`), aimed at function-level byte matching with
the original MSVC 19.00.24215 toolchain. Later stages cover a dedicated-server
target, UE4.20 integration, and recovery of the Unreal project.

![Fortnite 2.5 — Exact Function Matches](docs/images/byte-match-progress.svg)

*Text alternative: 33,478 of 157,719 identified functions (primary `.pdata` entries, 21.23 %) match the
original bytes exactly. Function bodies in the shipping executable are encrypted on disk, so
bodies are compared with a locally validated decrypted image of the same build. A relocation
counts only when resolved from independent evidence or corroborated by a different matched
function.*

**Stage:** 1 of 4 (exact-match client decompilation). See [docs/STATUS.md](docs/STATUS.md).
For building and verification see [docs/BUILDING.md](docs/BUILDING.md); method and
limitations are in [docs/REVERSE_ENGINEERING.md](docs/REVERSE_ENGINEERING.md).

This repository contains no original game files, executables, assets, keys or Unreal
Engine source. You need your own copies to build or verify anything.

Contribute and Donate

If you want to contribute to this project, the easiest way would be to donate Money that I can turn into AI Tokens for Claude to work 24/7, without it, the AI will stop due to usage running out and the result will be delayed!

All Donations will end up being converted into Tokens to aid this project!
