// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: Core. Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/Core/Private/Math/UnrealMath.cpp.
// Reconstruction written from image evidence; see analysis/functions.json.

#include "FortniteGameCode/MathDecls.h"
#include "FortniteGameCode/RecoveryHarness.h"

// The engine headers' GlobalVectorConstants (UnrealMathVectorConstants.h) of this unit: the 24
// whose leaf dynamic initializers store to its .bss in the reference (0x046A0EB0-0x046A1040; the
// initializers at 0x00129070-0x00129371), in header order. QuatRecovered.h reads them.
#include "FortniteGameCode/VectorRecovered.h"
namespace GlobalVectorConstants
{
#define SIGN_BIT ((1 << 31))
	static const VectorRegister FloatOne = MakeVectorRegister(1.0f, 1.0f, 1.0f, 1.0f);
	static const VectorRegister FloatZero = MakeVectorRegister(0.0f, 0.0f, 0.0f, 0.0f);
	static const VectorRegister FloatMinusOne = MakeVectorRegister(-1.0f, -1.0f, -1.0f, -1.0f);
	static const VectorRegister Float0001 = MakeVectorRegister( 0.0f, 0.0f, 0.0f, 1.0f );
	static const VectorRegister SmallLengthThreshold = MakeVectorRegister(1.e-8f, 1.e-8f, 1.e-8f, 1.e-8f);
	static const VectorRegister FloatMinus1_111 = MakeVectorRegister( -1.f, 1.f, 1.f, 1.f );
	static const VectorRegister FloatOneHalf = MakeVectorRegister( 0.5f, 0.5f, 0.5f, 0.5f );
	static const VectorRegister SmallNumber = MakeVectorRegister( SMALL_NUMBER, SMALL_NUMBER, SMALL_NUMBER, SMALL_NUMBER );
	static const VectorRegister ThreshQuatNormalized = MakeVectorRegister( THRESH_QUAT_NORMALIZED, THRESH_QUAT_NORMALIZED, THRESH_QUAT_NORMALIZED, THRESH_QUAT_NORMALIZED );
	static const VectorRegister QINV_SIGN_MASK = MakeVectorRegister( -1.f, -1.f, -1.f, 1.f );
	static const VectorRegister QMULTI_SIGN_MASK0 = MakeVectorRegister( 1.f, -1.f, 1.f, -1.f );
	static const VectorRegister QMULTI_SIGN_MASK1 = MakeVectorRegister( 1.f, 1.f, -1.f, -1.f );
	static const VectorRegister QMULTI_SIGN_MASK2 = MakeVectorRegister( -1.f, 1.f, 1.f, -1.f );
	static const VectorRegister DEG_TO_RAD = MakeVectorRegister(PI/(180.f), PI/(180.f), PI/(180.f), PI/(180.f));
	static const VectorRegister DEG_TO_RAD_HALF = MakeVectorRegister((PI/180.f)*0.5f, (PI/180.f)*0.5f, (PI/180.f)*0.5f, (PI/180.f)*0.5f);
	static const VectorRegister XYZMask = MakeVectorRegister((uint32)0xffffffff, (uint32)0xffffffff, (uint32)0xffffffff, (uint32)0x00000000);
	static const VectorRegister SignBit = MakeVectorRegister((uint32)SIGN_BIT, (uint32)SIGN_BIT, (uint32)SIGN_BIT, (uint32)SIGN_BIT);
	static const VectorRegister SignMask = MakeVectorRegister((uint32)(~SIGN_BIT), (uint32)(~SIGN_BIT), (uint32)(~SIGN_BIT), (uint32)(~SIGN_BIT));
	static const VectorRegister Pi = MakeVectorRegister(PI, PI, PI, PI);
	static const VectorRegister TwoPi = MakeVectorRegister(2.0f*PI, 2.0f*PI, 2.0f*PI, 2.0f*PI);
	static const VectorRegister PiByTwo = MakeVectorRegister(0.5f*PI, 0.5f*PI, 0.5f*PI, 0.5f*PI);
	static const VectorRegister OneOverTwoPi = MakeVectorRegister(1.0f / (2.0f*PI), 1.0f / (2.0f*PI), 1.0f / (2.0f*PI), 1.0f / (2.0f*PI));
	static const VectorRegister Float360 = MakeVectorRegister(360.f, 360.f, 360.f, 360.f);
	static const VectorRegister Float180 = MakeVectorRegister(180.f, 180.f, 180.f, 180.f);
#undef SIGN_BIT
}
#include "FortniteGameCode/TransformRecovered.h"
#include "FortniteGameCode/QuatRecovered.h"

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

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0118BD30 (end 0x0118BE2A)
// Original VA: 0x000000014118BD30 | File offset: 0x0118B330
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::execFindClosestPointOnSegment (the Kismet function is
//   inlined into its thunk) and by FMath::PointDistToSegment (0x0119F670).
FVector FMath::ClosestPointOnSegment(const FVector &Point, const FVector &StartPoint, const FVector &EndPoint)
{
	const FVector Segment = EndPoint - StartPoint;
	const FVector VectToPoint = Point - StartPoint;

	// See if closest point is before StartPoint
	const float Dot1 = VectToPoint | Segment;
	if( Dot1 <= 0 )
	{
		return StartPoint;
	}

	// See if closest point is beyond EndPoint
	const float Dot2 = Segment | Segment;
	if( Dot2 <= Dot1 )
	{
		return EndPoint;
	}

	// Closest Point is within segment
	return StartPoint + Segment * (Dot1 / Dot2);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0119F670 (end 0x0119F6CD)
// Original VA: 0x000000014119F670 | File offset: 0x0119EC70
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::execGetPointDistanceToSegment; calls
//   FMath::ClosestPointOnSegment (0x0118BD30), then the length of the difference.
float FMath::PointDistToSegment(const FVector &Point, const FVector &StartPoint, const FVector &EndPoint)
{
	const FVector ClosestPoint = ClosestPointOnSegment(Point, StartPoint, EndPoint);
	return (Point - ClosestPoint).Size();
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A73C0 (end 0x011A74BD)
// Original VA: 0x00000001411A73C0 | File offset: 0x011A69C0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::execVInterpTo_Constant (Kismet function inlined).
FVector FMath::VInterpConstantTo(const FVector Current, const FVector& Target, float DeltaTime, float InterpSpeed)
{
	const FVector Delta = Target - Current;
	const float DeltaM = Delta.Size();
	const float MaxStep = InterpSpeed * DeltaTime;

	if( DeltaM > MaxStep )
	{
		if( MaxStep > 0.f )
		{
			const FVector DeltaN = Delta / DeltaM;
			return Current + DeltaN * MaxStep;
		}
		else
		{
			return Current;
		}
	}

	return Target;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A74C0 (end 0x011A75E9)
// Original VA: 0x00000001411A74C0 | File offset: 0x011A6AC0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::execVInterpTo (Kismet function inlined).
FVector FMath::VInterpTo( const FVector& Current, const FVector& Target, float DeltaTime, float InterpSpeed )
{
	// If no interp speed, jump to target value
	if( InterpSpeed <= 0.f )
	{
		return Target;
	}

	// Distance to reach
	const FVector Dist = Target - Current;

	// If distance is too small, just set the desired location
	if( Dist.SizeSquared() < KINDA_SMALL_NUMBER )
	{
		return Target;
	}

	// Delta Move, Clamp so we do not over shoot.
	const FVector	DeltaMove = Dist * FMath::Clamp<float>(DeltaTime * InterpSpeed, 0.f, 1.f);

	return Current + DeltaMove;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A7E60 (end 0x011A7F23)
// Original VA: 0x00000001411A7E60 | File offset: 0x011A7460
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::execVector2DInterpTo_Constant (Kismet function inlined).
FVector2D FMath::Vector2DInterpConstantTo( const FVector2D& Current, const FVector2D& Target, float DeltaTime, float InterpSpeed )
{
	const FVector2D Delta = Target - Current;
	const float DeltaM = Delta.Size();
	const float MaxStep = InterpSpeed * DeltaTime;

	if( DeltaM > MaxStep )
	{
		if( MaxStep > 0.f )
		{
			const FVector2D DeltaN = Delta / DeltaM;
			return Current + DeltaN * MaxStep;
		}
		else
		{
			return Current;
		}
	}

	return Target;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A7F30 (end 0x011A7FF3)
// Original VA: 0x00000001411A7F30 | File offset: 0x011A7530
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::execVector2DInterpTo (Kismet function inlined).
FVector2D FMath::Vector2DInterpTo( const FVector2D& Current, const FVector2D& Target, float DeltaTime, float InterpSpeed )
{
	if( InterpSpeed <= 0.f )
	{
		return Target;
	}

	const FVector2D Dist = Target - Current;
	if( Dist.SizeSquared() < KINDA_SMALL_NUMBER )
	{
		return Target;
	}

	const FVector2D DeltaMove = Dist * FMath::Clamp<float>(DeltaTime * InterpSpeed, 0.f, 1.f);
	return Current + DeltaMove;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01190AA0 (end 0x01190AFE)
// Original VA: 0x0000000141190AA0 | File offset: 0x011900A0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::execFInterpTo (Kismet function inlined).
float FMath::FInterpTo( float Current, float Target, float DeltaTime, float InterpSpeed )
{
	// If no interp speed, jump to target value
	if( InterpSpeed <= 0.f )
	{
		return Target;
	}

	// Distance to reach
	const float Dist = Target - Current;

	// If distance is too small, just set the desired location
	if( FMath::Square(Dist) < SMALL_NUMBER )
	{
		return Target;
	}

	// Delta Move, Clamp so we do not over shoot.
	const float DeltaMove = Dist * FMath::Clamp<float>(DeltaTime * InterpSpeed, 0.f, 1.f);

	return Current + DeltaMove;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01190A40 (end 0x01190A95)
// Original VA: 0x0000000141190A40 | File offset: 0x01190040
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::execFInterpTo_Constant (Kismet function inlined).
float FMath::FInterpConstantTo( float Current, float Target, float DeltaTime, float InterpSpeed )
{
	const float Dist = Target - Current;

	// If distance is too small, just set the desired location
	if( FMath::Square(Dist) < SMALL_NUMBER )
	{
		return Target;
	}

	const float Step = InterpSpeed * DeltaTime;
	return Current + FMath::Clamp<float>(Dist, -Step, Step);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0119F2B0 (end 0x0119F496)
// Original VA: 0x000000014119F2B0 | File offset: 0x0119E8B0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::execGetPointDistanceToLine (Kismet function inlined); the
//   three-argument overload, which sorts before the four-argument one.
float FMath::PointDistToLine(const FVector &Point, const FVector &Direction, const FVector &Origin)
{
	const FVector SafeDir = Direction.GetSafeNormal();
	const FVector OutClosestPoint = Origin + (SafeDir * ((Point-Origin) | SafeDir));
	return (OutClosestPoint-Point).Size();
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0118B150 (end 0x0118B2EF)
// Original VA: 0x000000014118B150 | File offset: 0x0118A750
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::execCInterpTo (Kismet function inlined).
FLinearColor FMath::CInterpTo(const FLinearColor& Current, const FLinearColor& Target, float DeltaTime, float InterpSpeed)
{
	// If no interp speed, jump to target value
	if (InterpSpeed <= 0.f)
	{
		return Target;
	}

	// Difference between colors
	const float Dist = FLinearColor::Dist(Target, Current);

	// If distance is too small, just set the desired color
	if (Dist < KINDA_SMALL_NUMBER)
	{
		return Target;
	}

	// Delta change, Clamp so we do not over shoot.
	const FLinearColor DeltaMove = (Target - Current) * FMath::Clamp<float>(DeltaTime * InterpSpeed, 0.f, 1.f);

	return Current + DeltaMove;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01188C70 (end 0x01188CA0)
// Original VA: 0x0000000141188C70 | File offset: 0x01188270
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::ComposeRotators (0x02076420) on a quaternion product;
//   forwards to FQuat::Rotator (0x011A2050). Constructors sort first in UnrealMath.obj's run.
FRotator::FRotator(const FQuat& Quat)
{
	*this = Quat.Rotator();
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A2050 (end 0x011A23CF)
// Original VA: 0x00000001411A2050 | File offset: 0x011A1650
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called after every quaternion result in the Kismet rotator natives (RLerp,
//   TransformRotation, RotatorFromAxisAndAngle, ...); three branches on the 0.4999995
//   singularity threshold, FGenericPlatformMath::Atan2 (0x01112E50), FMath::FastAsin and
//   FRotator::NormalizeAxis (FmodReportError, 0x0126F320). SCOPE_CYCLE_COUNTER is empty in shipping.
FRotator FQuat::Rotator() const
{
	const float SingularityTest = Z*X-W*Y;
	const float YawY = 2.f*(W*Z+X*Y);
	const float YawX = (1.f-2.f*(FMath::Square(Y) + FMath::Square(Z)));

	// reference 
	// http://en.wikipedia.org/wiki/Conversion_between_quaternions_and_Euler_angles
	// http://www.euclideanspace.com/maths/geometry/rotations/conversions/quaternionToEuler/

	// this value was found from experience, the above websites recommend different values
	// but that isn't the case for us, so I went through different testing, and finally found the case 
	// where both of world lives happily. 
	const float SINGULARITY_THRESHOLD = 0.4999995f;
	const float RAD_TO_DEG = (180.f)/PI;
	FRotator RotatorFromQuat;

	if (SingularityTest < -SINGULARITY_THRESHOLD)
	{
		RotatorFromQuat.Pitch = -90.f;
		RotatorFromQuat.Yaw = FMath::Atan2(YawY, YawX) * RAD_TO_DEG;
		RotatorFromQuat.Roll = FRotator::NormalizeAxis(-RotatorFromQuat.Yaw - (2.f * FMath::Atan2(X, W) * RAD_TO_DEG));
	}
	else if (SingularityTest > SINGULARITY_THRESHOLD)
	{
		RotatorFromQuat.Pitch = 90.f;
		RotatorFromQuat.Yaw = FMath::Atan2(YawY, YawX) * RAD_TO_DEG;
		RotatorFromQuat.Roll = FRotator::NormalizeAxis(RotatorFromQuat.Yaw - (2.f * FMath::Atan2(X, W) * RAD_TO_DEG));
	}
	else
	{
		RotatorFromQuat.Pitch = FMath::FastAsin(2.f*(SingularityTest)) * RAD_TO_DEG;
		RotatorFromQuat.Yaw = FMath::Atan2(YawY, YawX) * RAD_TO_DEG;
		RotatorFromQuat.Roll = FMath::Atan2(-2.f*(W*X+Y*Z), (1.f-2.f*(FMath::Square(X) + FMath::Square(Y)))) * RAD_TO_DEG;
	}

	return RotatorFromQuat;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01194C60 (end 0x01194CC5)
// Original VA: 0x0000000141194C60 | File offset: 0x01194260
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::execNegateRotator (Kismet function inlined): the
//   out-of-line FRotator::Quaternion (0x011A0970), the scalar FQuat::Inverse (a sign-mask xorps),
//   then FQuat::Rotator (0x011A2050).
FRotator FRotator::GetInverse() const
{
	return Quaternion().Inverse().Rotator();
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A5A50 (end 0x011A5BC1)
// Original VA: 0x00000001411A5A50 | File offset: 0x011A5050
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::RLerp (0x0208CF60) between two FRotator::Quaternion
//   calls; acosf of the clamped cosine, three sinf calls below 0.9999, else linear weights.
FQuat FQuat::Slerp_NotNormalized(const FQuat& Quat1,const FQuat& Quat2, float Slerp)
{
	// Get cosine of angle between quats.
	const float RawCosom = 
		    Quat1.X * Quat2.X +
			Quat1.Y * Quat2.Y +
			Quat1.Z * Quat2.Z +
			Quat1.W * Quat2.W;
	// Unaligned quats - compensate, results in taking shorter route.
	const float Cosom = FMath::FloatSelect( RawCosom, RawCosom, -RawCosom );

	float Scale0, Scale1;

	if( Cosom < 0.9999f )
	{	
		const float Omega = FMath::Acos(Cosom);
		const float InvSin = 1.f/FMath::Sin(Omega);
		Scale0 = FMath::Sin( (1.f - Slerp) * Omega ) * InvSin;
		Scale1 = FMath::Sin( Slerp * Omega ) * InvSin;
	}
	else
	{
		// Use linear interpolation.
		Scale0 = 1.0f - Slerp;
		Scale1 = Slerp;	
	}

	// In keeping with our flipped Cosom:
	Scale1 = FMath::FloatSelect( RawCosom, Scale1, -Scale1 );

	FQuat Result;
		
	Result.X = Scale0 * Quat1.X + Scale1 * Quat2.X;
	Result.Y = Scale0 * Quat1.Y + Scale1 * Quat2.Y;
	Result.Z = Scale0 * Quat1.Z + Scale1 * Quat2.Z;
	Result.W = Scale0 * Quat1.W + Scale1 * Quat2.W;

	return Result;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A1EC0 (end 0x011A2049)
// Original VA: 0x00000001411A1EC0 | File offset: 0x011A14C0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::MakeRotationFromAxes (0x02089FA0); pitch and yaw from
//   the X axis (Atan2, 0x01112E50), then the out-of-line FRotationMatrix constructor
//   (0x009C4CB0) for the roll's Y axis.
FRotator FMatrix::Rotator() const
{
	const FVector		XAxis	= GetScaledAxis( EAxis::X );
	const FVector		YAxis	= GetScaledAxis( EAxis::Y );
	const FVector		ZAxis	= GetScaledAxis( EAxis::Z );

	FRotator	Rotator	= FRotator( 
									FMath::Atan2( XAxis.Z, FMath::Sqrt(FMath::Square(XAxis.X)+FMath::Square(XAxis.Y)) ) * 180.f / PI, 
									FMath::Atan2( XAxis.Y, XAxis.X ) * 180.f / PI, 
									0 
								);
	
	const FVector		SYAxis	= FRotationMatrix( Rotator ).GetScaledAxis( EAxis::Y );
	Rotator.Roll		= FMath::Atan2( ZAxis | SYAxis, YAxis | SYAxis ) * 180.f / PI;

	return Rotator;
}

// FVector::RotateAngleAxis is inline in Math/Vector.h; the reference calls one out-of-line copy
// (COMDAT), from an object not established. The anchor table below makes this unit emit it.
// Original FortniteClient-Win64-Shipping.exe: RVA 0x00579DF0 (end 0x0057A07F)
// Original VA: 0x0000000140579DF0 | File offset: 0x005793F0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::RotateAngleAxis (0x0208EF30) with the safe-normal
//   axis; FMath::SinCos of the angle in radians, then the axis-angle rotation matrix applied.
inline FVector FVector::RotateAngleAxis(const float AngleDeg, const FVector& Axis) const
{
	float S, C;
	FMath::SinCos(&S, &C, FMath::DegreesToRadians(AngleDeg));

	const float XX	= Axis.X * Axis.X;
	const float YY	= Axis.Y * Axis.Y;
	const float ZZ	= Axis.Z * Axis.Z;

	const float XY	= Axis.X * Axis.Y;
	const float YZ	= Axis.Y * Axis.Z;
	const float ZX	= Axis.Z * Axis.X;

	const float XS	= Axis.X * S;
	const float YS	= Axis.Y * S;
	const float ZS	= Axis.Z * S;

	const float OMC	= 1.f - C;

	return FVector(
		(OMC * XX + C) * X + (OMC * XY - ZS) * Y + (OMC * ZX + YS) * Z,
		(OMC * XY + ZS) * X + (OMC * YY + C) * Y + (OMC * YZ - XS) * Z,
		(OMC * ZX - YS) * X + (OMC * YZ + XS) * Y + (OMC * ZZ + C) * Z
		);
}

#if FNGC_MATCHING_HARNESS
// A member function's address does not convert to the anchor table's const void*; an external
// member pointer keeps the out-of-line copy the same way, without changing its code.
extern FVector (FVector::* const GFngcAnchor_RotateAngleAxis)(const float, const FVector&) const;
FVector (FVector::* const GFngcAnchor_RotateAngleAxis)(const float, const FVector&) const = &FVector::RotateAngleAxis;
#endif

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0119B690 (end 0x0119B9E8)
// Original VA: 0x000000014119B690 | File offset: 0x0119AC90
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by the exec thunk of UKismetMathLibrary::MakeRotX (Kismet function inlined),
//   before FMatrix::Rotator (0x011A1EC0); one axis: its safe normal, the world up (or X when nearly vertical), two cross products. The nine sort alphabetically in UnrealMath.obj's run.
FMatrix FRotationMatrix::MakeFromX(FVector const& XAxis)
{
	FVector const NewX = XAxis.GetSafeNormal();

	// try to use up if possible
	FVector const UpVector = ( FMath::Abs(NewX.Z) < (1.f - KINDA_SMALL_NUMBER) ) ? FVector(0,0,1.f) : FVector(1.f,0,0);

	const FVector NewY = (UpVector ^ NewX).GetSafeNormal();
	const FVector NewZ = NewX ^ NewY;

	return FMatrix(NewX, NewY, NewZ, FVector::ZeroVector);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0119C350 (end 0x0119C6A8)
// Original VA: 0x000000014119C350 | File offset: 0x0119B950
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by the exec thunk of UKismetMathLibrary::MakeRotY (Kismet function inlined),
//   before FMatrix::Rotator (0x011A1EC0); one axis: its safe normal, the world up (or X when nearly vertical), two cross products. The nine sort alphabetically in UnrealMath.obj's run.
FMatrix FRotationMatrix::MakeFromY(FVector const& YAxis)
{
	FVector const NewY = YAxis.GetSafeNormal();

	// try to use up if possible
	FVector const UpVector = ( FMath::Abs(NewY.Z) < (1.f - KINDA_SMALL_NUMBER) ) ? FVector(0,0,1.f) : FVector(1.f,0,0);

	const FVector NewZ = (UpVector ^ NewY).GetSafeNormal();
	const FVector NewX = NewY ^ NewZ;

	return FMatrix(NewX, NewY, NewZ, FVector::ZeroVector);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0119D010 (end 0x0119D368)
// Original VA: 0x000000014119D010 | File offset: 0x0119C610
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by the exec thunk of UKismetMathLibrary::MakeRotZ (Kismet function inlined),
//   before FMatrix::Rotator (0x011A1EC0); one axis: its safe normal, the world up (or X when nearly vertical), two cross products. The nine sort alphabetically in UnrealMath.obj's run.
FMatrix FRotationMatrix::MakeFromZ(FVector const& ZAxis)
{
	FVector const NewZ = ZAxis.GetSafeNormal();

	// try to use up if possible
	FVector const UpVector = ( FMath::Abs(NewZ.Z) < (1.f - KINDA_SMALL_NUMBER) ) ? FVector(0,0,1.f) : FVector(1.f,0,0);

	const FVector NewX = (UpVector ^ NewZ).GetSafeNormal();
	const FVector NewY = NewZ ^ NewX;

	return FMatrix(NewX, NewY, NewZ, FVector::ZeroVector);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0119B9F0 (end 0x0119BE9D)
// Original VA: 0x000000014119B9F0 | File offset: 0x0119AFF0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by the exec thunk of UKismetMathLibrary::MakeRotXY (Kismet function inlined),
//   before FMatrix::Rotator (0x011A1EC0); two axes: their safe normals, an arbitrary axis when nearly parallel (IsNearlyEqual), two cross products. The nine sort alphabetically in UnrealMath.obj's run.
FMatrix FRotationMatrix::MakeFromXY(FVector const& XAxis, FVector const& YAxis)
{
	FVector NewX = XAxis.GetSafeNormal();
	FVector Norm = YAxis.GetSafeNormal();

	// if they're almost same, we need to find arbitrary vector
	if ( FMath::IsNearlyEqual(FMath::Abs(NewX | Norm), 1.f) )
	{
		// make sure we don't ever pick the same as NewX
		Norm = ( FMath::Abs(NewX.Z) < (1.f - KINDA_SMALL_NUMBER) ) ? FVector(0,0,1.f) : FVector(1.f,0,0);
	}

	const FVector NewZ = (NewX ^ Norm).GetSafeNormal();
	const FVector NewY = NewZ ^ NewX;

	return FMatrix(NewX, NewY, NewZ, FVector::ZeroVector);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0119BEA0 (end 0x0119C34D)
// Original VA: 0x000000014119BEA0 | File offset: 0x0119B4A0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by the exec thunk of UKismetMathLibrary::MakeRotXZ (Kismet function inlined),
//   before FMatrix::Rotator (0x011A1EC0); two axes: their safe normals, an arbitrary axis when nearly parallel (IsNearlyEqual), two cross products. The nine sort alphabetically in UnrealMath.obj's run.
FMatrix FRotationMatrix::MakeFromXZ(FVector const& XAxis, FVector const& ZAxis)
{
	FVector const NewX = XAxis.GetSafeNormal();
	FVector Norm = ZAxis.GetSafeNormal();

	// if they're almost same, we need to find arbitrary vector
	if ( FMath::IsNearlyEqual(FMath::Abs(NewX | Norm), 1.f) )
	{
		// make sure we don't ever pick the same as NewX
		Norm = ( FMath::Abs(NewX.Z) < (1.f - KINDA_SMALL_NUMBER) ) ? FVector(0,0,1.f) : FVector(1.f,0,0);
	}

	const FVector NewY = (Norm ^ NewX).GetSafeNormal();
	const FVector NewZ = NewX ^ NewY;

	return FMatrix(NewX, NewY, NewZ, FVector::ZeroVector);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0119C6B0 (end 0x0119CB5D)
// Original VA: 0x000000014119C6B0 | File offset: 0x0119BCB0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by the exec thunk of UKismetMathLibrary::MakeRotYX (Kismet function inlined),
//   before FMatrix::Rotator (0x011A1EC0); two axes: their safe normals, an arbitrary axis when nearly parallel (IsNearlyEqual), two cross products. The nine sort alphabetically in UnrealMath.obj's run.
FMatrix FRotationMatrix::MakeFromYX(FVector const& YAxis, FVector const& XAxis)
{
	FVector const NewY = YAxis.GetSafeNormal();
	FVector Norm = XAxis.GetSafeNormal();

	// if they're almost same, we need to find arbitrary vector
	if ( FMath::IsNearlyEqual(FMath::Abs(NewY | Norm), 1.f) )
	{
		// make sure we don't ever pick the same as NewX
		Norm = ( FMath::Abs(NewY.Z) < (1.f - KINDA_SMALL_NUMBER) ) ? FVector(0,0,1.f) : FVector(1.f,0,0);
	}
	
	const FVector NewZ = (Norm ^ NewY).GetSafeNormal();
	const FVector NewX = NewY ^ NewZ;

	return FMatrix(NewX, NewY, NewZ, FVector::ZeroVector);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0119CB60 (end 0x0119D00D)
// Original VA: 0x000000014119CB60 | File offset: 0x0119C160
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by the exec thunk of UKismetMathLibrary::MakeRotYZ (Kismet function inlined),
//   before FMatrix::Rotator (0x011A1EC0); two axes: their safe normals, an arbitrary axis when nearly parallel (IsNearlyEqual), two cross products. The nine sort alphabetically in UnrealMath.obj's run.
FMatrix FRotationMatrix::MakeFromYZ(FVector const& YAxis, FVector const& ZAxis)
{
	FVector const NewY = YAxis.GetSafeNormal();
	FVector Norm = ZAxis.GetSafeNormal();

	// if they're almost same, we need to find arbitrary vector
	if ( FMath::IsNearlyEqual(FMath::Abs(NewY | Norm), 1.f) )
	{
		// make sure we don't ever pick the same as NewX
		Norm = ( FMath::Abs(NewY.Z) < (1.f - KINDA_SMALL_NUMBER) ) ? FVector(0,0,1.f) : FVector(1.f,0,0);
	}

	const FVector NewX = (NewY ^ Norm).GetSafeNormal();
	const FVector NewZ = NewX ^ NewY;

	return FMatrix(NewX, NewY, NewZ, FVector::ZeroVector);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0119D370 (end 0x0119D81D)
// Original VA: 0x000000014119D370 | File offset: 0x0119C970
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by the exec thunk of UKismetMathLibrary::MakeRotZX (Kismet function inlined),
//   before FMatrix::Rotator (0x011A1EC0); two axes: their safe normals, an arbitrary axis when nearly parallel (IsNearlyEqual), two cross products. The nine sort alphabetically in UnrealMath.obj's run.
FMatrix FRotationMatrix::MakeFromZX(FVector const& ZAxis, FVector const& XAxis)
{
	FVector const NewZ = ZAxis.GetSafeNormal();
	FVector Norm = XAxis.GetSafeNormal();

	// if they're almost same, we need to find arbitrary vector
	if ( FMath::IsNearlyEqual(FMath::Abs(NewZ | Norm), 1.f) )
	{
		// make sure we don't ever pick the same as NewX
		Norm = ( FMath::Abs(NewZ.Z) < (1.f - KINDA_SMALL_NUMBER) ) ? FVector(0,0,1.f) : FVector(1.f,0,0);
	}

	const FVector NewY = (NewZ ^ Norm).GetSafeNormal();
	const FVector NewX = NewY ^ NewZ;

	return FMatrix(NewX, NewY, NewZ, FVector::ZeroVector);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0119D820 (end 0x0119DCCD)
// Original VA: 0x000000014119D820 | File offset: 0x0119CE20
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by the exec thunk of UKismetMathLibrary::MakeRotZY (Kismet function inlined),
//   before FMatrix::Rotator (0x011A1EC0); two axes: their safe normals, an arbitrary axis when nearly parallel (IsNearlyEqual), two cross products. The nine sort alphabetically in UnrealMath.obj's run.
FMatrix FRotationMatrix::MakeFromZY(FVector const& ZAxis, FVector const& YAxis)
{
	FVector const NewZ = ZAxis.GetSafeNormal();
	FVector Norm = YAxis.GetSafeNormal();

	// if they're almost same, we need to find arbitrary vector
	if ( FMath::IsNearlyEqual(FMath::Abs(NewZ | Norm), 1.f) )
	{
		// make sure we don't ever pick the same as NewX
		Norm = ( FMath::Abs(NewZ.Z) < (1.f - KINDA_SMALL_NUMBER) ) ? FVector(0,0,1.f) : FVector(1.f,0,0);
	}

	const FVector NewX = (Norm ^ NewZ).GetSafeNormal();
	const FVector NewY = NewZ ^ NewX;

	return FMatrix(NewX, NewY, NewZ, FVector::ZeroVector);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A0970 (end 0x011A0AFE)
// Original VA: 0x00000001411A0970 | File offset: 0x011A0F70
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: the out-of-line call before every quaternion product in the Kismet rotator natives
//   (ComposeRotators, RLerp, TransformRotation, ...) and in FRotator::GetInverse; VectorSinCos of
//   the half angles (DEG_TO_RAD_HALF, OneOverTwoPi, TwoPi, SignBit, Pi, SignMask, PiByTwo,
//   FloatMinusOne, FloatOne: this unit's constants) and the sign-bit shuffles.
//   SCOPE_CYCLE_COUNTER is commented out in 4.20; NaN checks are compiled out in shipping.
FQuat FRotator::Quaternion() const
{
	const VectorRegister Angles = MakeVectorRegister(Pitch, Yaw, Roll, 0.0f);
	const VectorRegister HalfAngles = VectorMultiply(Angles, GlobalVectorConstants::DEG_TO_RAD_HALF);

	VectorRegister SinAngles, CosAngles;
	VectorSinCos(&SinAngles, &CosAngles, &HalfAngles);

	// Vectorized conversion, measured 20% faster than using scalar version after VectorSinCos.
	// Indices within VectorRegister (for shuffles): P=0, Y=1, R=2
	const VectorRegister SR = VectorReplicate(SinAngles, 2);
	const VectorRegister CR = VectorReplicate(CosAngles, 2);

	const VectorRegister SY_SY_CY_CY_Temp = VectorShuffle(SinAngles, CosAngles, 1, 1, 1, 1);

	const VectorRegister SP_SP_CP_CP = VectorShuffle(SinAngles, CosAngles, 0, 0, 0, 0);
	const VectorRegister SY_CY_SY_CY = VectorShuffle(SY_SY_CY_CY_Temp, SY_SY_CY_CY_Temp, 0, 2, 0, 2);

	const VectorRegister CP_CP_SP_SP = VectorShuffle(CosAngles, SinAngles, 0, 0, 0, 0);
	const VectorRegister CY_SY_CY_SY = VectorShuffle(SY_SY_CY_CY_Temp, SY_SY_CY_CY_Temp, 2, 0, 2, 0);

	const uint32 Neg = uint32(1 << 31);
	const uint32 Pos = uint32(0);
	const VectorRegister SignBitsLeft  = MakeVectorRegister(Pos, Neg, Pos, Pos);
	const VectorRegister SignBitsRight = MakeVectorRegister(Neg, Neg, Neg, Pos);
	const VectorRegister LeftTerm  = VectorBitwiseXor(SignBitsLeft , VectorMultiply(CR, VectorMultiply(SP_SP_CP_CP, SY_CY_SY_CY)));
	const VectorRegister RightTerm = VectorBitwiseXor(SignBitsRight, VectorMultiply(SR, VectorMultiply(CP_CP_SP_SP, CY_SY_CY_SY)));

	FQuat RotationQuat;
	const VectorRegister Result = VectorAdd(LeftTerm, RightTerm);
	VectorStoreAligned(Result, &RotationQuat);

	return RotationQuat;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A0B00 (end 0x011A0D2D)
// Original VA: 0x00000001411A0B00 | File offset: 0x011A0100
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::execRInterpTo_Constant (Kismet function inlined); the
//   vectorized FRotator::GetNormalized (Float360, Float180) twice, the per-axis clamps between.
FRotator FMath::RInterpConstantTo( const FRotator& Current, const FRotator& Target, float DeltaTime, float InterpSpeed )
{
	// if DeltaTime is 0, do not perform any interpolation (Location was already calculated for that frame)
	if( DeltaTime == 0.f || Current == Target )
	{
		return Current;
	}

	// If no interp speed, jump to target value
	if( InterpSpeed <= 0.f )
	{
		return Target;
	}

	const float DeltaInterpSpeed = InterpSpeed * DeltaTime;

	const FRotator DeltaMove = (Target - Current).GetNormalized();
	FRotator Result = Current;
	Result.Pitch += FMath::Clamp(DeltaMove.Pitch, -DeltaInterpSpeed, DeltaInterpSpeed);
	Result.Yaw += FMath::Clamp(DeltaMove.Yaw, -DeltaInterpSpeed, DeltaInterpSpeed);
	Result.Roll += FMath::Clamp(DeltaMove.Roll, -DeltaInterpSpeed, DeltaInterpSpeed);
	return Result.GetNormalized();
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A0D30 (end 0x011A101C)
// Original VA: 0x00000001411A0D30 | File offset: 0x011A0330
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::execRInterpTo (Kismet function inlined); the vectorized
//   FRotator::GetNormalized and IsNearlyZero (Float360, Float180, SignMask).
FRotator FMath::RInterpTo( const FRotator& Current, const FRotator& Target, float DeltaTime, float InterpSpeed)
{
	// if DeltaTime is 0, do not perform any interpolation (Location was already calculated for that frame)
	if( DeltaTime == 0.f || Current == Target )
	{
		return Current;
	}

	// If no interp speed, jump to target value
	if( InterpSpeed <= 0.f )
	{
		return Target;
	}

	const float DeltaInterpSpeed = InterpSpeed * DeltaTime;

	const FRotator Delta = (Target - Current).GetNormalized();

	// If steps are too small, just return Target and assume we have reached our destination.
	if (Delta.IsNearlyZero())
	{
		return Target;
	}

	// Delta Move, Clamp so we do not over shoot.
	const FRotator DeltaMove = Delta * FMath::Clamp<float>(DeltaInterpSpeed, 0.f, 1.f);
	return (Current + DeltaMove).GetNormalized();
}

// FORCEINLINE_DEBUGGABLE (FORCEINLINE in shipping): inlined into both FindBetween functions.
__forceinline FQuat FindBetween_Helper(const FVector& A, const FVector& B, float NormAB)
{
	float W = NormAB + (A | B);   // FVector::DotProduct(A, B)
	FQuat Result;

	if (W >= 1e-6f * NormAB)
	{
		//Axis = FVector::CrossProduct(A, B);
		Result = FQuat(A.Y * B.Z - A.Z * B.Y,
					   A.Z * B.X - A.X * B.Z,
					   A.X * B.Y - A.Y * B.X,
					   W);
	}
	else
	{
		// A and B point in opposite directions
		W = 0.f;
		Result = FMath::Abs(A.X) > FMath::Abs(A.Y)
				? FQuat(-A.Z, 0.f, A.X, W)
				: FQuat(0.f, -A.Z, A.Y, W);
	}

	Result.Normalize();
	return Result;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011912C0 (end 0x0119145A)
// Original VA: 0x00000001411912C0 | File offset: 0x011908C0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: sorts between FInterpTo and FindBetweenVectors in Core's alphabetical run; the inlined
//   FindBetween_Helper with NormAB 1 and the vectorized FQuat::Normalize (Float0001, FloatOneHalf).
FQuat FQuat::FindBetweenNormals(const FVector& A, const FVector& B)
{
	const float NormAB = 1.f;
	return FindBetween_Helper(A, B, NormAB);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01191460 (end 0x0119165C)
// Original VA: 0x0000000141191460 | File offset: 0x01190A60
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: follows FindBetweenNormals; NormAB = Sqrt(|A|^2 |B|^2), then the same helper.
FQuat FQuat::FindBetweenVectors(const FVector& A, const FVector& B)
{
	const float NormAB = FMath::Sqrt(A.SizeSquared() * B.SizeSquared());
	return FindBetween_Helper(A, B, NormAB);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A5870 (end 0x011A5A48)
// Original VA: 0x00000001411A5870 | File offset: 0x011A4E70
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called twice by FQuat::Squad (0x011A5EF0); sorts before Slerp_NotNormalized
//   ("SlerpF" < "Slerp_"); acosf of the clamped dot product and three sinf.
FQuat FQuat::SlerpFullPath_NotNormalized(const FQuat &quat1, const FQuat &quat2, float Alpha )
{
	const float CosAngle = FMath::Clamp(quat1 | quat2, -1.f, 1.f);
	const float Angle = FMath::Acos(CosAngle);

	//UE_LOG(LogUnrealMath, Log,  TEXT("CosAngle: %f Angle: %f"), CosAngle, Angle );

	if ( FMath::Abs(Angle) < KINDA_SMALL_NUMBER )
	{
		return quat1;
	}

	const float SinAngle = FMath::Sin(Angle);
	const float InvSinAngle = 1.f/SinAngle;

	const float Scale0 = FMath::Sin((1.0f-Alpha)*Angle)*InvSinAngle;
	const float Scale1 = FMath::Sin(Alpha*Angle)*InvSinAngle;

	return quat1*Scale0 + quat2*Scale1;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A5EF0 (end 0x011A6017)
// Original VA: 0x00000001411A5EF0 | File offset: 0x011A54F0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: sorts after Slerp_NotNormalized; FQuat::Slerp_NotNormalized (0x011A5A50), then
//   SlerpFullPath_NotNormalized (0x011A5870) twice and the vectorized normalization.
FQuat FQuat::Squad(const FQuat& quat1, const FQuat& tang1, const FQuat& quat2, const FQuat& tang2, float Alpha)
{
	// Always slerp along the short path from quat1 to quat2 to prevent axis flipping.
	// This approach is taken by OGRE engine, amongst others.
	const FQuat Q1 = FQuat::Slerp_NotNormalized(quat1, quat2, Alpha);
	const FQuat Q2 = FQuat::SlerpFullPath_NotNormalized(tang1, tang2, Alpha);
	const FQuat Result = FQuat::SlerpFullPath(Q1, Q2, 2.f * Alpha * (1.f - Alpha));

	return Result;
}
