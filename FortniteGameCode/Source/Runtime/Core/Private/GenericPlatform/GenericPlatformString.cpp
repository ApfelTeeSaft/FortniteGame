// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: Core. Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/Core/Private/GenericPlatform/GenericPlatformString.cpp.
// Reconstruction written from image evidence; see analysis/functions.json.

#define FNGC_CORE_MATH_EXTRAS 1   // FGenericPlatformString (ContainersRecovered.h)
#include "FortniteGameCode/MathDecls.h"
#include "FortniteGameCode/ContainersRecovered.h"

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0111CAE0 (end 0x0111CAF7)
// Original VA: 0x000000014111CAE0 | File offset: 0x0111C0E0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: FString's literal constructor calls it through FPlatformString::Convert with the
//   copy's byte count (UKismetMathLibrary::FromDays 0x0207D8E0 and the other From* natives);
//   the CRT memcpy (0x02D9ADE0), then Dest as the result.
void* FGenericPlatformString::Memcpy(void* Dest, const void* Src, SIZE_T Count)
{
	return FMemory::Memcpy(Dest, Src, Count);
}
