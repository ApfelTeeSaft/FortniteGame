// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: Core. Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/Core/Private/Math/UnrealMath.cpp.
// Reconstruction written from image evidence; see analysis/functions.json.

#define FNGC_CORE_MATH_EXTRAS 1   // FDateTime, FColor, FVector4, ... (MathDecls.h)
#include "FortniteGameCode/MathDecls.h"
#include "FortniteGameCode/ContainersRecovered.h"   // TArray (PointsAreCoplanar)
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

// FMatrix::Determinant is inline in Math/Matrix.inl; the reference calls one out-of-line copy
// (COMDAT), from an object not established. The member pointer below makes this unit emit it.
// Original FortniteClient-Win64-Shipping.exe: RVA 0x0064F030 (end 0x0064F1FC)
// Original VA: 0x000000014064F030 | File offset: 0x0064E630
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::Transform_Determinant (0x02094D80) on the matrix
//   ToMatrixWithScale builds; the scalar 4x4 cofactor expansion of Matrix.inl.
inline float FMatrix::Determinant() const
{
	return	M[0][0] * (
				M[1][1] * (M[2][2] * M[3][3] - M[2][3] * M[3][2]) -
				M[2][1] * (M[1][2] * M[3][3] - M[1][3] * M[3][2]) +
				M[3][1] * (M[1][2] * M[2][3] - M[1][3] * M[2][2])
				) -
			M[1][0] * (
				M[0][1] * (M[2][2] * M[3][3] - M[2][3] * M[3][2]) -
				M[2][1] * (M[0][2] * M[3][3] - M[0][3] * M[3][2]) +
				M[3][1] * (M[0][2] * M[2][3] - M[0][3] * M[2][2])
				) +
			M[2][0] * (
				M[0][1] * (M[1][2] * M[3][3] - M[1][3] * M[3][2]) -
				M[1][1] * (M[0][2] * M[3][3] - M[0][3] * M[3][2]) +
				M[3][1] * (M[0][2] * M[1][3] - M[0][3] * M[1][2])
				) -
			M[3][0] * (
				M[0][1] * (M[1][2] * M[2][3] - M[1][3] * M[2][2]) -
				M[1][1] * (M[0][2] * M[2][3] - M[0][3] * M[2][2]) +
				M[2][1] * (M[0][2] * M[1][3] - M[0][3] * M[1][2])
				);
}

#if FNGC_MATCHING_HARNESS
extern float (FMatrix::* const GFngcAnchor_Determinant)() const;
float (FMatrix::* const GFngcAnchor_Determinant)() const = &FMatrix::Determinant;
#endif

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01194110 (end 0x01194422)
// Original VA: 0x0000000141194110 | File offset: 0x01193710
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::GetAzimuthAndElevation (0x0207FDA0) with the reference
//   frame's unit axes; sorts between FixedTurn and FRotator::GetInverse; two safe normals
//   (FVector::ZeroVector), acosf and asinf of the clamped cosines.
FVector2D FMath::GetAzimuthAndElevation
(
	const FVector &Direction,
	const FVector &AxisX,
	const FVector &AxisY,
	const FVector &AxisZ
)
{
	const FVector NormalDir = Direction.GetSafeNormal();
	// Find projected point (on AxisX and AxisY, remove AxisZ component)
	const FVector NoZProjDir = (NormalDir - (NormalDir | AxisZ) * AxisZ).GetSafeNormal();
	// Figure out if projection is on right or left.
	const float AzimuthSign = ((NoZProjDir | AxisY) < 0.f) ? -1.f : 1.f;
	const float ElevationSin = NormalDir | AxisZ;
	const float AzimuthCos = NoZProjDir | AxisX;

	// Convert to Angles in Radian.
	return FVector2D(FMath::Acos(AzimuthCos) * AzimuthSign, FMath::Asin(ElevationSin));
}

