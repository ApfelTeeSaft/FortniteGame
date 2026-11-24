// The VectorRegister parts of FQuat and FTransform's rotation helpers, from the UE4.20 headers:
// Core's Math/UnrealMathSSE.h, Quat.h and TransformVectorized.h. Not recovered code.
//
// They read the unit's GlobalVectorConstants (QMULTI_SIGN_MASK0-2, FloatOneHalf, Float0001;
// FRotator's normalization Float360 and Float180; VectorSinCos OneOverTwoPi, TwoPi, SignBit, Pi,
// SignMask, PiByTwo, FloatMinusOne, FloatOne), so
// a unit includes this after defining them, as each original unity file has its own copies, and
// after TransformRecovered.h (no shim header includes that one: tools/matching/selftest.py).
#pragma once

#include "FortniteGameCode/VectorRecovered.h"
#include "FortniteGameCode/MathDecls.h"

#define VectorLoadAligned( Ptr )		_mm_load_ps( (float*)(Ptr) )
#define VectorStoreAligned( Vec, Ptr )	_mm_store_ps( (float*)(Ptr), Vec )
#define VectorLoadFloat1( Ptr )			_mm_load1_ps( (float*)(Ptr) )
#define VectorReplicate( Vec, ElementIndex )	_mm_shuffle_ps( Vec, Vec, SHUFFLEMASK(ElementIndex,ElementIndex,ElementIndex,ElementIndex) )
#define VectorSwizzle( Vec, X, Y, Z, W )	_mm_shuffle_ps( Vec, Vec, SHUFFLEMASK(X,Y,Z,W) )
#define VectorAdd( Vec1, Vec2 )			_mm_add_ps( Vec1, Vec2 )
#define VectorSubtract( Vec1, Vec2 )	_mm_sub_ps( Vec1, Vec2 )
#define VectorMultiply( Vec1, Vec2 )	_mm_mul_ps( Vec1, Vec2 )
#define VectorMultiplyAdd( Vec1, Vec2, Vec3 )	_mm_add_ps( _mm_mul_ps(Vec1, Vec2), Vec3 )
#define VectorCompareGE( Vec1, Vec2 )			_mm_cmpge_ps( Vec1, Vec2 )
#define VectorReciprocalSqrt(Vec)		_mm_rsqrt_ps( Vec )
#define VectorDivide( Vec1, Vec2 )		_mm_div_ps( Vec1, Vec2 )
#define VectorCompareGT( Vec1, Vec2 )			_mm_cmpgt_ps( Vec1, Vec2 )
#define VectorAbs( Vec )				_mm_and_ps(Vec, GlobalVectorConstants::SignMask)
#define VectorBitwiseOr(Vec1, Vec2)	_mm_or_ps(Vec1, Vec2)
#define VectorBitwiseAnd(Vec1, Vec2) _mm_and_ps(Vec1, Vec2)
#define VectorBitwiseXor(Vec1, Vec2) _mm_xor_ps(Vec1, Vec2)
#define VectorShuffle( Vec1, Vec2, X, Y, Z, W )	_mm_shuffle_ps( Vec1, Vec2, SHUFFLEMASK(X,Y,Z,W) )
#define VectorLoadFloat3_W0( Ptr )		MakeVectorRegister( ((const float*)(Ptr))[0], ((const float*)(Ptr))[1], ((const float*)(Ptr))[2], 0.0f )
#define VectorAnyGreaterThan( Vec1, Vec2 )		_mm_movemask_ps( _mm_cmpgt_ps(Vec1, Vec2) )

__forceinline void VectorStoreFloat3( const VectorRegister& Vec, void* Ptr )
{
	union { VectorRegister v; float f[4]; } Tmp;
	Tmp.v = Vec;
	float* FloatPtr = (float*)(Ptr);
	FloatPtr[0] = Tmp.f[0];
	FloatPtr[1] = Tmp.f[1];
	FloatPtr[2] = Tmp.f[2];
}

