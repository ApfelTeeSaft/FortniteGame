// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: Core. Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/Core/Private/GenericPlatform/GenericPlatformMisc.cpp.
// Reconstruction written from image evidence; see analysis/functions.json.

#include "FortniteGameCode/EngineDecls.h"

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01112B50 (end 0x01112B72)
// Original VA: 0x0000000141112B50 | File offset: 0x01112150
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: the only function passing L"noheartbeatthread" to FParse::Param(FCommandLine::Get(), ...);
//   it returns the negated result. In the 4.20 tree that literal appears only here.
bool FGenericPlatformMisc::AllowThreadHeartBeat()
{
	if (FParse::Param(FCommandLine::Get(), TEXT("noheartbeatthread")))
	{
		return false;
	}

	return true;
}
