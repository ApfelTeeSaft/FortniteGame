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
