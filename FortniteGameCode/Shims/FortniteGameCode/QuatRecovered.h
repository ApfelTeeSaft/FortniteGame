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
#define VectorReciprocal(Vec)			_mm_rcp_ps(Vec)

// Math/ScalarRegister.h
class ScalarRegister
{
public:
	VectorRegister Value;

	__forceinline ScalarRegister() { }
	__forceinline ScalarRegister(const ScalarRegister& VectorValue) { Value = VectorValue.Value; }
	explicit __forceinline ScalarRegister(const float& ScalarValue) { Value = VectorLoadFloat1(&ScalarValue); }
	explicit __forceinline ScalarRegister(VectorRegister VectorValue) { Value = VectorValue; }
};

__forceinline VectorRegister VectorReciprocalAccurate(const VectorRegister& Vec)
{
	// Perform two passes of Newton-Raphson iteration on the hardware estimate
	// Initial estimate
	const VectorRegister x0 = VectorReciprocal(Vec);

	// First iteration
	const VectorRegister x0Squared = VectorMultiply(x0, x0);
	const VectorRegister x0Times2 = VectorAdd(x0, x0);
	const VectorRegister x1 = VectorSubtract(x0Times2, VectorMultiply(Vec, x0Squared));

	// Second iteration
	const VectorRegister x1Squared = VectorMultiply(x1, x1);
	const VectorRegister x1Times2 = VectorAdd(x1, x1);
	const VectorRegister x2 = VectorSubtract(x1Times2, VectorMultiply(Vec, x1Squared));

	return x2;
}

__forceinline VectorRegister VectorCross( const VectorRegister& Vec1, const VectorRegister& Vec2 )
{
	VectorRegister A_YZXW = _mm_shuffle_ps( Vec1, Vec1, SHUFFLEMASK(1,2,0,3) );
	VectorRegister B_ZXYW = _mm_shuffle_ps( Vec2, Vec2, SHUFFLEMASK(2,0,1,3) );
	VectorRegister A_ZXYW = _mm_shuffle_ps( Vec1, Vec1, SHUFFLEMASK(2,0,1,3) );
	VectorRegister B_YZXW = _mm_shuffle_ps( Vec2, Vec2, SHUFFLEMASK(1,2,0,3) );
	return VectorSubtract( VectorMultiply(A_YZXW,B_ZXYW), VectorMultiply(A_ZXYW, B_YZXW) );
}

// Math/UnrealMathVectorCommon.h
__forceinline VectorRegister VectorQuaternionInverse(const VectorRegister& NormalizedQuat)
{
	return VectorMultiply(GlobalVectorConstants::QINV_SIGN_MASK, NormalizedQuat);
}

__forceinline VectorRegister VectorQuaternionRotateVector(const VectorRegister& Quat, const VectorRegister& VectorW0)
{
	// Q * V * Q.Inverse
	// V' = V + w*(T) + (Q x T), T = 2(Q x V)
	const VectorRegister QW = VectorReplicate(Quat, 3);
	VectorRegister T = VectorCross(Quat, VectorW0);
	T = VectorAdd(T, T);
	const VectorRegister VTemp0 = VectorMultiplyAdd(QW, T, VectorW0);
	const VectorRegister VTemp1 = VectorCross(Quat, T);
	const VectorRegister Rotated = VectorAdd(VTemp0, VTemp1);
	return Rotated;
}

__forceinline VectorRegister VectorQuaternionInverseRotateVector(const VectorRegister& Quat, const VectorRegister& VectorW0)
{
	// Q.Inverse * V * Q
	const VectorRegister QInv = VectorQuaternionInverse(Quat);
	return VectorQuaternionRotateVector(QInv, VectorW0);
}

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

__forceinline VectorRegister VectorReciprocalSqrtAccurate(const VectorRegister& Vec);

