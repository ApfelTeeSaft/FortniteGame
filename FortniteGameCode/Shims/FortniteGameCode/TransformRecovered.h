// FTransform and the vector helpers its constructors use, from the UE4.20 headers: Core's
// Math/UnrealMathSSE.h and TransformVectorized.h. Not recovered code.
//
// Its default constructor reads GlobalVectorConstants::FloatOne and XYZMask, which each unity
// unit defines itself (VectorRecovered.h). tools/codegen/unity.py includes this after a unit's
// constants, in the units that have both.
#pragma once

#include "FortniteGameCode/VectorRecovered.h"
#include "FortniteGameCode/AxisRecovered.h"

struct FQuat;   // MathDecls.h; the unity units include this header before it
struct FVector;
struct FMatrix;
struct FRotator;
class ScalarRegister;   // QuatRecovered.h

#define VectorZero()					_mm_setzero_ps()
#define VectorOne()						(GlobalVectorConstants::FloatOne)
#define VectorSet_W0( Vec )		_mm_and_ps( Vec, GlobalVectorConstants::XYZMask )

__forceinline VectorRegister VectorSet_W1( const VectorRegister& Vector )
{
	// Temp = (Vector[2]. Vector[3], 1.0f, 1.0f)
	VectorRegister Temp = _mm_movehl_ps( VectorOne(), Vector );

	// Return (Vector[0], Vector[1], Vector[2], 1.0f)
	return _mm_shuffle_ps( Vector, Temp, SHUFFLEMASK(0,1,0,3) );
}

// Math/TransformVectorized.h. noexport: no StaticStruct. DiagnosticCheckNaN_All() is empty in
// shipping (ENABLE_NAN_DIAGNOSTIC 0).
__declspec(align(16)) struct FTransform
{
protected:
	VectorRegister	Rotation;
	VectorRegister	Translation;
	VectorRegister Scale3D;
public:
	__forceinline FTransform()
	{
		// Rotation = {0,0,0,1)
		Rotation = VectorSet_W1( VectorZero() );
		// Translation = {0,0,0,0)
		Translation = VectorZero();
		// Scale3D = {1,1,1,0);
		Scale3D = VectorSet_W0( VectorOne() );
	}

	__forceinline FTransform(const FTransform& InTransform) :
		Rotation(InTransform.Rotation),
		Translation(InTransform.Translation),
		Scale3D(InTransform.Scale3D)
	{
	}

	__forceinline FTransform& operator=(const FTransform& Other)
	{
		this->Rotation = Other.Rotation;
		this->Translation = Other.Translation;
		this->Scale3D = Other.Scale3D;

		return *this;
	}

	// QuatRecovered.h
	FQuat GetRotation() const;
	FQuat TransformRotation(const FQuat& Q) const;
	FQuat InverseTransformRotation(const FQuat& Q) const;
	void ToMatrixInternal( VectorRegister& OutDiagonals, VectorRegister& OutAdds, VectorRegister& OutSubtracts ) const;
	FMatrix ToMatrixWithScale() const;
	FVector InverseTransformPosition(const FVector &V) const;
	// The default Tolerance (ScalarRegister(GlobalVectorConstants::SmallNumber)) is given with the
	// definition, after the unit's constants.
	static VectorRegister GetSafeScaleReciprocal(const VectorRegister& InScale, const ScalarRegister& Tolerance);
	FTransform(const FQuat& InRotation, const FVector& InTranslation, const FVector& InScale3D);
	void NormalizeRotation();
	void Blend(const FTransform& Atom1, const FTransform& Atom2, float Alpha);
	FRotator Rotator() const;
	void SetRotation(const FQuat& NewRotation);
	void SetTranslation(const FVector& NewTranslation);
	void SetScale3D(const FVector& NewScale3D);
	FVector GetTranslation() const;
	FVector GetScale3D() const;
#if FNGC_CORE_MATH_EXTRAS   // MathDecls.h
	static const FTransform Identity;   // CORE_API, Math/TransformVectorized.cpp
	FTransform GetRelativeTransform(const FTransform& Other) const;
	FTransform GetRelativeTransformReverse(const FTransform& Other) const;
	void SetToRelativeTransform(const FTransform& ParentTransform);
	static void GetRelativeTransformUsingMatrixWithScale(FTransform* OutTransform, const FTransform* Base, const FTransform* Relative);
	static void ConstructTransformFromMatrixWithDesiredScale(const FMatrix& AMatrix, const FMatrix& BMatrix, const VectorRegister& DesiredScale, FTransform& OutTransform);
	bool IsRotationNormalized() const;
private:
	static bool Private_AnyHasNegativeScale(const VectorRegister& InScale3D, const  VectorRegister& InOtherScale3D);
public:
#endif
	FVector TransformVectorNoScale(const FVector& V) const;
	FVector GetUnitAxis( EAxis::Type InAxis ) const;
};
