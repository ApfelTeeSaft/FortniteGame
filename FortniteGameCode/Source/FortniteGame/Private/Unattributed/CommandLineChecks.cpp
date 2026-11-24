// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: not established (Fortnite game code; no source in the supplied tree).
// Reconstruction written from image evidence; see analysis/functions.json.
//
// Each function returns whether a Fortnite-specific switch is absent from the command line. Their
// names, owners and callers' intent are unknown, so they keep neutral names with their RVA.

#include "FortniteGameCode/EngineDecls.h"

// Original FortniteClient-Win64-Shipping.exe: RVA 0x008641F0 (end 0x00864212)
// Original VA: 0x00000001408641F0 | File offset: 0x008637F0
// Recovery: unknown (neutral name) | Matching: see analysis/functions.json
// Evidence: !FParse::Param(FCommandLine::Get(), L"AlternateAIDirectorBalance"), the literal not in
//   the 4.20 tree.
bool FortniteGame_NoAlternateAIDirectorBalance_008641F0()
{
	return !FParse::Param(FCommandLine::Get(), TEXT("AlternateAIDirectorBalance"));
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x00EF0D50 (end 0x00EF0D72)
// Original VA: 0x0000000140EF0D50 | File offset: 0x00EF0350
// Recovery: unknown (neutral name) | Matching: see analysis/functions.json
// Evidence: !FParse::Param(FCommandLine::Get(), L"activities"), the literal not in the 4.20 tree.
bool FortniteGame_NoActivities_00EF0D50()
{
	return !FParse::Param(FCommandLine::Get(), TEXT("activities"));
}
