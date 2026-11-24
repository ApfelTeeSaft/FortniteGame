// ABI declarations of Core math types and functions recovered math code uses (Math/Vector.h,
// Rotator.h, UnrealMathUtility.h, GenericPlatform/GenericPlatformMath.h). Not recovered code. Only
// the members recovered code defines or calls are declared; the inline helpers are the 4.20
// forms the reference's code shows (fabsf/sqrtf become andps/sqrtss under /fp:fast).
#pragma once

#include <math.h>

#define PI (3.1415926535897932f)

struct FGenericPlatformMath
{
	static float Atan2(float Y, float X);

	static __forceinline float Abs(const float A) { return fabsf(A); }   // the float specialization
	static __forceinline float Sqrt(float Value) { return sqrtf(Value); }
};

// FMath derives from FPlatformMath (FWindowsPlatformMath : FGenericPlatformMath).
struct FMath : public FGenericPlatformMath
{
};

struct FRotator
{
	float Pitch;
	float Yaw;
	float Roll;
	__forceinline FRotator() { }
};

struct FVector
{
	float X;
	float Y;
	float Z;

	FRotator ToOrientationRotator() const;
	FRotator Rotation() const;
};