__forceinline VectorRegister VectorTruncate(const VectorRegister& X)
{
	return _mm_cvtepi32_ps(_mm_cvttps_epi32(X));
}

__forceinline VectorRegister VectorMod(const VectorRegister& X, const VectorRegister& Y)
{
	VectorRegister Temp = VectorTruncate(VectorDivide(X, Y));
	return VectorSubtract(X, VectorMultiply(Y, Temp));
}

__forceinline VectorRegister VectorDot4( const VectorRegister& Vec1, const VectorRegister& Vec2 )
{
	VectorRegister Temp1, Temp2;
	Temp1 = VectorMultiply( Vec1, Vec2 );
	Temp2 = _mm_shuffle_ps( Temp1, Temp1, SHUFFLEMASK(2,3,0,1) );	// (Z,W,X,Y).
	Temp1 = VectorAdd( Temp1, Temp2 );								// (X*X + Z*Z, Y*Y + W*W, Z*Z + X*X, W*W + Y*Y)
	Temp2 = _mm_shuffle_ps( Temp1, Temp1, SHUFFLEMASK(1,2,3,0) );	// Rotate left 4 bytes (Y,Z,W,X).
	return VectorAdd( Temp1, Temp2 );								// (X*X + Z*Z + Y*Y + W*W, Y*Y + W*W + Z*Z + X*X, Z*Z + X*X + W*W + Y*Y, W*W + Y*Y + X*X + Z*Z)
}

__forceinline VectorRegister VectorSelect(const VectorRegister& Mask, const VectorRegister& Vec1, const VectorRegister& Vec2 )
{
	return _mm_xor_ps( Vec2, _mm_and_ps( Mask, _mm_xor_ps( Vec1, Vec2 ) ) );
}

__forceinline VectorRegister VectorReciprocalSqrtAccurate(const VectorRegister& Vec)
{
	// Perform two passes of Newton-Raphson iteration on the hardware estimate
	const VectorRegister OneHalf = GlobalVectorConstants::FloatOneHalf;
	const VectorRegister VecDivBy2 = VectorMultiply(Vec, OneHalf);

	// Initial estimate
	const VectorRegister x0 = VectorReciprocalSqrt(Vec);

	// First iteration
	VectorRegister x1 = VectorMultiply(x0, x0);
	x1 = VectorSubtract(OneHalf, VectorMultiply(VecDivBy2, x1));
	x1 = VectorMultiplyAdd(x0, x1, x0);

	// Second iteration
	VectorRegister x2 = VectorMultiply(x1, x1);
	x2 = VectorSubtract(OneHalf, VectorMultiply(VecDivBy2, x2));
	x2 = VectorMultiplyAdd(x1, x2, x1);

	return x2;
}

// Math/UnrealMathVectorCommon.h
__forceinline VectorRegister VectorNormalizeRotator(const VectorRegister& UnnormalizedRotator)
{
	// shift in the range [-360,360]
	VectorRegister V0	= VectorMod( UnnormalizedRotator, GlobalVectorConstants::Float360);
	VectorRegister V1	= VectorAdd( V0, GlobalVectorConstants::Float360 );
	VectorRegister V2	= VectorSelect(VectorCompareGE(V0, VectorZero()), V0, V1);

	// shift to [-180,180]
	VectorRegister V3	= VectorSubtract( V2, GlobalVectorConstants::Float360 );
	VectorRegister V4	= VectorSelect(VectorCompareGT(V2, GlobalVectorConstants::Float180), V3, V2);

	return  V4;
}

