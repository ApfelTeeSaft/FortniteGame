// Matching-harness helpers. Not recovered code.
//
// Recovered translation units keep the original internal linkage of their
// functions. A file-static function with no caller in the TU would be
// discarded by the compiler, so each TU lists its recovered statics in an
// anchor table guarded by FNGC_MATCHING_HARNESS. The table only takes the
// functions' addresses; it does not change their generated code.
#pragma once

#if FNGC_MATCHING_HARNESS
#define FNGC_ANCHOR_TABLE(Name) extern "C" const void* const Name[]; extern "C" const void* const Name[] =
#endif