__forceinline VectorRegister VectorNormalizeSafe( const VectorRegister& Vector, const VectorRegister& DefaultValue )
{
	const VectorRegister SquareSum = VectorDot4(Vector, Vector);
	const VectorRegister NonZeroMask = VectorCompareGE(SquareSum, GlobalVectorConstants::SmallLengthThreshold);
	const VectorRegister InvLength = VectorReciprocalSqrtAccurate(SquareSum);
	const VectorRegister NormalizedVector = VectorMultiply(InvLength, Vector);
	return VectorSelect(NonZeroMask, NormalizedVector, DefaultValue);
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

__forceinline VectorRegister VectorNormalizeSafe( const VectorRegister& Vector, const VectorRegister& DefaultValue );

__forceinline VectorRegister VectorNormalizeQuaternion(const VectorRegister& UnnormalizedQuat)
{
	return VectorNormalizeSafe(UnnormalizedQuat, GlobalVectorConstants::Float0001);
}

__forceinline VectorRegister VectorLerpQuat(const VectorRegister& A, const VectorRegister& B, const VectorRegister& Alpha)
{
	// Blend rotation
	//     To ensure the 'shortest route', we make sure the dot product between the both rotations is positive.
	//     const float Bias = (|A.B| >= 0 ? 1 : -1)
	//     BlendedAtom.Rotation = (B * Alpha) + (A * (Bias * (1.f - Alpha)));
	//     BlendedAtom.Rotation.QuaternionNormalize();
	//  Note: A and B are flipped from the reference implementation, so that this function
	//  matches FMath::Lerp(A, B, Alpha) (and BiasedQuatLerp()), which is required by other code.
	const VectorRegister Zero = VectorZero();

	const VectorRegister OneMinusAlpha = VectorSubtract(VectorOne(), Alpha);

	const VectorRegister RotationDot = VectorDot4(A, B);
	const VectorRegister QuatRotationDirMask = VectorCompareGE(RotationDot, Zero);
	const VectorRegister NegativeA = VectorSubtract(Zero, A);
	const VectorRegister BiasTimesA = VectorSelect(QuatRotationDirMask, A, NegativeA);
	const VectorRegister BTimesWeight = VectorMultiply(B, Alpha);
	const VectorRegister UnnormalizedResult = VectorMultiplyAdd(BiasTimesA, OneMinusAlpha, BTimesWeight);

	return UnnormalizedResult;
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

// Math/TransformVectorized.h
__forceinline void FTransform::ToMatrixInternal( VectorRegister& OutDiagonals, VectorRegister& OutAdds, VectorRegister& OutSubtracts ) const
{
	const VectorRegister RotationX2Y2Z2 = VectorAdd(Rotation, Rotation);	// x2, y2, z2
	const VectorRegister RotationXX2YY2ZZ2 = VectorMultiply(RotationX2Y2Z2, Rotation);	// xx2, yy2, zz2

	// The diagonal terms of the rotation matrix are:
	//   (1 - (yy2 + zz2)) * scale
	//   (1 - (xx2 + zz2)) * scale
	//   (1 - (xx2 + yy2)) * scale
	const VectorRegister yy2_xx2_xx2 = VectorSwizzle(RotationXX2YY2ZZ2, 1, 0, 0, 0);
	const VectorRegister zz2_zz2_yy2 = VectorSwizzle(RotationXX2YY2ZZ2, 2, 2, 1, 0);
	const VectorRegister DiagonalSum = VectorAdd(yy2_xx2_xx2, zz2_zz2_yy2);
	const VectorRegister Diagonals = VectorSubtract(VectorOne(), DiagonalSum);
	OutDiagonals = VectorMultiply(Diagonals, Scale3D);

	// Grouping the non-diagonal elements in the rotation block by operations:
	//    ((x*y2,y*z2,x*z2) + (w*z2,w*x2,w*y2)) * scale.xyz and
	//    ((x*y2,y*z2,x*z2) - (w*z2,w*x2,w*y2)) * scale.yxz
	// Rearranging so the LHS and RHS are in the same order as for +
	//    ((x*y2,y*z2,x*z2) - (w*z2,w*x2,w*y2)) * scale.yxz

	// RotBase = x*y2, y*z2, x*z2
	// RotOffset = w*z2, w*x2, w*y2
	const VectorRegister x_y_x = VectorSwizzle(Rotation, 0, 1, 0, 0);
	const VectorRegister y2_z2_z2 = VectorSwizzle(RotationX2Y2Z2, 1, 2, 2, 0);
	const VectorRegister RotBase = VectorMultiply(x_y_x, y2_z2_z2);

	const VectorRegister w_w_w = VectorReplicate(Rotation, 3);
	const VectorRegister z2_x2_y2 = VectorSwizzle(RotationX2Y2Z2, 2, 0, 1, 0);
	const VectorRegister RotOffset = VectorMultiply(w_w_w, z2_x2_y2);

	// Adds = (RotBase + RotOffset)*Scale3D :  (x*y2 + w*z2) * Scale3D.X , (y*z2 + w*x2) * Scale3D.Y, (x*z2 + w*y2) * Scale3D.Z
	// Subtracts = (RotBase - RotOffset)*Scale3DYZX :  (x*y2 - w*z2) * Scale3D.Y , (y*z2 - w*x2) * Scale3D.Z, (x*z2 - w*y2) * Scale3D.X
	const VectorRegister Adds = VectorAdd(RotBase, RotOffset);
	OutAdds = VectorMultiply(Adds, Scale3D);
	const VectorRegister Scale3DYZXW = VectorSwizzle( Scale3D, 1, 2, 0, 3);
	const VectorRegister Subtracts = VectorSubtract(RotBase, RotOffset);
	OutSubtracts = VectorMultiply(Subtracts , Scale3DYZXW);
}

__forceinline FMatrix FTransform::ToMatrixWithScale() const
{
	FMatrix OutMatrix;
	VectorRegister DiagonalsXYZ;
	VectorRegister Adds;
	VectorRegister Subtracts;

	ToMatrixInternal( DiagonalsXYZ, Adds, Subtracts );
	const VectorRegister DiagonalsXYZ_W0 = VectorSet_W0(DiagonalsXYZ);

	// OutMatrix.M[0][0] = (1.0f - (yy2 + zz2)) * Scale.X;    // Diagonal.X
	// OutMatrix.M[0][1] = (xy2 + wz2) * Scale.X;             // Adds.X
	// OutMatrix.M[0][2] = (xz2 - wy2) * Scale.X;             // Subtracts.Z
	// OutMatrix.M[0][3] = 0.0f;                              // DiagonalsXYZ_W0.W
	const VectorRegister AddX_DC_DiagX_DC = VectorShuffle(Adds, DiagonalsXYZ_W0, 0, 0, 0, 0);
	const VectorRegister SubZ_DC_DiagW_DC = VectorShuffle(Subtracts, DiagonalsXYZ_W0, 2, 0, 3, 0);
	const VectorRegister Row0 = VectorShuffle(AddX_DC_DiagX_DC, SubZ_DC_DiagW_DC, 2, 0, 0, 2);

	// OutMatrix.M[1][0] = (xy2 - wz2) * Scale.Y;             // Subtracts.X
	// OutMatrix.M[1][1] = (1.0f - (xx2 + zz2)) * Scale.Y;    // Diagonal.Y
	// OutMatrix.M[1][2] = (yz2 + wx2) * Scale.Y;             // Adds.Y
	// OutMatrix.M[1][3] = 0.0f;                              // DiagonalsXYZ_W0.W
	const VectorRegister SubX_DC_DiagY_DC = VectorShuffle(Subtracts, DiagonalsXYZ_W0, 0, 0, 1, 0);
	const VectorRegister AddY_DC_DiagW_DC = VectorShuffle(Adds, DiagonalsXYZ_W0, 1, 0, 3, 0);
	const VectorRegister Row1 = VectorShuffle(SubX_DC_DiagY_DC, AddY_DC_DiagW_DC, 0, 2, 0, 2);

	// OutMatrix.M[2][0] = (xz2 + wy2) * Scale.Z;             // Adds.Z
	// OutMatrix.M[2][1] = (yz2 - wx2) * Scale.Z;             // Subtracts.Y
	// OutMatrix.M[2][2] = (1.0f - (xx2 + yy2)) * Scale.Z;    // Diagonals.Z
	// OutMatrix.M[2][3] = 0.0f;                              // DiagonalsXYZ_W0.W
	const VectorRegister AddZ_DC_SubY_DC = VectorShuffle(Adds, Subtracts, 2, 0, 1, 0);
	const VectorRegister Row2 = VectorShuffle(AddZ_DC_SubY_DC, DiagonalsXYZ_W0, 0, 2, 2, 3);

	VectorStoreAligned(Row0, &(OutMatrix.M[0][0]));
	VectorStoreAligned(Row1, &(OutMatrix.M[1][0]));
	VectorStoreAligned(Row2, &(OutMatrix.M[2][0]));

	// OutMatrix.M[3][0] = Translation.X;
	// OutMatrix.M[3][1] = Translation.Y;
	// OutMatrix.M[3][2] = Translation.Z;
	// OutMatrix.M[3][3] = 1.0f;
	const VectorRegister Row3 = VectorSet_W1(Translation);
	VectorStoreAligned(Row3, &(OutMatrix.M[3][0]));

	return OutMatrix;
}

__forceinline VectorRegister FTransform::GetSafeScaleReciprocal(const VectorRegister& InScale, const ScalarRegister& Tolerance = ScalarRegister(GlobalVectorConstants::SmallNumber))
{
	// SafeReciprocalScale.X = (InScale.X == 0) ? 0.f : 1/InScale.X; // same for YZW
	VectorRegister SafeReciprocalScale;

	/// VectorRegister( 1.0f / InScale.x, 1.0f / InScale.y, 1.0f / InScale.z, 1.0f / InScale.w )
	const VectorRegister ReciprocalScale = VectorReciprocalAccurate(InScale);

	//VectorRegister( Vec1.x == Vec2.x ? 0xFFFFFFFF : 0, same for yzw )
	const VectorRegister ScaleZeroMask = VectorCompareGE(Tolerance.Value, VectorAbs(InScale));

	// VectorRegister( for each bit i: Mask[i] ? Vec1[i] : Vec2[i] )
	SafeReciprocalScale = VectorSelect(ScaleZeroMask, VectorZero(), ReciprocalScale);

	return SafeReciprocalScale;
}

__forceinline FVector FTransform::InverseTransformPosition(const FVector &V) const
{
	const VectorRegister InputVector = VectorLoadFloat3_W0(&V);

	// (V-Translation)
	const VectorRegister TranslatedVec = VectorSet_W0(VectorSubtract(InputVector, Translation));

	// ( Rotation.Inverse() * (V-Translation) )
	const VectorRegister VR = VectorQuaternionInverseRotateVector(Rotation, TranslatedVec);

	// GetSafeScaleReciprocal(Scale3D);
	const VectorRegister SafeReciprocal = GetSafeScaleReciprocal(Scale3D);

	// ( Rotation.Inverse() * (V-Translation) ) * GetSafeScaleReciprocal(Scale3D);
	const VectorRegister VResult = VectorMultiply(VR, SafeReciprocal);

	FVector Result;
	VectorStoreFloat3(VResult, &Result);
	return Result;
}

// Specialization of Lerp template that works with vector registers (UnrealMathVectorCommon.h)
template<> __forceinline VectorRegister FMath::Lerp(const VectorRegister& A, const VectorRegister& B, const VectorRegister& Alpha)
{
	const VectorRegister Delta = VectorSubtract(B, A);
	return VectorMultiplyAdd(Alpha, Delta, A);
}

__forceinline FTransform::FTransform(const FQuat& InRotation, const FVector& InTranslation, const FVector& InScale3D)
{
	// Rotation = InRotation
	Rotation =  VectorLoadAligned( &InRotation.X );
	// Translation = InTranslation
	Translation = MakeVectorRegister(InTranslation.X, InTranslation.Y, InTranslation.Z, 0.0f );
	// Scale3D = InScale3D
	Scale3D = MakeVectorRegister(InScale3D.X, InScale3D.Y, InScale3D.Z, 0.0f );
}

__forceinline void FTransform::NormalizeRotation()
{
	Rotation = VectorNormalizeQuaternion(Rotation);
}

__forceinline void FTransform::Blend(const FTransform& Atom1, const FTransform& Atom2, float Alpha)
{
	if( FMath::Abs(Alpha) <= ZERO_ANIMWEIGHT_THRESH )
	{
		// if blend is all the way for child1, then just copy its bone atoms
		(*this) = Atom1;
	}
	else if( FMath::Abs(Alpha - 1.0f) <= ZERO_ANIMWEIGHT_THRESH )
	{
		// if blend is all the way for child2, then just copy its bone atoms
		(*this) = Atom2;
	}
	else
	{
		// Simple linear interpolation for translation and scale.
		ScalarRegister BlendWeight = ScalarRegister(Alpha);

		Translation = FMath::Lerp(Atom1.Translation, Atom2.Translation, BlendWeight.Value);
		Scale3D = FMath::Lerp(Atom1.Scale3D, Atom2.Scale3D, BlendWeight.Value);

		VectorRegister VRotation = VectorLerpQuat(Atom1.Rotation, Atom2.Rotation, BlendWeight.Value);

		// ..and renormalize
		Rotation = VectorNormalizeQuaternion(VRotation);
	}
}

__forceinline FRotator FTransform::Rotator() const
{
	FQuat OutRotation;
	VectorStoreAligned(Rotation, &OutRotation);
	return OutRotation.Rotator();
}

__forceinline void FTransform::SetRotation(const FQuat& NewRotation)
{
	Rotation = VectorLoadAligned(&NewRotation);
}

__forceinline void FTransform::SetTranslation(const FVector& NewTranslation)
{
	Translation = VectorLoadFloat3_W0(&NewTranslation);
}

__forceinline void FTransform::SetScale3D(const FVector& NewScale3D)
{
	Scale3D = VectorLoadFloat3_W0(&NewScale3D);
}

__forceinline FVector FTransform::GetTranslation() const
{
	FVector OutTranslation;
	VectorStoreFloat3(Translation, &OutTranslation);
	return OutTranslation;
}

__forceinline FVector FTransform::GetScale3D() const
{
	FVector OutScale3D;
	VectorStoreFloat3(Scale3D, &OutScale3D);
	return OutScale3D;
}

#if FNGC_CORE_MATH_EXTRAS
#define VectorMin( Vec1, Vec2 )			_mm_min_ps( Vec1, Vec2 )

// Math/UnrealMathVectorCommon.h
__forceinline uint32 VectorAnyLesserThan( VectorRegister Vec1, VectorRegister Vec2 )
{
	return VectorAnyGreaterThan( Vec2, Vec1 );
}

__forceinline VectorRegister VectorSign(const VectorRegister& X)
{
	VectorRegister Mask = VectorCompareGE(X, (GlobalVectorConstants::FloatZero));
	return VectorSelect(Mask, (GlobalVectorConstants::FloatOne), (GlobalVectorConstants::FloatMinusOne));
}

__forceinline void VectorMatrixMultiply( void *Result, const void* Matrix1, const void* Matrix2 )
{
	const VectorRegister *A	= (const VectorRegister *) Matrix1;
	const VectorRegister *B	= (const VectorRegister *) Matrix2;
	VectorRegister *R		= (VectorRegister *) Result;
	VectorRegister Temp, R0, R1, R2, R3;

	// First row of result (Matrix1[0] * Matrix2).
	Temp	= VectorMultiply( VectorReplicate( A[0], 0 ), B[0] );
	Temp	= VectorMultiplyAdd( VectorReplicate( A[0], 1 ), B[1], Temp );
	Temp	= VectorMultiplyAdd( VectorReplicate( A[0], 2 ), B[2], Temp );
	R0		= VectorMultiplyAdd( VectorReplicate( A[0], 3 ), B[3], Temp );

	// Second row of result (Matrix1[1] * Matrix2).
	Temp	= VectorMultiply( VectorReplicate( A[1], 0 ), B[0] );
	Temp	= VectorMultiplyAdd( VectorReplicate( A[1], 1 ), B[1], Temp );
	Temp	= VectorMultiplyAdd( VectorReplicate( A[1], 2 ), B[2], Temp );
	R1		= VectorMultiplyAdd( VectorReplicate( A[1], 3 ), B[3], Temp );

	// Third row of result (Matrix1[2] * Matrix2).
	Temp	= VectorMultiply( VectorReplicate( A[2], 0 ), B[0] );
	Temp	= VectorMultiplyAdd( VectorReplicate( A[2], 1 ), B[1], Temp );
	Temp	= VectorMultiplyAdd( VectorReplicate( A[2], 2 ), B[2], Temp );
	R2		= VectorMultiplyAdd( VectorReplicate( A[2], 3 ), B[3], Temp );

	// Fourth row of result (Matrix1[3] * Matrix2).
	Temp	= VectorMultiply( VectorReplicate( A[3], 0 ), B[0] );
	Temp	= VectorMultiplyAdd( VectorReplicate( A[3], 1 ), B[1], Temp );
	Temp	= VectorMultiplyAdd( VectorReplicate( A[3], 2 ), B[2], Temp );
	R3		= VectorMultiplyAdd( VectorReplicate( A[3], 3 ), B[3], Temp );

	// Store result
	R[0] = R0;
	R[1] = R1;
	R[2] = R2;
	R[3] = R3;
}

// Math/UnrealMathSSE.h (scalar code, as in 4.20)
__forceinline void VectorMatrixInverse( void* DstMatrix, const void* SrcMatrix )
{
	typedef float Float4x4[4][4];
	const Float4x4& M = *((const Float4x4*) SrcMatrix);
	Float4x4 Result;
	float Det[4];
	Float4x4 Tmp;

	Tmp[0][0]	= M[2][2] * M[3][3] - M[2][3] * M[3][2];
	Tmp[0][1]	= M[1][2] * M[3][3] - M[1][3] * M[3][2];
	Tmp[0][2]	= M[1][2] * M[2][3] - M[1][3] * M[2][2];

	Tmp[1][0]	= M[2][2] * M[3][3] - M[2][3] * M[3][2];
	Tmp[1][1]	= M[0][2] * M[3][3] - M[0][3] * M[3][2];
	Tmp[1][2]	= M[0][2] * M[2][3] - M[0][3] * M[2][2];

	Tmp[2][0]	= M[1][2] * M[3][3] - M[1][3] * M[3][2];
	Tmp[2][1]	= M[0][2] * M[3][3] - M[0][3] * M[3][2];
	Tmp[2][2]	= M[0][2] * M[1][3] - M[0][3] * M[1][2];

	Tmp[3][0]	= M[1][2] * M[2][3] - M[1][3] * M[2][2];
	Tmp[3][1]	= M[0][2] * M[2][3] - M[0][3] * M[2][2];
	Tmp[3][2]	= M[0][2] * M[1][3] - M[0][3] * M[1][2];

	Det[0]		= M[1][1]*Tmp[0][0] - M[2][1]*Tmp[0][1] + M[3][1]*Tmp[0][2];
	Det[1]		= M[0][1]*Tmp[1][0] - M[2][1]*Tmp[1][1] + M[3][1]*Tmp[1][2];
	Det[2]		= M[0][1]*Tmp[2][0] - M[1][1]*Tmp[2][1] + M[3][1]*Tmp[2][2];
	Det[3]		= M[0][1]*Tmp[3][0] - M[1][1]*Tmp[3][1] + M[2][1]*Tmp[3][2];

	float Determinant = M[0][0]*Det[0] - M[1][0]*Det[1] + M[2][0]*Det[2] - M[3][0]*Det[3];
	const float	RDet = 1.0f / Determinant;

	Result[0][0] =  RDet * Det[0];
	Result[0][1] = -RDet * Det[1];
	Result[0][2] =  RDet * Det[2];
	Result[0][3] = -RDet * Det[3];
	Result[1][0] = -RDet * (M[1][0]*Tmp[0][0] - M[2][0]*Tmp[0][1] + M[3][0]*Tmp[0][2]);
	Result[1][1] =  RDet * (M[0][0]*Tmp[1][0] - M[2][0]*Tmp[1][1] + M[3][0]*Tmp[1][2]);
	Result[1][2] = -RDet * (M[0][0]*Tmp[2][0] - M[1][0]*Tmp[2][1] + M[3][0]*Tmp[2][2]);
	Result[1][3] =  RDet * (M[0][0]*Tmp[3][0] - M[1][0]*Tmp[3][1] + M[2][0]*Tmp[3][2]);
	Result[2][0] =  RDet * (
		M[1][0] * (M[2][1] * M[3][3] - M[2][3] * M[3][1]) -
		M[2][0] * (M[1][1] * M[3][3] - M[1][3] * M[3][1]) +
		M[3][0] * (M[1][1] * M[2][3] - M[1][3] * M[2][1])
		);
	Result[2][1] = -RDet * (
		M[0][0] * (M[2][1] * M[3][3] - M[2][3] * M[3][1]) -
		M[2][0] * (M[0][1] * M[3][3] - M[0][3] * M[3][1]) +
		M[3][0] * (M[0][1] * M[2][3] - M[0][3] * M[2][1])
		);
	Result[2][2] =  RDet * (
		M[0][0] * (M[1][1] * M[3][3] - M[1][3] * M[3][1]) -
		M[1][0] * (M[0][1] * M[3][3] - M[0][3] * M[3][1]) +
		M[3][0] * (M[0][1] * M[1][3] - M[0][3] * M[1][1])
		);
	Result[2][3] = -RDet * (
		M[0][0] * (M[1][1] * M[2][3] - M[1][3] * M[2][1]) -
		M[1][0] * (M[0][1] * M[2][3] - M[0][3] * M[2][1]) +
		M[2][0] * (M[0][1] * M[1][3] - M[0][3] * M[1][1])
		);
	Result[3][0] = -RDet * (
		M[1][0] * (M[2][1] * M[3][2] - M[2][2] * M[3][1]) -
		M[2][0] * (M[1][1] * M[3][2] - M[1][2] * M[3][1]) +
		M[3][0] * (M[1][1] * M[2][2] - M[1][2] * M[2][1])
		);
	Result[3][1] =  RDet * (
		M[0][0] * (M[2][1] * M[3][2] - M[2][2] * M[3][1]) -
		M[2][0] * (M[0][1] * M[3][2] - M[0][2] * M[3][1]) +
		M[3][0] * (M[0][1] * M[2][2] - M[0][2] * M[2][1])
		);
	Result[3][2] = -RDet * (
		M[0][0] * (M[1][1] * M[3][2] - M[1][2] * M[3][1]) -
		M[1][0] * (M[0][1] * M[3][2] - M[0][2] * M[3][1]) +
		M[3][0] * (M[0][1] * M[1][2] - M[0][2] * M[1][1])
		);
	Result[3][3] =  RDet * (
		M[0][0] * (M[1][1] * M[2][2] - M[1][2] * M[2][1]) -
		M[1][0] * (M[0][1] * M[2][2] - M[0][2] * M[2][1]) +
		M[2][0] * (M[0][1] * M[1][2] - M[0][2] * M[1][1])
		);

	memcpy( DstMatrix, &Result, 16*sizeof(float) );
}

// Math/Matrix.inl
__forceinline FMatrix FMatrix::operator*(const FMatrix& Other) const
{
	FMatrix Result;
	VectorMatrixMultiply( &Result, this, &Other );
	return Result;
}

// Remove any scaling from this matrix (ie magnitude of each row is 1)
inline void FMatrix::RemoveScaling(float Tolerance/*=SMALL_NUMBER*/)
{
	// For each row, find magnitude, and if its non-zero re-scale so its unit length.
	const float SquareSum0 = (M[0][0] * M[0][0]) + (M[0][1] * M[0][1]) + (M[0][2] * M[0][2]);
	const float SquareSum1 = (M[1][0] * M[1][0]) + (M[1][1] * M[1][1]) + (M[1][2] * M[1][2]);
	const float SquareSum2 = (M[2][0] * M[2][0]) + (M[2][1] * M[2][1]) + (M[2][2] * M[2][2]);
	const float Scale0 = FMath::FloatSelect( SquareSum0 - Tolerance, FMath::InvSqrt(SquareSum0), 1.0f );
	const float Scale1 = FMath::FloatSelect( SquareSum1 - Tolerance, FMath::InvSqrt(SquareSum1), 1.0f );
	const float Scale2 = FMath::FloatSelect( SquareSum2 - Tolerance, FMath::InvSqrt(SquareSum2), 1.0f );
	M[0][0] *= Scale0;
	M[0][1] *= Scale0;
	M[0][2] *= Scale0;
	M[1][0] *= Scale1;
	M[1][1] *= Scale1;
	M[1][2] *= Scale1;
	M[2][0] *= Scale2;
	M[2][1] *= Scale2;
	M[2][2] *= Scale2;
}

// Inline in Matrix.inl (not FORCEINLINE); the reference calls an out-of-line copy (0x00674050),
// which UKismetMathLibrary::MinimumAreaRectangle's object emits. The zero-scale check is
// compiled out of shipping builds.
inline FMatrix FMatrix::InverseFast() const
{
	FMatrix Result;
	VectorMatrixInverse( &Result, this );
	return Result;
}

inline FMatrix FMatrix::Inverse() const
{
	FMatrix Result;

	// Check for zero scale matrix to invert
	if(	GetScaledAxis( EAxis::X ).IsNearlyZero(SMALL_NUMBER) &&
		GetScaledAxis( EAxis::Y ).IsNearlyZero(SMALL_NUMBER) &&
		GetScaledAxis( EAxis::Z ).IsNearlyZero(SMALL_NUMBER) )
	{
		// just set to zero - avoids unsafe inverse of zero and duplicates what QNANs were resulting in before (scaling away all children)
		Result = FMatrix::Identity;
	}
	else
	{
		const float	Det = Determinant();

		if(Det == 0.0f)
		{
			Result = FMatrix::Identity;
		}
		else
		{
			VectorMatrixInverse( &Result, this );
		}
	}

	return Result;
}

/** Faster version of InverseTransformVector that assumes no scaling. WARNING: Will NOT work correctly if there is scaling in the matrix. */
__forceinline FVector FMatrix::InverseTransformVector(const FVector &V) const
{
	FMatrix InvSelf = this->InverseFast();
	return InvSelf.TransformVector(V);
}

// Math/Quat.h
__forceinline bool FQuat::Equals(const FQuat& Q, float Tolerance) const
{
	const VectorRegister ToleranceV = VectorLoadFloat1(&Tolerance);
	const VectorRegister A = VectorLoadAligned(this);
	const VectorRegister B = VectorLoadAligned(&Q);

	const VectorRegister RotationSub = VectorAbs(VectorSubtract(A, B));
	const VectorRegister RotationAdd = VectorAbs(VectorAdd(A, B));
	return !VectorAnyGreaterThan(RotationSub, ToleranceV) || !VectorAnyGreaterThan(RotationAdd, ToleranceV);
}

__forceinline float FQuat::AngularDistance(const FQuat& Q) const
{
	float InnerProd = X*Q.X + Y*Q.Y + Z*Q.Z + W*Q.W;
	return FMath::Acos((2 * InnerProd * InnerProd) - 1.f);
}

// Math/Quat.h. The ensure() on the unit-length axes is compiled out of shipping builds.
inline FQuat::FQuat(const FMatrix& M)
{
	// If Matrix is NULL, return Identity quaternion. If any of them is 0, you won't be able to construct rotation
	// if you have two plane at least, we can reconstruct the frame using cross product, but that's a bit expensive op to do here
	// for now, if you convert to matrix from 0 scale and convert back, you'll lose rotation. Don't do that.
	if (M.GetScaledAxis(EAxis::X).IsNearlyZero() || M.GetScaledAxis(EAxis::Y).IsNearlyZero() || M.GetScaledAxis(EAxis::Z).IsNearlyZero())
	{
		*this = FQuat::Identity;
		return;
	}

	//const MeReal *const t = (MeReal *) tm;
	float	s;

	// Check diagonal (trace)
	const float tr = M.M[0][0] + M.M[1][1] + M.M[2][2];

	if (tr > 0.0f)
	{
		float InvS = FMath::InvSqrt(tr + 1.f);
		this->W = 0.5f * (1.f / InvS);
		s = 0.5f * InvS;

		this->X = (M.M[1][2] - M.M[2][1]) * s;
		this->Y = (M.M[2][0] - M.M[0][2]) * s;
		this->Z = (M.M[0][1] - M.M[1][0]) * s;
	}
	else
	{
		// diagonal is negative
		int32 i = 0;

		if (M.M[1][1] > M.M[0][0])
			i = 1;

		if (M.M[2][2] > M.M[i][i])
			i = 2;

		static const int32 nxt[3] = { 1, 2, 0 };
		const int32 j = nxt[i];
		const int32 k = nxt[j];

		s = M.M[i][i] - M.M[j][j] - M.M[k][k] + 1.0f;

		float InvS = FMath::InvSqrt(s);

		float qt[4];
		qt[i] = 0.5f * (1.f / InvS);

		s = 0.5f * InvS;

		qt[3] = (M.M[j][k] - M.M[k][j]) * s;
		qt[j] = (M.M[i][j] + M.M[j][i]) * s;
		qt[k] = (M.M[i][k] + M.M[k][i]) * s;

		this->X = qt[0];
		this->Y = qt[1];
		this->Z = qt[2];
		this->W = qt[3];
	}
}
#endif

// Math/UnrealMathSSE.h
__forceinline VectorRegister VectorTransformVector(const VectorRegister&  VecP,  const void* MatrixM )
{
	const VectorRegister *M	= (const VectorRegister *) MatrixM;
	VectorRegister VTempX, VTempY, VTempZ, VTempW;

	// Splat x,y,z and w
	VTempX = VectorReplicate(VecP, 0);
	VTempY = VectorReplicate(VecP, 1);
	VTempZ = VectorReplicate(VecP, 2);
	VTempW = VectorReplicate(VecP, 3);
	// Mul by the matrix
	VTempX = VectorMultiply(VTempX, M[0]);
	VTempY = VectorMultiply(VTempY, M[1]);
	VTempZ = VectorMultiply(VTempZ, M[2]);
	VTempW = VectorMultiply(VTempW, M[3]);
	// Add them all together
	VTempX = VectorAdd(VTempX, VTempY);
	VTempZ = VectorAdd(VTempZ, VTempW);
	VTempX = VectorAdd(VTempX, VTempZ);

	return VTempX;
}

// Math/Matrix.inl
__forceinline FVector4 FMatrix::TransformFVector4(const FVector4 &P) const
{
	FVector4 Result;
	VectorRegister VecP = VectorLoadAligned(&P);
	VectorRegister VecR = VectorTransformVector(VecP, this);
	VectorStoreAligned(VecR, &Result);
	return Result;
}

__forceinline FVector4 FMatrix::TransformVector(const FVector& V) const
{
	return TransformFVector4(FVector4(V.X,V.Y,V.Z,0.0f));
}

__forceinline FVector FTransform::TransformVectorNoScale(const FVector& V) const
{
	const VectorRegister InputVectorW0 = VectorLoadFloat3_W0(&V);

	//RotatedVec = Q.Rotate(V.X, V.Y, V.Z, 0.f)
	const VectorRegister RotatedVec = VectorQuaternionRotateVector(Rotation, InputVectorW0);

	FVector Result;
	VectorStoreFloat3(RotatedVec, &Result);
	return Result;
}

// x = 0, y = 1, z = 2
__forceinline FVector FTransform::GetUnitAxis( EAxis::Type InAxis ) const
{
	if ( InAxis == EAxis::X )
	{
		return TransformVectorNoScale(FVector(1.f, 0.f, 0.f));
	}
	else if ( InAxis == EAxis::Y )
	{
		return TransformVectorNoScale(FVector(0.f, 1.f, 0.f));
	}

	return TransformVectorNoScale(FVector(0.f, 0.f, 1.f));
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

// Math/DualQuat.h. The constructor from an FTransform is inline there; the reference keeps an
// out-of-line copy in UKismetMathLibrary's object (0x0206EDB0), as this does.
struct FDualQuat
{
	/** rotation or real part */
	FQuat R;
	/** half trans or dual part */
	FQuat D;

	// Constructors
	FDualQuat(const FQuat &InR, const FQuat &InD)
		: R(InR)
		, D(InD)
	{}

	FDualQuat(const FTransform &T)
	{
		FVector V = T.GetTranslation()*0.5f;
		*this = FDualQuat(FQuat(0, 0, 0, 1), FQuat(V.X, V.Y, V.Z, 0.f)) * FDualQuat(T.GetRotation(), FQuat(0, 0, 0, 0));
	}

	/** Dual quat addition */
	FDualQuat operator+(const FDualQuat &B) const
	{
		return{ R + B.R, D + B.D };
	}

	/** Dual quat product */
	FDualQuat operator*(const FDualQuat &B) const
	{
		return{ R*B.R, D*B.R + B.D*R };
	}

	/** Scale dual quat */
	FDualQuat operator*(const float S) const
	{
		return{ R*S, D*S };
	}

	/** Return normalized dual quat */
	FDualQuat Normalized() const
	{
		float MinV = 1.0f / FMath::Sqrt(R | R);
		return{ R*MinV, D*MinV };
	}

	/** Convert dual quat to transform */
	FTransform AsFTransform(FVector Scale)   // = FVector(1.0f, 1.0f, 1.0f) in 4.20
	{
		FQuat TQ = D*FQuat(-R.X, -R.Y, -R.Z, R.W);
		return FTransform(R, FVector(TQ.X, TQ.Y, TQ.Z)*2.0f, Scale);
	}
};