__forceinline void VectorSinCos(VectorRegister* __restrict VSinAngles, VectorRegister* __restrict VCosAngles, const VectorRegister* __restrict VAngles)
{
	// Map to [-pi, pi]
	// X = A - 2pi * round(A/2pi)
	// Note the round(), not truncate(). In this case round() can round halfway cases using round-to-nearest-even OR round-to-nearest.

	// Quotient = round(A/2pi)
	VectorRegister Quotient = VectorMultiply(*VAngles, GlobalVectorConstants::OneOverTwoPi);
	Quotient = _mm_cvtepi32_ps(_mm_cvtps_epi32(Quotient)); // round to nearest even is the default rounding mode but that's fine here.
	// X = A - 2pi * Quotient
	VectorRegister X = VectorSubtract(*VAngles, VectorMultiply(GlobalVectorConstants::TwoPi, Quotient));

	// Map in [-pi/2,pi/2]
	VectorRegister sign = VectorBitwiseAnd(X, GlobalVectorConstants::SignBit);
	VectorRegister c = VectorBitwiseOr(GlobalVectorConstants::Pi, sign);  // pi when x >= 0, -pi when x < 0
	VectorRegister absx = VectorAbs(X);
	VectorRegister rflx = VectorSubtract(c, X);
	VectorRegister comp = VectorCompareGT(absx, GlobalVectorConstants::PiByTwo);
	X = VectorSelect(comp, rflx, X);
	sign = VectorSelect(comp, GlobalVectorConstants::FloatMinusOne, GlobalVectorConstants::FloatOne);

	const VectorRegister XSquared = VectorMultiply(X, X);

	// 11-degree minimax approximation
	//*ScalarSin = (((((-2.3889859e-08f * y2 + 2.7525562e-06f) * y2 - 0.00019840874f) * y2 + 0.0083333310f) * y2 - 0.16666667f) * y2 + 1.0f) * y;
	const VectorRegister SinCoeff0 = MakeVectorRegister(1.0f, -0.16666667f, 0.0083333310f, -0.00019840874f);
	const VectorRegister SinCoeff1 = MakeVectorRegister(2.7525562e-06f, -2.3889859e-08f, /*unused*/ 0.f, /*unused*/ 0.f);

	VectorRegister S;
	S = VectorReplicate(SinCoeff1, 1);
	S = VectorMultiplyAdd(XSquared, S, VectorReplicate(SinCoeff1, 0));
	S = VectorMultiplyAdd(XSquared, S, VectorReplicate(SinCoeff0, 3));
	S = VectorMultiplyAdd(XSquared, S, VectorReplicate(SinCoeff0, 2));
	S = VectorMultiplyAdd(XSquared, S, VectorReplicate(SinCoeff0, 1));
	S = VectorMultiplyAdd(XSquared, S, VectorReplicate(SinCoeff0, 0));
	*VSinAngles = VectorMultiply(S, X);

	// 10-degree minimax approximation
	//*ScalarCos = sign * (((((-2.6051615e-07f * y2 + 2.4760495e-05f) * y2 - 0.0013888378f) * y2 + 0.041666638f) * y2 - 0.5f) * y2 + 1.0f);
	const VectorRegister CosCoeff0 = MakeVectorRegister(1.0f, -0.5f, 0.041666638f, -0.0013888378f);
	const VectorRegister CosCoeff1 = MakeVectorRegister(2.4760495e-05f, -2.6051615e-07f, /*unused*/ 0.f, /*unused*/ 0.f);

	VectorRegister C;
	C = VectorReplicate(CosCoeff1, 1);
	C = VectorMultiplyAdd(XSquared, C, VectorReplicate(CosCoeff1, 0));
	C = VectorMultiplyAdd(XSquared, C, VectorReplicate(CosCoeff0, 3));
	C = VectorMultiplyAdd(XSquared, C, VectorReplicate(CosCoeff0, 2));
	C = VectorMultiplyAdd(XSquared, C, VectorReplicate(CosCoeff0, 1));
	C = VectorMultiplyAdd(XSquared, C, VectorReplicate(CosCoeff0, 0));
	*VCosAngles = VectorMultiply(C, sign);
}

