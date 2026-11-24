// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: Engine. Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/Engine/Private/GameplayStatics.cpp.
// Reconstruction written from image evidence; see analysis/functions.json.

// Hand-written natives of UGameplayStatics, declared in its generated class body
// (tools/codegen/uht_classes.py, EXTRA_MEMBERS).
#define FNGC_EXTRA_MEMBERS_UGameplayStatics \
	static bool HasLaunchOption(const FString& OptionToCheck);

#include "FortniteGameCode/UHTRecovered.h"
#include "FortniteGameCode/CommandLineDecls.h"

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01FFE540 (end 0x01FFE56D)
// Original VA: 0x0000000141FFE540 | File offset: 0x01FFDB40
// Recovery: high-confidence inferred (called by execHasLaunchOption) | Matching: see analysis/functions.json
// Evidence: the native implementation that UGameplayStatics::execHasLaunchOption calls
//   (analysis/native-implementations.json); FString::operator* (TEXT("") when empty) inlined
//   before the tail call to FParse::Param(FCommandLine::Get(), ...).
bool UGameplayStatics::HasLaunchOption(const FString& OptionToCheck)
{
	return FParse::Param(FCommandLine::Get(), *OptionToCheck);
}
