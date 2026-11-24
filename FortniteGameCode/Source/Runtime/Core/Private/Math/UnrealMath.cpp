// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: Core. Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/Core/Private/Math/UnrealMath.cpp.
// Reconstruction written from image evidence; see analysis/functions.json.

#include "FortniteGameCode/MathDecls.h"

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
