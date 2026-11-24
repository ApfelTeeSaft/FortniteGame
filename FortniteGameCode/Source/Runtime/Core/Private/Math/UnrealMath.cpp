// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: Core. Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/Core/Private/Math/UnrealMath.cpp.
// Reconstruction written from image evidence; see analysis/functions.json.

#include "FortniteGameCode/MathDecls.h"
#include "FortniteGameCode/RecoveryHarness.h"

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A6B30 (end 0x011A6BA2)
// Original VA: 0x00000001411A6B30 | File offset: 0x011A6130
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: yaw Atan2(Y, X) and pitch Atan2(Z, Sqrt(X*X + Y*Y)), each scaled by 180/PI, roll 0;
//   its only caller is FVector::Rotation (0x011A1EA0). ENABLE_NAN_DIAGNOSTIC is 0 in shipping.
FRotator FVector::ToOrientationRotator() const
{
	FRotator R;

	// Find yaw.
	R.Yaw = FMath::Atan2(Y,X) * (180.f / PI);

	// Find pitch.
	R.Pitch = FMath::Atan2(Z,FMath::Sqrt(X*X+Y*Y)) * (180.f / PI);

	// Find roll.
	R.Roll = 0;

	return R;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A1EA0 (end 0x011A1EB7)
// Original VA: 0x00000001411A1EA0 | File offset: 0x011A14A0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: a member forwarding this and the return slot to FVector::ToOrientationRotator. The
//   exec thunk of UKismetMathLibrary::Conv_VectorToRotator calls it (the Kismet function is inlined
//   there), so analysis/native-implementations.json lists it under that name at low confidence.
FRotator FVector::Rotation() const
{
	return ToOrientationRotator();
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A8000 (end 0x011A82A1)
// Original VA: 0x00000001411A8000 | File offset: 0x011A7600
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::GetForwardVector (0x020812F0); two FMath::SinCos
//   expansions of Pitch and Yaw in radians, returning (CP*CY, CP*SY, SP).
FVector FRotator::Vector() const
{
	float CP, SP, CY, SY;
	FMath::SinCos( &SP, &CP, FMath::DegreesToRadians(Pitch) );
	FMath::SinCos( &SY, &CY, FMath::DegreesToRadians(Yaw) );
	FVector V = FVector( CP*CY, CP*SY, SP );

	return V;
}

// FMath::VRand is inline in Math/Vector.h; the reference keeps one out-of-line copy (COMDAT), from
// an object not established. The anchor table below makes this unit emit it.
// Original FortniteClient-Win64-Shipping.exe: RVA 0x00AA95F0 (end 0x00AA96FD)
// Original VA: 0x0000000140AA95F0 | File offset: 0x00AA8BF0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::RandomUnitVector (0x0208D930); three FRand() calls
//   (rand() / RAND_MAX) per try until 1e-4 <= |V|^2 <= 1, then V / Sqrt(|V|^2).
inline FVector FMath::VRand()
{
	FVector Result;

	float L;

	do
	{
		// Check random vectors in the unit sphere so result is statistically uniform.
		Result.X = FRand() * 2.f - 1.f;
		Result.Y = FRand() * 2.f - 1.f;
		Result.Z = FRand() * 2.f - 1.f;
		L = Result.SizeSquared();
	}
	while(L > 1.0f || L < KINDA_SMALL_NUMBER);

	return Result * (1.0f / Sqrt(L));
}

#if FNGC_MATCHING_HARNESS
FNGC_ANCHOR_TABLE(GFngcAnchors_UnrealMath)
{
	(const void*)&FMath::VRand,
};
#endif
