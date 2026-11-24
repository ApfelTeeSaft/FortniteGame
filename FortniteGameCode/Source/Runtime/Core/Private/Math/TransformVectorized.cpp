// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: Core. Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/Core/Private/Math/TransformVectorized.cpp.
// Reconstruction written from image evidence; see analysis/functions.json.
//
// Compiled through UnrealMath.cpp, which includes this file at its end. The reference builds both
// in one Core unity unit: GetRelativeTransform reads that unit's GlobalVectorConstants (FloatOne
// 0x046A0EB0, XYZMask 0x046A0EC0, ...), which UnrealMath.cpp defines, and FTransform::Identity
// sits in the same .bss block (0x046A0E80).

// FTransform identity
// @Note: Do not reference FVector::ZeroVector or FVector::OneVector
// because they're not initialized yet, it will come as 0 vector
const FTransform FTransform::Identity(FQuat(0.f,0.f,0.f,1.f), FVector(0.f), FVector(1.f));

// Math/TransformVectorized.h: the inline members the functions below use.
__forceinline bool FTransform::IsRotationNormalized() const
{
	const VectorRegister TestValue = VectorAbs(VectorSubtract(VectorOne(), VectorDot4(Rotation, Rotation)));
	return !VectorAnyGreaterThan(TestValue, GlobalVectorConstants::ThreshQuatNormalized);
}

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

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01195BD0 (end 0x01195D03)
// Original VA: 0x0000000141195BD0 | File offset: 0x011951D0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: the 4.20 body (safe reciprocal scale, quaternion inverse and product); sorts after
//   GetRelativeTransform.
FTransform FTransform::GetRelativeTransformReverse(const FTransform& Other) const
{
	// A (-1) * B = VQS(B)(VQS (A)(-1))
	//
	// Scale = S(B)/S(A)
	// Rotation = Q(B) * Q(A)(-1)
	// Translation = T(B)-S(B)/S(A) *[Q(B)*Q(A)(-1)*T(A)*Q(A)*Q(B)(-1)]
	// where A = this, and B = Other
	FTransform Result;

	// Scale = S(B)/S(A)
	VectorRegister VSafeScale3D	= VectorSet_W0(GetSafeScaleReciprocal(Scale3D));
	VectorRegister VScale3D = VectorMultiply(Other.Scale3D, VSafeScale3D);

	// Rotation = Q(B) * Q(A)(-1)
	VectorRegister VInverseRot = VectorQuaternionInverse(Rotation);
	VectorRegister VRotation = VectorQuaternionMultiply2(Other.Rotation, VInverseRot );

	// RotatedTranslation
	VectorRegister VR = VectorQuaternionRotateVector(VRotation, Translation);

	// Translation = T(B)-S(B)/S(A) *[Q(B)*Q(A)(-1)*T(A)*Q(A)*Q(B)(-1)]
	VectorRegister VTranslation = VectorSet_W0(VectorSubtract(Other.Translation, VectorMultiply(VScale3D, VR)));

	Result.Scale3D = VScale3D;
	Result.Translation = VTranslation;
	Result.Rotation = VRotation;

	return Result;
}

/**
 * Set current transform and the relative to ParentTransform.
 * Equates to This = This->GetRelativeTransform(Parent), but saves the intermediate FTransform storage and copy.
 */
// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A4980 (end 0x011A4ACD)
// Original VA: 0x00000001411A4980 | File offset: 0x011A3F80
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: the 4.20 body, GetRelativeTransform's arithmetic in place; sorts between
//   SegmentPlaneIntersection (0x011A32A0) and SlerpFullPath_NotNormalized (0x011A5870).
void FTransform::SetToRelativeTransform(const FTransform& ParentTransform)
{
	// A * B(-1) = VQS(B)(-1) (VQS (A))
	//
	// Scale = S(A)/S(B)
	// Rotation = Q(B)(-1) * Q(A)
	// Translation = 1/S(B) *[Q(B)(-1)*(T(A)-T(B))*Q(B)]
	// where A = this, B = Other

	// Scale = S(A)/S(B)
	VectorRegister VSafeScale3D	= VectorSet_W0(GetSafeScaleReciprocal(ParentTransform.Scale3D, ScalarRegister(SMALL_NUMBER)));
	Scale3D = VectorMultiply(Scale3D, VSafeScale3D);

	//VQTranslation = (  ( T(A).X - T(B).X ),  ( T(A).Y - T(B).Y ), ( T(A).Z - T(B).Z), 0.f );
	VectorRegister VQTranslation = VectorSet_W0(VectorSubtract(Translation, ParentTransform.Translation));

	// Inverse RotatedTranslation
	VectorRegister VInverseParentRot = VectorQuaternionInverse(ParentTransform.Rotation);
	VectorRegister VR = VectorQuaternionRotateVector(VInverseParentRot, VQTranslation);

	// Translation = 1/S(B)
	Translation = VectorMultiply(VR, VSafeScale3D);

	// Rotation = Q(B)(-1) * Q(A)
	Rotation = VectorQuaternionMultiply2(VInverseParentRot, Rotation );
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01195D10 (end 0x01196272)
// Original VA: 0x0000000141195D10 | File offset: 0x01195310
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by GetRelativeTransform (0x01195910); ToMatrixWithScale twice, the out-of-line
//   FMatrix::Inverse (0x00696430) and FQuat(const FMatrix&) (0x00569390), and its own thread-safe STolerance.
void FTransform::GetRelativeTransformUsingMatrixWithScale(FTransform* OutTransform, const FTransform* Base, const FTransform* Relative)
{
	// the goal of using M is to get the correct orientation
	// but for translation, we still need scale
	FMatrix AM = Base->ToMatrixWithScale();
	FMatrix BM = Relative->ToMatrixWithScale();
	// get combined scale
	// Scale = S(A)/S(B)
	static ScalarRegister STolerance(SMALL_NUMBER);
	VectorRegister VSafeScale3D = VectorSet_W0(GetSafeScaleReciprocal(Relative->Scale3D, STolerance));
	VectorRegister VScale3D = VectorMultiply(Base->Scale3D, VSafeScale3D);
	ConstructTransformFromMatrixWithDesiredScale(AM, BM.Inverse(), VScale3D, *OutTransform);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01195910 (end 0x01195BCE)
// Original VA: 0x0000000141195910 | File offset: 0x01194F10
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by execConvertTransformToRelative (UKismetMathLibrary::ConvertTransformToRelative inlined);
//   IsRotationNormalized, FTransform::Identity (0x046A0E80) for an unnormalized rotation, the
//   thread-safe STolerance and GetRelativeTransformUsingMatrixWithScale (0x01195D10) for negative scales.
FTransform FTransform::GetRelativeTransform(const FTransform& Other) const
{
	// A * B(-1) = VQS(B)(-1) (VQS (A))
	//
	// Scale = S(A)/S(B)
	// Rotation = Q(B)(-1) * Q(A)
	// Translation = 1/S(B) *[Q(B)(-1)*(T(A)-T(B))*Q(B)]
	// where A = this, B = Other
	FTransform Result;

	if (Other.IsRotationNormalized() == false)
	{
		return FTransform::Identity;
	}

	if (Private_AnyHasNegativeScale(this->Scale3D, Other.Scale3D))
	{
		// @note, if you have 0 scale with negative, you're going to lose rotation as it can't convert back to quat
		GetRelativeTransformUsingMatrixWithScale(&Result, this, &Other);
	}
	else
	{
		// Scale = S(A)/S(B)
		static ScalarRegister STolerance(SMALL_NUMBER);
		VectorRegister VSafeScale3D = VectorSet_W0(GetSafeScaleReciprocal(Other.Scale3D, STolerance));

		VectorRegister VScale3D = VectorMultiply(Scale3D, VSafeScale3D);

		//VQTranslation = (  ( T(A).X - T(B).X ),  ( T(A).Y - T(B).Y ), ( T(A).Z - T(B).Z), 0.f );
		VectorRegister VQTranslation = VectorSet_W0(VectorSubtract(Translation, Other.Translation));

		// Inverse RotatedTranslation
		VectorRegister VInverseRot = VectorQuaternionInverse(Other.Rotation);
		VectorRegister VR = VectorQuaternionRotateVector(VInverseRot, VQTranslation);

		//Translation = 1/S(B)
		VectorRegister VTranslation = VectorMultiply(VR, VSafeScale3D);

		// Rotation = Q(B)(-1) * Q(A)
		VectorRegister VRotation = VectorQuaternionMultiply2(VInverseRot, Rotation);

		Result.Scale3D = VScale3D;
		Result.Translation = VTranslation;
		Result.Rotation = VRotation;
	}

	return Result;
}
