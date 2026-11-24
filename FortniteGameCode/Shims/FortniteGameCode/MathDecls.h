// ABI declarations of Core math types and functions recovered math code uses (Math/Vector.h,
// Rotator.h, UnrealMathUtility.h, GenericPlatform/GenericPlatformMath.h). Not recovered code. Only
// the members recovered code defines or calls are declared; the inline helpers are the 4.20
// forms the reference's code shows (fabsf/sqrtf become andps/sqrtss under /fp:fast).
#pragma once

#include <math.h>
#include <stdlib.h>

// UnrealMathUtility.h constants.
#define PI 					(3.1415926535897932f)
#define KINDA_SMALL_NUMBER	(1.e-4f)
#define INV_PI				(0.31830988618f)
#define HALF_PI				(1.57079632679f)

struct FVector;
struct FRotator;

struct FGenericPlatformMath
{
	static float Atan2(float Y, float X);

	static __forceinline float Abs(const float A) { return fabsf(A); }   // the float specialization
	static __forceinline float Sqrt(float Value) { return sqrtf(Value); }
	static __forceinline int Rand() { return rand(); }
	static __forceinline float FRand() { return Rand() / (float)RAND_MAX; }
};

// FMath derives from FPlatformMath (FWindowsPlatformMath : FGenericPlatformMath).
struct FMath : public FGenericPlatformMath
{
	static FVector VRand();   // inline in Math/Vector.h

	template<class T>
	static __forceinline auto DegreesToRadians(T const& DegVal) -> decltype(DegVal * (PI / 180.f))
	{
		return DegVal * (PI / 180.f);
	}

	static __forceinline void SinCos(float* ScalarSin, float* ScalarCos, float Value)
	{
		// Map Value to y in [-pi,pi], x = 2*pi*quotient + remainder.
		float quotient = (INV_PI*0.5f)*Value;
		if (Value >= 0.0f)
		{
			quotient = (float)((int)(quotient + 0.5f));
		}
		else
		{
			quotient = (float)((int)(quotient - 0.5f));
		}
		float y = Value - (2.0f*PI)*quotient;

		// Map y to [-pi/2,pi/2] with sin(y) = sin(Value).
		float sign;
		if (y > HALF_PI)
		{
			y = PI - y;
			sign = -1.0f;
		}
		else if (y < -HALF_PI)
		{
			y = -PI - y;
			sign = -1.0f;
		}
		else
		{
			sign = +1.0f;
		}

		float y2 = y * y;

		// 11-degree minimax approximation
		*ScalarSin = ( ( ( ( (-2.3889859e-08f * y2 + 2.7525562e-06f) * y2 - 0.00019840874f ) * y2 + 0.0083333310f ) * y2 - 0.16666667f ) * y2 + 1.0f ) * y;

		// 10-degree minimax approximation
		float p = ( ( ( ( -2.6051615e-07f * y2 + 2.4760495e-05f ) * y2 - 0.0013888378f ) * y2 + 0.041666638f ) * y2 - 0.5f ) * y2 + 1.0f;
		*ScalarCos = sign*p;
	}
};

struct FRotator
{
	float Pitch;
	float Yaw;
	float Roll;
	__forceinline FRotator() { }

	FVector Vector() const;
};

struct FVector
{
	float X;
	float Y;
	float Z;

	__forceinline FVector() { }
	__forceinline FVector(float InX, float InY, float InZ) : X(InX), Y(InY), Z(InZ) { }   // DiagnosticCheckNaN() is empty in shipping

	__forceinline float SizeSquared() const { return X*X + Y*Y + Z*Z; }
	__forceinline FVector operator*(float Scale) const { return FVector(X * Scale, Y * Scale, Z * Scale); }

	FRotator ToOrientationRotator() const;
	FRotator Rotation() const;
};
