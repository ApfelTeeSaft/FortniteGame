// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: Core. Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/Core/Private/GenericPlatform/GenericPlatformProcess.cpp.
// Reconstruction written from image evidence; see analysis/functions.json.

#include "FortniteGameCode/EngineDecls.h"

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01123730 (end 0x011237A3)
// Original VA: 0x0000000141123730 | File offset: 0x01122D30
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: a thread-safe static set from !FParse::Param(FCommandLine::Get(), L"nothreading"), the
//   literal used only here in the 4.20 tree (DEFAULT_NO_THREADING is 0 on Windows).
bool FGenericPlatformProcess::SupportsMultithreading()
{
	static bool bSupportsMultithreading = !FParse::Param(FCommandLine::Get(), TEXT("nothreading"));
	return bSupportsMultithreading;
}
