// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: Core. Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/Core/Private/Stats/Stats2.cpp.
// Reconstruction written from image evidence; see analysis/functions.json.
//
// The three functions keep their source order: their thread-safe statics (each a bool and its
// guard) are adjacent in the reference's .bss in that order, 0x046AEBD8..0x046AEBEF.

#include "FortniteGameCode/EngineDecls.h"

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011E61B0 (end 0x011E6226)
// Original VA: 0x00000001411E61B0 | File offset: 0x011E57B0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: a thread-safe static set from the two functions below (called, not inlined), the
//   only caller of both; its static directly precedes theirs.
bool FStats::EnabledForCommandlet()
{
	static bool bHasStatsForCommandletsToken = HasLoadTimeStatsForCommandletToken() || HasLoadTimeFileForCommandletToken();
	return bHasStatsForCommandletsToken;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011E64B0 (end 0x011E6520)
// Original VA: 0x00000001411E64B0 | File offset: 0x011E5AB0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: a thread-safe static set from FParse::Param(FCommandLine::Get(), L"LoadTimeStatsForCommandlet"),
//   the literal used only here in the 4.20 tree.
bool FStats::HasLoadTimeStatsForCommandletToken()
{
	static bool bHasLoadTimeStatsForCommandletToken = FParse::Param(FCommandLine::Get(), TEXT("LoadTimeStatsForCommandlet"));
	return bHasLoadTimeStatsForCommandletToken;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011E6440 (end 0x011E64B0)
// Original VA: 0x00000001411E6440 | File offset: 0x011E5A40
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: the same over L"LoadTimeFileForCommandlet".
bool FStats::HasLoadTimeFileForCommandletToken()
{
	static bool bHasLoadTimeFileForCommandletToken = FParse::Param(FCommandLine::Get(), TEXT("LoadTimeFileForCommandlet"));
	return bHasLoadTimeFileForCommandletToken;
}
