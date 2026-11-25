// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: Engine. Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/Engine/Classes/Kismet/KismetMathLibrary.inl.
// Reconstruction written from image evidence; see analysis/functions.json.
//
// Out-of-line copies of four KISMET_MATH_INLINE (plain `inline`) functions. KismetMathLibrary.h
// includes the .inl, and in the reference the generated unity unit Engine.18 emits these
// copies: its exec thunks call them without inlining them. They read that unit's
// GlobalVectorConstants (0x048B7290-0x048B7360; analysis/unity-order.json). The exec thunks are
// not reconstructed, so nothing here would call an `inline` definition and none would be
// emitted. The functions are defined without `inline`, which gives the same code, and
// tools/codegen/unity.py (UNIT_SOURCES) compiles this file in Engine.18 after its fragments.
// KismetMathLibraryUnity.h opens the unit.

#include "FortniteGameCode/TransformMathRecovered.h"

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02430650 (end 0x02430B9E)
// Original VA: 0x0000000142430650 | File offset: 0x0242FC50
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: execComposeTransforms (0x0243B730) calls it; FTransform::operator* inlined: the
//   default FTransform, Private_AnyHasNegativeScale (minps, cmpltps FloatZero), the
//   MultiplyUsingMatrixWithScale path (FMatrix::RemoveScaling 0x00575220, FQuat(const FMatrix&)
//   0x00569390) and VectorQuaternionMultiply2 (QMULTI_SIGN_MASK0-2).
FTransform UKismetMathLibrary::ComposeTransforms(const FTransform& A, const FTransform& B)
{
	return A * B;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02430CE0 (end 0x02430E21)
// Original VA: 0x0000000142430CE0 | File offset: 0x024302E0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: execGetDirectionUnitVector (0x02440F90) calls it; FVector::GetSafeNormal inlined
//   (the 1.0f and SMALL_NUMBER tests, FVector::ZeroVector 0x046A1130).
FVector UKismetMathLibrary::GetDirectionUnitVector(FVector From, FVector To)
{
	return (To - From).GetSafeNormal();
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x024313F0 (end 0x0243152F)
// Original VA: 0x00000001424313F0 | File offset: 0x024309F0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: execInvertTransform (0x02444600) calls it; FTransform::Inverse inlined: the
//   SignMask and SmallNumber scale test, InverseFast (QINV_SIGN_MASK, XYZMask) and the copy of
//   FTransform::Identity (0x046A0E80).
FTransform UKismetMathLibrary::InvertTransform(const FTransform& T)
{
	return T.Inverse();
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x024315F0 (end 0x024316AC)
// Original VA: 0x00000001424315F0 | File offset: 0x02430BF0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: execRandomPointInBoundingBox (0x0244D8F0) calls it; builds the FBox and calls
//   FMath::RandPointInBox (0x011A1020).
FVector UKismetMathLibrary::RandomPointInBoundingBox(const FVector& Origin, const FVector& BoxExtent)
{
	const FVector BoxMin = Origin - BoxExtent;
	const FVector BoxMax = Origin + BoxExtent;
	return FMath::RandPointInBox(FBox(BoxMin, BoxMax));
}