__forceinline VectorRegister VectorQuaternionMultiply2( const VectorRegister& Quat1, const VectorRegister& Quat2 )
{
	VectorRegister Result = VectorMultiply(VectorReplicate(Quat1, 3), Quat2);
	Result = VectorMultiplyAdd( VectorMultiply(VectorReplicate(Quat1, 0), VectorSwizzle(Quat2, 3,2,1,0)), GlobalVectorConstants::QMULTI_SIGN_MASK0, Result);
	Result = VectorMultiplyAdd( VectorMultiply(VectorReplicate(Quat1, 1), VectorSwizzle(Quat2, 2,3,0,1)), GlobalVectorConstants::QMULTI_SIGN_MASK1, Result);
	Result = VectorMultiplyAdd( VectorMultiply(VectorReplicate(Quat1, 2), VectorSwizzle(Quat2, 1,0,3,2)), GlobalVectorConstants::QMULTI_SIGN_MASK2, Result);

	return Result;
}

__forceinline void VectorQuaternionMultiply( void* __restrict Result, const void* __restrict Quat1, const void* __restrict Quat2)
{
	*((VectorRegister *)Result) = VectorQuaternionMultiply2(*((const VectorRegister *)Quat1), *((const VectorRegister *)Quat2));
}

__forceinline FQuat FQuat::operator*( const FQuat& Q ) const
{
	FQuat Result;
	VectorQuaternionMultiply(&Result, this, &Q);

	return Result;
}

__forceinline void FQuat::Normalize(float Tolerance)
{
	const VectorRegister Vector = VectorLoadAligned(this);

	const VectorRegister SquareSum = VectorDot4(Vector, Vector);
	const VectorRegister NonZeroMask = VectorCompareGE(SquareSum, VectorLoadFloat1(&Tolerance));
	const VectorRegister InvLength = VectorReciprocalSqrtAccurate(SquareSum);
	const VectorRegister NormalizedVector = VectorMultiply(InvLength, Vector);
	VectorRegister Result = VectorSelect(NonZeroMask, NormalizedVector, GlobalVectorConstants::Float0001);

	VectorStoreAligned(Result, this);
}

__forceinline FQuat FQuat::GetNormalized(float Tolerance) const
{
	FQuat Result(*this);
	Result.Normalize(Tolerance);
	return Result;
}

__forceinline FQuat FQuat::Slerp(const FQuat &Quat1, const FQuat &Quat2, float Slerp)
{
	// Slerp_NotNormalized is just Slerp without the normalization
	return Slerp_NotNormalized(Quat1, Quat2, Slerp).GetNormalized();
}

__forceinline FQuat FQuat::SlerpFullPath(const FQuat &quat1, const FQuat &quat2, float Alpha)
{
	return SlerpFullPath_NotNormalized(quat1, quat2, Alpha).GetNormalized();
}

// Math/Rotator.h (PLATFORM_ENABLE_VECTORINTRINSICS); DiagnosticCheckNaN() is empty in shipping.
__forceinline void FRotator::Normalize()
{
	VectorRegister VRotator = VectorLoadFloat3_W0(this);
	VRotator = VectorNormalizeRotator(VRotator);
	VectorStoreFloat3(VRotator, this);
}

__forceinline FRotator FRotator::GetNormalized() const
{
	FRotator Rot = *this;
	Rot.Normalize();
	return Rot;
}

__forceinline bool FRotator::IsNearlyZero(float Tolerance) const
{
	const VectorRegister RegA = VectorLoadFloat3_W0(this);
	const VectorRegister Norm = VectorNormalizeRotator(RegA);
	const VectorRegister AbsNorm = VectorAbs(Norm);
	return !VectorAnyGreaterThan(AbsNorm, VectorLoadFloat1(&Tolerance));
}

__forceinline FQuat FTransform::GetRotation() const
{
	FQuat OutRotation;
	VectorStoreAligned(Rotation, &OutRotation);
	return OutRotation;
}

__forceinline FQuat FTransform::TransformRotation(const FQuat& Q) const
{
	return GetRotation() * Q;
}

__forceinline FQuat FTransform::InverseTransformRotation(const FQuat& Q) const
{
	return GetRotation().Inverse() * Q;
}