// ---- Batch 10: date/time, colour and rotator helpers (generated by gen_core.py) ----

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A6820 (end 0x011A6B23)
// Original VA: 0x00000001411A6820 | File offset: 0x011A5E20
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: two Atan2 calls (FGenericPlatformMath::Atan2, 0x01112E50) and SinCos of the half angles.
FQuat FVector::ToOrientationQuat() const
{
	// Essentially an optimized Vector->Rotator->Quat made possible by knowing Roll == 0, and avoiding radians->degrees->radians.
	// This is done to avoid adding any roll (which our API states as a constraint).
	const float YawRad = FMath::Atan2(Y, X);
	const float PitchRad = FMath::Atan2(Z, FMath::Sqrt(X*X + Y*Y));

	const float DIVIDE_BY_2 = 0.5f;
	float SP, SY;
	float CP, CY;

	FMath::SinCos(&SP, &CP, PitchRad * DIVIDE_BY_2);
	FMath::SinCos(&SY, &CY, YawRad * DIVIDE_BY_2);

	FQuat RotationQuat;
	RotationQuat.X =  SP*SY;
	RotationQuat.Y = -SP*CY;
	RotationQuat.Z =  CP*SY;
	RotationQuat.W =  CP*CY;
	return RotationQuat;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01191080 (end 0x011912BD)
// Original VA: 0x0000000141191080 | File offset: 0x01190680
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: picks (1,0,0) or (0,0,1), then the safe normal of the projection and a cross product.
void FVector::FindBestAxisVectors( FVector& Axis1, FVector& Axis2 ) const
{
	const float NX = FMath::Abs(X);
	const float NY = FMath::Abs(Y);
	const float NZ = FMath::Abs(Z);

	// Find best basis vectors.
	if( NZ>NX && NZ>NY )	Axis1 = FVector(1,0,0);
	else					Axis1 = FVector(0,0,1);

	Axis1 = (Axis1 - *this * (Axis1 | *this)).GetSafeNormal();
	Axis2 = Axis1 ^ *this;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0118BBC0 (end 0x0118BC89)
// Original VA: 0x000000014118BBC0 | File offset: 0x0118B1C0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: clamped projection; sorts before ClosestPointOnSegment2D (0x0118BC90).
FVector FMath::ClosestPointOnLine(const FVector& LineStart, const FVector& LineEnd, const FVector& Point)
{
	// Solve to find alpha along line that is closest point
	// Weisstein, Eric W. "Point-Line Distance--3-Dimensional." From MathWorld--A Switchram Web Resource. http://mathworld.wolfram.com/Point-LineDistance3-Dimensional.html
	const float A = (LineStart - Point) | (LineEnd - LineStart);
	const float B = (LineEnd - LineStart).SizeSquared();
	// This should be robust to B == 0 (resulting in NaN) because clamp should return 1.
	const float T = FMath::Clamp(-A/B, 0.f, 1.f);

	// Generate closest point
	FVector ClosestPoint = LineStart + (T * (LineEnd - LineStart));

	return ClosestPoint;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011905D0 (end 0x011905E4), no .pdata (leaf)
// Original VA: 0x00000001411905D0 | File offset: 0x0118FBD0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: returns (Roll, Pitch, Yaw); called by FQuat::Euler (0x011905A0).
FVector FRotator::Euler() const
{
	return FVector( Roll, Pitch, Yaw );
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0119B670 (end 0x0119B684), no .pdata (leaf)
// Original VA: 0x000000014119B670 | File offset: 0x0119AC70
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: returns (Y, Z, X); sorts after FQuat::MakeFromEuler (0x0119B630).
FRotator FRotator::MakeFromEuler(const FVector& Euler)
{
	return FRotator(Euler.Y, Euler.Z, Euler.X);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A7250 (end 0x011A73B2)
// Original VA: 0x00000001411A7250 | File offset: 0x011A6850
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by execLessLess_VectorRotator; the out-of-line FRotationMatrix constructor
//   (0x009C4CB0), its transpose and VectorTransformVector.
FVector FRotator::UnrotateVector(const FVector& V) const
{
	return FRotationMatrix(*this).GetTransposed().TransformVector( V );
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A1DE0 (end 0x011A1E96)
// Original VA: 0x00000001411A1DE0 | File offset: 0x011A13E0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by execGreaterGreater_VectorRotator; the out-of-line FRotationMatrix
//   constructor (0x009C4CB0) and VectorTransformVector.
FVector FRotator::RotateVector(const FVector& V) const
{
	return FRotationMatrix(*this).TransformFVector4( FVector4(V, 0.f) );
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0119B630 (end 0x0119B66F)
// Original VA: 0x000000014119B630 | File offset: 0x0119AC30
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: FRotator::MakeFromEuler inlined, then FRotator::Quaternion (0x011A0970).
FQuat FQuat::MakeFromEuler(const FVector& Euler)
{
	return FRotator::MakeFromEuler(Euler).Quaternion();
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011905A0 (end 0x011905CC)
// Original VA: 0x00000001411905A0 | File offset: 0x0118FBA0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: FQuat::Rotator (0x011A2050), then FRotator::Euler (0x011905D0).
FVector FQuat::Euler() const
{
	return Rotator().Euler();
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0118BC90 (end 0x0118BD28), no .pdata (leaf)
// Original VA: 0x000000014118BC90 | File offset: 0x0118B290
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: 2D projection; sorts before ClosestPointOnSegment (0x0118BD30).
FVector2D FMath::ClosestPointOnSegment2D(const FVector2D &Point, const FVector2D &StartPoint, const FVector2D &EndPoint)
{
	const FVector2D Segment = EndPoint - StartPoint;
	const FVector2D VectToPoint = Point - StartPoint;

	// See if closest point is before StartPoint
	const float Dot1 = VectToPoint | Segment;
	if (Dot1 <= 0)
	{
		return StartPoint;
	}

	// See if closest point is beyond EndPoint
	const float Dot2 = Segment | Segment;
	if (Dot2 <= Dot1)
	{
		return EndPoint;
	}

	// Closest Point is within segment
	return StartPoint + Segment * (Dot1 / Dot2);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0119F6D0 (end 0x0119F726)
// Original VA: 0x000000014119F6D0 | File offset: 0x0119ECD0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: FMath::ClosestPointOnSegment (0x0118BD30), then SizeSquared; sorts after PointDistToSegment.
float FMath::PointDistToSegmentSquared(const FVector &Point, const FVector &StartPoint, const FVector &EndPoint)
{
	const FVector ClosestPoint = ClosestPointOnSegment(Point, StartPoint, EndPoint);
	return (Point - ClosestPoint).SizeSquared();
}

struct SegmentDistToSegment_Solver
{
	SegmentDistToSegment_Solver(const FVector& InA1, const FVector& InB1, const FVector& InA2, const FVector& InB2):
		bLinesAreNearlyParallel(false),
		A1(InA1),
		A2(InA2),
		S1(InB1 - InA1),
		S2(InB2 - InA2),
		S3(InA1 - InA2)
	{
	}

	bool bLinesAreNearlyParallel;

	const FVector& A1;
	const FVector& A2;

	const FVector S1;
	const FVector S2;
	const FVector S3;

	// Defined in the class; MSVC emits it out of line (a COMDAT both callers share).
// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A5BD0 (end 0x011A5E3E)
// Original VA: 0x00000001411A5BD0 | File offset: 0x011A51D0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by FMath::SegmentDistToSegment (0x011A2C90) and SegmentDistToSegmentSafe (0x011A2D70).
	void Solve(FVector& OutP1, FVector& OutP2)
	{
		const float Dot11 = S1 | S1;
		const float Dot12 = S1 | S2;
		const float Dot13 = S1 | S3;
		const float Dot22 = S2 | S2;
		const float Dot23 = S2 | S3;

		const float D = Dot11*Dot22 - Dot12*Dot12;

		float D1 = D;
		float D2 = D;

		float N1;
		float N2;

		if (bLinesAreNearlyParallel || D < KINDA_SMALL_NUMBER)
		{
			// the lines are almost parallel
			N1 = 0.f;	// force using point A on segment S1
			D1 = 1.f;	// to prevent possible division by 0 later
			N2 = Dot23;
			D2 = Dot22;
		}
		else
		{
			// get the closest points on the infinite lines
			N1 = (Dot12*Dot23 - Dot22*Dot13);
			N2 = (Dot11*Dot23 - Dot12*Dot13);

			if (N1 < 0.f)
			{
				// t1 < 0.f => the s==0 edge is visible
				N1 = 0.f;
				N2 = Dot23;
				D2 = Dot22;
			}
			else if (N1 > D1)
			{
				// t1 > 1 => the t1==1 edge is visible
				N1 = D1;
				N2 = Dot23 + Dot12;
				D2 = Dot22;
			}
		}

		if (N2 < 0.f)
		{
			// t2 < 0 => the t2==0 edge is visible
			N2 = 0.f;

			// recompute t1 for this edge
			if (-Dot13 < 0.f)
			{
				N1 = 0.f;
			}
			else if (-Dot13 > Dot11)
			{
				N1 = D1;
			}
			else
			{
				N1 = -Dot13;
				D1 = Dot11;
			}
		}
		else if (N2 > D2)
		{
			// t2 > 1 => the t2=1 edge is visible
			N2 = D2;

			// recompute t1 for this edge
			if ((-Dot13 + Dot12) < 0.f)
			{
				N1 = 0.f;
			}
			else if ((-Dot13 + Dot12) > Dot11)
			{
				N1 = D1;
			}
			else
			{
				N1 = (-Dot13 + Dot12);
				D1 = Dot11;
			}
		}

		// finally do the division to get the points' location
		const float T1 = (FMath::Abs(N1) < KINDA_SMALL_NUMBER ? 0.f : N1 / D1);
		const float T2 = (FMath::Abs(N2) < KINDA_SMALL_NUMBER ? 0.f : N2 / D2);

		// return the closest points
		OutP1 = A1 + T1 * S1;
		OutP2 = A2 + T2 * S2;
	}

};

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A2D70 (end 0x011A316E)
// Original VA: 0x00000001411A2D70 | File offset: 0x011A2370
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by execFindNearestPointsOnLineSegments; two safe normals, ClosestPointOnSegment, Solve.
void FMath::SegmentDistToSegmentSafe(FVector A1, FVector B1, FVector A2, FVector B2, FVector& OutP1, FVector& OutP2)
{
	SegmentDistToSegment_Solver Solver(A1, B1, A2, B2);

	const FVector S1_norm = Solver.S1.GetSafeNormal();
	const FVector S2_norm = Solver.S2.GetSafeNormal();

	const bool bS1IsPoint = S1_norm.IsZero();
	const bool bS2IsPoint = S2_norm.IsZero();

	if (bS1IsPoint && bS2IsPoint)
	{
		OutP1 = A1;
		OutP2 = A2;
	}
	else if (bS2IsPoint)
	{
		OutP1 = ClosestPointOnSegment(A2, A1, B1);
		OutP2 = A2;
	}
	else if (bS1IsPoint)
	{
		OutP1 = A1;
		OutP2 = ClosestPointOnSegment(A1, A2, B2);
	}
	else
	{
		const	float	Dot11_norm = S1_norm | S1_norm;	// always >= 0
		const	float	Dot22_norm = S2_norm | S2_norm;	// always >= 0
		const	float	Dot12_norm = S1_norm | S2_norm;
		const	float	D_norm	= Dot11_norm*Dot22_norm - Dot12_norm*Dot12_norm;	// always >= 0

		Solver.bLinesAreNearlyParallel = D_norm < KINDA_SMALL_NUMBER;
		Solver.Solve(OutP1, OutP2);
	}
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A2C90 (end 0x011A2D61)
// Original VA: 0x00000001411A2C90 | File offset: 0x011A2290
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: the solver's members, then Solve (0x011A5BD0); sorts before SegmentDistToSegmentSafe.
void FMath::SegmentDistToSegment(FVector A1, FVector B1, FVector A2, FVector B2, FVector& OutP1, FVector& OutP2)
{
	SegmentDistToSegment_Solver(A1, B1, A2, B2).Solve(OutP1, OutP2);
}

// No standalone copy in the reference: inlined into FMath::SegmentPlaneIntersection (0x011A32A0).
float FMath::GetTForSegmentPlaneIntersect(const FVector& StartPoint, const FVector& EndPoint, const FPlane& Plane)
{
	return ( Plane.W - (StartPoint|Plane) ) / ( (EndPoint - StartPoint)|Plane);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A32A0 (end 0x011A3388)
// Original VA: 0x00000001411A32A0 | File offset: 0x011A28A0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: GetTForSegmentPlaneIntersect inlined; the T window (-KINDA_SMALL_NUMBER, 1 + KINDA_SMALL_NUMBER).
bool FMath::SegmentPlaneIntersection(const FVector& StartPoint, const FVector& EndPoint, const FPlane& Plane, FVector& out_IntersectionPoint)
{
	float T = FMath::GetTForSegmentPlaneIntersect(StartPoint, EndPoint, Plane);
	// If the parameter value is not between 0 and 1, there is no intersection
	if (T > -KINDA_SMALL_NUMBER && T < 1.f + KINDA_SMALL_NUMBER)
	{
		out_IntersectionPoint = StartPoint + T * (EndPoint - StartPoint);
		return true;
	}
	return false;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0119F730 (end 0x0119F92E)
// Original VA: 0x000000014119F730 | File offset: 0x0119ED30
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by execPointsAreCoplanar; cross product of the first three points, PointPlaneDist loop.
bool FMath::PointsAreCoplanar(const TArray<FVector>& Points, const float Tolerance)
{
	//less than 4 points = coplanar
	if (Points.Num() < 4)
	{
		return true;
	}

	//Get the Normal for plane determined by first 3 points
	const FVector Normal = FVector::CrossProduct(Points[2] - Points[0], Points[1] - Points[0]).GetSafeNormal();

	const int32 Total = Points.Num();
	for (int32 v = 3; v < Total; v++)
	{
		//Abs of PointPlaneDist, dist should be 0
		if (FMath::Abs(FVector::PointPlaneDist(Points[v], Points[0], Normal)) > Tolerance)
		{
			return false;
		}
	}

	return true;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A1110 (end 0x011A11C1)
// Original VA: 0x00000001411A1110 | File offset: 0x011A0710
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: rand() rejection loop in the unit circle; sorts after RandPointInBox (0x011A1020).
FVector2D FMath::RandPointInCircle(float CircleRadius)
{
	FVector2D Point;
	float L;

	do
	{
		// Check random vectors in the unit circle so result is statistically uniform.
		Point.X = FRand() * 2.f - 1.f;
		Point.Y = FRand() * 2.f - 1.f;
		L = Point.SizeSquared();
	}
	while (L > 1.0f);

	return Point * CircleRadius;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A1020 (end 0x011A1104)
// Original VA: 0x00000001411A1020 | File offset: 0x011A0620
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: three FRandRange calls (rand); sorts before RandPointInCircle.
FVector FMath::RandPointInBox(const FBox& Box)
{
	return FVector(	FRandRange(Box.Min.X, Box.Max.X),
					FRandRange(Box.Min.Y, Box.Max.Y),
					FRandRange(Box.Min.Z, Box.Max.Z) );
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01195650 (end 0x01195904)
// Original VA: 0x0000000141195650 | File offset: 0x01194C50
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::GetReflectionVector (0x020828F0) and execMirrorVectorByNormal;
//   the surface normal's safe normal computed twice.
FVector FMath::GetReflectionVector(const FVector& Direction, const FVector& SurfaceNormal)
{
	return Direction - 2 * (Direction | SurfaceNormal.GetSafeNormal()) * SurfaceNormal.GetSafeNormal();
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011921F0 (end 0x011924E2)
// Original VA: 0x00000001411921F0 | File offset: 0x011917F0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by execFixedTurn; ClampAxis (Fmod, FmodReportError 0x0126F320) of both angles.
float FMath::FixedTurn(float InCurrent, float InDesired, float InDeltaRate)
{
	if (InDeltaRate == 0.f)
	{
		return FRotator::ClampAxis(InCurrent);
	}

	if (InDeltaRate >= 360.f)
	{
		return FRotator::ClampAxis(InDesired);
	}

	float result = FRotator::ClampAxis(InCurrent);
	InCurrent = result;
	InDesired = FRotator::ClampAxis(InDesired);

	if (InCurrent > InDesired)
	{
		if (InCurrent - InDesired < 180.f)
			result -= FMath::Min((InCurrent - InDesired), FMath::Abs(InDeltaRate));
		else
			result += FMath::Min((InDesired + 360.f - InCurrent), FMath::Abs(InDeltaRate));
	}
	else
	{
		if (InDesired - InCurrent < 180.f)
			result += FMath::Min((InDesired - InCurrent), FMath::Abs(InDeltaRate));
		else
			result -= FMath::Min((InCurrent + 360.f - InDesired), FMath::Abs(InDeltaRate));
	}
	return FRotator::ClampAxis(result);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0118B680 (end 0x0118B938)
// Original VA: 0x000000014118B680 | File offset: 0x0118AC80
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by execClampAngle; ClampAxis/NormalizeAxis inlined (FmodReportError 0x0126F320).
float FMath::ClampAngle(float AngleDegrees, float MinAngleDegrees, float MaxAngleDegrees)
{
	float const MaxDelta = FRotator::ClampAxis(MaxAngleDegrees - MinAngleDegrees) * 0.5f;			// 0..180
	float const RangeCenter = FRotator::ClampAxis(MinAngleDegrees + MaxDelta);						// 0..360
	float const DeltaFromCenter = FRotator::NormalizeAxis(AngleDegrees - RangeCenter);				// -180..180

	// maybe clamp to nearest edge
	if (DeltaFromCenter > MaxDelta)
	{
		return FRotator::NormalizeAxis(RangeCenter + MaxDelta);
	}
	else if (DeltaFromCenter < -MaxDelta)
	{
		return FRotator::NormalizeAxis(RangeCenter - MaxDelta);
	}

	// already in range, just return it
	return FRotator::NormalizeAxis(AngleDegrees);
}

// ---- end of batch 10 ----

// ---- Batch 11: transforms (generated by gen_core.py) ----
// The constants Math/UnrealMath.cpp defines that this batch's functions read. Their dynamic
// initializers: see analysis/functions.json ("dynamic initializer for FMatrix::Identity", ...).
const FMatrix FMatrix::Identity(FPlane(1,0,0,0),FPlane(0,1,0,0),FPlane(0,0,1,0),FPlane(0,0,0,1));

const FQuat FQuat::Identity(0,0,0,1);

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A6BB0 (end 0x011A6BCD)
// Original VA: 0x00000001411A6BB0 | File offset: 0x011A61B0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: FQuat(const FMatrix&) (0x00569390) into the return slot; of the two identical bodies, the one
//   sorting between ToOrientationRotator (0x011A6B30) and ToSwingTwist (0x011A6D10).
FQuat FMatrix::ToQuat() const
{
	FQuat Result(*this);
	return Result;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011A6D10 (end 0x011A6EF3)
// Original VA: 0x00000001411A6D10 | File offset: 0x011A6310
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: the twist axis projection, FQuat::Identity for a degenerate twist, the vectorized Normalize
//   and product; sorts after FMatrix::ToQuat.
void FQuat::ToSwingTwist(const FVector& InTwistAxis, FQuat& OutSwing, FQuat& OutTwist) const
{
	// Vector part projected onto twist axis
	FVector Projection = FVector::DotProduct(InTwistAxis, FVector(X, Y, Z)) * InTwistAxis;

	// Twist quaternion
	OutTwist = FQuat(Projection.X, Projection.Y, Projection.Z, W);

	// Singularity close to 180deg
	if(OutTwist.SizeSquared() == 0.0f)
	{
		OutTwist = FQuat::Identity;
	}
	else
	{
		OutTwist.Normalize();
	}

	// Set swing
	OutSwing = *this * OutTwist.Inverse();
}

// No standalone copy in the reference: inlined into FQuat::CalcTangents (0x0118B2F0).
FQuat FQuat::Log() const
{
	FQuat Result;
	Result.W = 0.f;

	if ( FMath::Abs(W) < 1.f )
	{
		const float Angle = FMath::Acos(W);
		const float SinAngle = FMath::Sin(Angle);

		if ( FMath::Abs(SinAngle) >= SMALL_NUMBER )
		{
			const float Scale = Angle/SinAngle;
			Result.X = Scale*X;
			Result.Y = Scale*Y;
			Result.Z = Scale*Z;

			return Result;
		}
	}

	Result.X = X;
	Result.Y = Y;
	Result.Z = Z;

	return Result;
}

// No standalone copy in the reference: inlined into FQuat::CalcTangents (0x0118B2F0).
FQuat FQuat::Exp() const
{
	const float Angle = FMath::Sqrt(X*X + Y*Y + Z*Z);
	const float SinAngle = FMath::Sin(Angle);

	FQuat Result;
	Result.W = FMath::Cos(Angle);

	if ( FMath::Abs(SinAngle) >= SMALL_NUMBER )
	{
		const float Scale = SinAngle/Angle;
		Result.X = Scale*X;
		Result.Y = Scale*Y;
		Result.Z = Scale*Z;
	}
	else
	{
		Result.X = X;
		Result.Y = Y;
		Result.Z = Z;
	}

	return Result;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0118B2F0 (end 0x0118B672)
// Original VA: 0x000000014118B2F0 | File offset: 0x0118A8F0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: FQuat::Log and Exp inlined (acosf, sinf, cosf); sorts between CInterpTo (0x0118B150) and
//   ClampAngle (0x0118B680).
void FQuat::CalcTangents(const FQuat& PrevP, const FQuat& P, const FQuat& NextP, float Tension, FQuat& OutTan)
{
	const FQuat InvP = P.Inverse();
	const FQuat Part1 = (InvP * PrevP).Log();
	const FQuat Part2 = (InvP * NextP).Log();

	const FQuat PreExp = (Part1 + Part2) * -0.5f;

	OutTan = P * PreExp.Exp();
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0118B940 (end 0x0118BAD1)
// Original VA: 0x000000014118B940 | File offset: 0x0118AF40
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: the 4.20 body (crest test, the 0.333 clamp threshold); sorts after ClampAngle (0x0118B680).
float ClampFloatTangent( float PrevPointVal, float PrevTime, float CurPointVal, float CurTime, float NextPointVal, float NextTime )
{
	const float PrevToNextTimeDiff = FMath::Max< double >( KINDA_SMALL_NUMBER, NextTime - PrevTime );
	const float PrevToCurTimeDiff = FMath::Max< double >( KINDA_SMALL_NUMBER, CurTime - PrevTime );
	const float CurToNextTimeDiff = FMath::Max< double >( KINDA_SMALL_NUMBER, NextTime - CurTime );

	float OutTangentVal = 0.0f;

	const float PrevToNextHeightDiff = NextPointVal - PrevPointVal;
	const float PrevToCurHeightDiff = CurPointVal - PrevPointVal;
	const float CurToNextHeightDiff = NextPointVal - CurPointVal;

	// Check to see if the current point is crest
	if( ( PrevToCurHeightDiff >= 0.0f && CurToNextHeightDiff <= 0.0f ) ||
		( PrevToCurHeightDiff <= 0.0f && CurToNextHeightDiff >= 0.0f ) )
	{
		// Neighbor points are both both on the same side, so zero out the tangent
		OutTangentVal = 0.0f;
	}
	else
	{
		// The three points form a slope

		// Constants
		const float ClampThreshold = 0.333f;

		// Compute height deltas
		const float CurToNextTangent = CurToNextHeightDiff / CurToNextTimeDiff;
		const float PrevToCurTangent = PrevToCurHeightDiff / PrevToCurTimeDiff;
		const float PrevToNextTangent = PrevToNextHeightDiff / PrevToNextTimeDiff;

		// Default to not clamping
		const float UnclampedTangent = PrevToNextTangent;
		float ClampedTangent = UnclampedTangent;

		const float LowerClampThreshold = ClampThreshold;
		const float UpperClampThreshold = 1.0f - ClampThreshold;

		// @todo: Would we get better results using percentange of TIME instead of HEIGHT?
		const float CurHeightAlpha = PrevToCurHeightDiff / PrevToNextHeightDiff;

		if( PrevToNextHeightDiff > 0.0f )
		{
			if( CurHeightAlpha < LowerClampThreshold )
			{
				// 1.0 = maximum clamping (flat), 0.0 = minimal clamping (don't touch)
				const float ClampAlpha = 1.0f - CurHeightAlpha / ClampThreshold;
				const float LowerClamp = FMath::Lerp( PrevToNextTangent, PrevToCurTangent, ClampAlpha );
				ClampedTangent = FMath::Min( ClampedTangent, LowerClamp );
			}

			if( CurHeightAlpha > UpperClampThreshold )
			{
				// 1.0 = maximum clamping (flat), 0.0 = minimal clamping (don't touch)
				const float ClampAlpha = ( CurHeightAlpha - UpperClampThreshold ) / ClampThreshold;
				const float UpperClamp = FMath::Lerp( PrevToNextTangent, CurToNextTangent, ClampAlpha );
				ClampedTangent = FMath::Min( ClampedTangent, UpperClamp );
			}
		}
		else
		{

			if( CurHeightAlpha < LowerClampThreshold )
			{
				// 1.0 = maximum clamping (flat), 0.0 = minimal clamping (don't touch)
				const float ClampAlpha = 1.0f - CurHeightAlpha / ClampThreshold;
				const float LowerClamp = FMath::Lerp( PrevToNextTangent, PrevToCurTangent, ClampAlpha );
				ClampedTangent = FMath::Max( ClampedTangent, LowerClamp );
			}

			if( CurHeightAlpha > UpperClampThreshold )
			{
				// 1.0 = maximum clamping (flat), 0.0 = minimal clamping (don't touch)
				const float ClampAlpha = ( CurHeightAlpha - UpperClampThreshold ) / ClampThreshold;
				const float UpperClamp = FMath::Lerp( PrevToNextTangent, CurToNextTangent, ClampAlpha );
				ClampedTangent = FMath::Max( ClampedTangent, UpperClamp );
			}
		}

		OutTangentVal = ClampedTangent;
	}

	return OutTangentVal;
}

// Math/TransformVectorized.cpp is part of this unit (see its header).
#include "TransformVectorized.cpp"

// ---- end of batch 11 ----
