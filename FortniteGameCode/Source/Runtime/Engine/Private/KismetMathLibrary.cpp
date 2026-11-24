// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: Engine. Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/Engine/Private/KismetMathLibrary.cpp.
// Reconstruction written from image evidence; see analysis/functions.json.

// Hand-written natives of UKismetMathLibrary, declared in its generated class body
// (tools/codegen/uht_classes.py, EXTRA_MEMBERS).
#define FNGC_EXTRA_MEMBERS_UKismetMathLibrary \
	static FVector RandomUnitVector(); \
	static FVector GetForwardVector(FRotator InRot);

#include "FortniteGameCode/UHTRecovered.h"

// Core's FMath (GenericPlatform/GenericPlatformMath.h, Math/UnrealMathUtility.h): only the member
// called here. FMath::VRand is inline in Math/Vector.h, but the reference calls its out-of-line copy.
struct FMath
{
	static FVector VRand();
};

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208D930 (end 0x0208D947)
// Original VA: 0x000000014208D930 | File offset: 0x0208CF30
// Recovery: high-confidence inferred (called by execRandomUnitVector) | Matching: see analysis/functions.json
// Evidence: the native implementation execRandomUnitVector calls (analysis/native-implementations.json),
//   forwarding its return slot to FMath::VRand (0x00AA95F0).
FVector UKismetMathLibrary::RandomUnitVector()
{
	return FMath::VRand();
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x020812F0 (end 0x02081310)
// Original VA: 0x00000001420812F0 | File offset: 0x020808F0
// Recovery: high-confidence inferred (called by execGetForwardVector) | Matching: see analysis/functions.json
// Evidence: the native implementation execGetForwardVector calls: a static function (it swaps the
//   return slot and its by-reference FRotator argument) calling FRotator::Vector (0x011A8000).
FVector UKismetMathLibrary::GetForwardVector(FRotator InRot)
{
	return InRot.Vector();
}
