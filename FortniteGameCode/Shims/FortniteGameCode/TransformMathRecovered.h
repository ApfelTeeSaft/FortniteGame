// FTransform's composition and inversion, from the UE4.20 header Core's Math/TransformVectorized.h.
// Not recovered code.
//
// They read the unit's GlobalVectorConstants (FloatZero, SmallNumber, SignMask, XYZMask, and
// through QuatRecovered.h FloatOne, FloatMinusOne, Float0001, FloatOneHalf, QINV_SIGN_MASK and
// QMULTI_SIGN_MASK0-2), so a unit includes this after defining them. The members are declared in
// TransformRecovered.h and the matrix routines are in QuatRecovered.h, both behind
// FNGC_CORE_MATH_EXTRAS (MathDecls.h), which a unit including this defines to 1.
#pragma once

#include "FortniteGameCode/QuatRecovered.h"

#define VectorNegate( Vec )				_mm_sub_ps(_mm_setzero_ps(),Vec)

inline bool FTransform::Private_AnyHasNegativeScale(const VectorRegister& InScale3D, const  VectorRegister& InOtherScale3D)
{
	return !!VectorAnyLesserThan(VectorMin(InScale3D, InOtherScale3D), GlobalVectorConstants::FloatZero);
}

__forceinline void FTransform::ConstructTransformFromMatrixWithDesiredScale(const FMatrix& AMatrix, const FMatrix& BMatrix, const VectorRegister& DesiredScale, FTransform& OutTransform)
{
	// the goal of using M is to get the correct orientation
	// but for translation, we still need scale
	FMatrix M = AMatrix * BMatrix;
	M.RemoveScaling();

	// apply negative scale back to axes
	FVector SignedScale;
	VectorStoreFloat3(VectorSign(DesiredScale), &SignedScale);

	M.SetAxis(0, SignedScale.X * M.GetScaledAxis(EAxis::X));
	M.SetAxis(1, SignedScale.Y * M.GetScaledAxis(EAxis::Y));
	M.SetAxis(2, SignedScale.Z * M.GetScaledAxis(EAxis::Z));

	// @note: if you have negative with 0 scale, this will return rotation that is identity
	// since matrix loses that axes
	FQuat Rotation = FQuat(M);
	Rotation.Normalize();

	// set values back to output
	OutTransform.Scale3D = DesiredScale;
	OutTransform.Rotation = VectorLoadAligned(&Rotation);

	// technically I could calculate this using FTransform but then it does more quat multiplication
	// instead of using Scale in matrix multiplication
	// it's a question of between RemoveScaling vs using FTransform to move translation
	FVector Translation = M.GetOrigin();
	OutTransform.Translation = VectorLoadFloat3_W0(&Translation);
}

__forceinline FTransform::FTransform(const VectorRegister& InRotation, const VectorRegister& InTranslation, const VectorRegister& InScale3D)
	: Rotation(InRotation),
	Translation(InTranslation),
	Scale3D(InScale3D)
{
}

__forceinline FTransform FTransform::InverseFast() const
{
	// Invert the scale
	const VectorRegister InvScale = VectorSet_W0(GetSafeScaleReciprocal(Scale3D , ScalarRegister(GlobalVectorConstants::SmallNumber)));

	// Invert the rotation
	const VectorRegister InvRotation = VectorQuaternionInverse(Rotation);

	// Invert the translation
	const VectorRegister ScaledTranslation = VectorMultiply(InvScale, Translation);
	const VectorRegister t2 = VectorQuaternionRotateVector(InvRotation, ScaledTranslation);
	const VectorRegister InvTranslation = VectorSet_W0(VectorNegate(t2));

	return FTransform(InvRotation, InvTranslation, InvScale);
}

__forceinline FTransform FTransform::Inverse() const
{
	// Replacement of Inverse of FMatrix
	if (VectorAnyGreaterThan(VectorAbs(Scale3D), GlobalVectorConstants::SmallNumber))
	{
		return InverseFast();
	}
	else
	{
		return FTransform::Identity;
	}
}

__forceinline void FTransform::MultiplyUsingMatrixWithScale(FTransform* OutTransform, const FTransform* A, const FTransform* B)
{
	ConstructTransformFromMatrixWithDesiredScale(A->ToMatrixWithScale(), B->ToMatrixWithScale(), VectorMultiply(A->Scale3D, B->Scale3D), *OutTransform);
}

__forceinline void FTransform::Multiply(FTransform* OutTransform, const FTransform* A, const FTransform* B)
{
	//	Q(AxB) = Q(B)*Q(A)
	//	S(AxB) = S(A)*S(B)
	//	T(AxB) = Q(B)*S(B)*T(A)*-Q(B) + T(B)
	if (Private_AnyHasNegativeScale(A->Scale3D, B->Scale3D))
	{
		// @note, if you have 0 scale with negative, you're going to lose rotation as it can't convert back to quat
		MultiplyUsingMatrixWithScale(OutTransform, A, B);
	}
	else
	{
		const VectorRegister QuatA = A->Rotation;
		const VectorRegister QuatB = B->Rotation;
		const VectorRegister TranslateA = A->Translation;
		const VectorRegister TranslateB = B->Translation;
		const VectorRegister ScaleA = A->Scale3D;
		const VectorRegister ScaleB = B->Scale3D;

		// RotationResult = B.Rotation * A.Rotation
		OutTransform->Rotation = VectorQuaternionMultiply2(QuatB, QuatA);

		// TranslateResult = B.Rotate(B.Scale * A.Translation) + B.Translate
		const VectorRegister ScaledTransA = VectorMultiply(TranslateA, ScaleB);
		const VectorRegister RotatedTranslate = VectorQuaternionRotateVector(QuatB, ScaledTransA);
		OutTransform->Translation = VectorAdd(RotatedTranslate, TranslateB);

		// ScaleResult = Scale.B * Scale.A
		OutTransform->Scale3D = VectorMultiply(ScaleA, ScaleB);;
	}
}

__forceinline FTransform FTransform::operator*(const FTransform& Other) const
{
	FTransform Output;
	Multiply(&Output, this, &Other);
	return Output;
}
