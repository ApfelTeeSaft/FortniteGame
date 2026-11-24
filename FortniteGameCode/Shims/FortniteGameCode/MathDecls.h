// ABI declarations of Core math types and functions recovered code uses: Math/Vector.h,
// Vector2D.h, Rotator.h, Box.h, Color.h, RandomStream.h, UnrealMathUtility.h,
// GenericPlatform/GenericPlatformMath.h, Windows/WindowsPlatformMath.h, UnrealPlatformMathSSE.h,
// Misc/Timespan.h. Not recovered code. Only the members recovered code defines or calls are
// declared; the inline helpers are the 4.20 forms the reference's code shows (fabsf/sqrtf become
// andps/sqrtss under /fp:fast). Shared by Core's recovered math and, through ScriptRecovered.h,
// by the UHT world, so both see one definition of each type.
#pragma once

#include <math.h>
#include <stdlib.h>
#include <xmmintrin.h>   // as UnrealPlatformMathSSE.h

// Windows/WindowsPlatformCompilerSetup.h disables this for all UE4 code (FMath::MakePulsatingValue
// narrows its double expression).
#pragma warning(disable : 4244) // 'expression' : conversion from 'type' to 'type', possible loss of data
// Windows/WindowsPlatform.h: disabled for all UE4 code (FmodReportError's body is compiled out).
#pragma warning(disable : 4100) // unreferenced formal parameter

typedef int int32;
typedef unsigned int uint32;
typedef unsigned char uint8;
typedef long long int64;

// UnrealMathUtility.h constants (VectorRecovered.h defines the same ones for the unity units).
#ifndef PI
#define PI 					(3.1415926535897932f)
#endif
#ifndef SMALL_NUMBER
#define SMALL_NUMBER		(1.e-8f)
#endif
#ifndef KINDA_SMALL_NUMBER
#define KINDA_SMALL_NUMBER	(1.e-4f)
#endif
#ifndef DELTA
#define DELTA			(0.00001f)
#endif
#define INV_PI				(0.31830988618f)
#define HALF_PI				(1.57079632679f)

// Misc/CoreMiscDefines.h
enum { INDEX_NONE = -1 };
enum EForceInit { ForceInit, ForceInitToZero };

struct FVector;
struct FVector2D;
struct FRotator;
struct FLinearColor;
struct FQuat;
template<typename InElementType, typename InAllocator> class TArray;

struct FGenericPlatformMath
{
	static float Atan2(float Y, float X);

	static __forceinline int32 TruncToInt(float F) { return (int32)F; }
	static __forceinline float TruncToFloat(float F) { return (float)TruncToInt(F); }

	static __forceinline float Exp( float Value ) { return expf(Value); }
	static __forceinline float Loge( float Value ) {	return logf(Value); }
	static __forceinline float Sin( float Value ) { return sinf(Value); }
	static __forceinline float Cos( float Value ) { return cosf(Value); }
	static __forceinline float Pow( float A, float B ) { return powf(A,B); }
	static __forceinline float Sqrt(float Value) { return sqrtf(Value); }

	static __forceinline float Fractional(float Value) { return Value - TruncToFloat(Value); }

	static __forceinline int32 Rand() { return rand(); }
	static __forceinline float FRand() { return Rand() / (float)RAND_MAX; }

	template< class T >
	static constexpr __forceinline T Abs( const T A ) { return (A>=(T)0) ? A : -A; }
	static __forceinline float Abs(const float A) { return fabsf(A); }   // the float specialization

	template< class T >
	static constexpr __forceinline T Max( const T A, const T B ) { return (A>=B) ? A : B; }
	template< class T >
	static constexpr __forceinline T Min( const T A, const T B ) { return (A<=B) ? A : B; }

	// The TArray overloads (the allocator is a parameter so they need no definition of TArray here).
	template< class T, class A >
	static __forceinline T Min(const TArray<T, A>& Values, int32* MinIndex = nullptr)
	{
		if (Values.Num() == 0)
		{
			if (MinIndex)
			{
				*MinIndex = INDEX_NONE;
			}
			return T();
		}

		T CurMin = Values[0];
		int32 CurMinIndex = 0;
		for (int32 v = 1; v < Values.Num(); ++v)
		{
			const T Value = Values[v];
			if (Value < CurMin)
			{
				CurMin = Value;
				CurMinIndex = v;
			}
		}

		if (MinIndex)
		{
			*MinIndex = CurMinIndex;
		}
		return CurMin;
	}

	template< class T, class A >
	static __forceinline T Max(const TArray<T, A>& Values, int32* MaxIndex = nullptr)
	{
		if (Values.Num() == 0)
		{
			if (MaxIndex)
			{
				*MaxIndex = INDEX_NONE;
			}
			return T();
		}

		T CurMax = Values[0];
		int32 CurMaxIndex = 0;
		for (int32 v = 1; v < Values.Num(); ++v)
		{
			const T Value = Values[v];
			if (CurMax < Value)
			{
				CurMax = Value;
				CurMaxIndex = v;
			}
		}

		if (MaxIndex)
		{
			*MaxIndex = CurMaxIndex;
		}
		return CurMax;
	}

	static __forceinline float Fmod(float X, float Y)
	{
		if (fabsf(Y) <= 1.e-8f)
		{
			FmodReportError(X, Y);
			return 0.f;
		}
		const float Quotient = TruncToFloat(X / Y);
		float IntPortion = Y * Quotient;

		// Rounding and imprecision could cause IntPortion to exceed X and cause the result to be outside the expected range.
		if (fabsf(IntPortion) > fabsf(X))
		{
			IntPortion = X;
		}

		const float Result = X - IntPortion;
		return Result;
	}

private:
	static void FmodReportError(float X, float Y);   // CORE_API; empty in shipping (ensure is compiled out)
};

// Windows/WindowsPlatformMath.h (PLATFORM_ENABLE_VECTORINTRINSICS).
struct FWindowsPlatformMath : public FGenericPlatformMath
{
	static __forceinline int32 TruncToInt(float F)
	{
		return _mm_cvtt_ss2si(_mm_set_ss(F));
	}
	static __forceinline float TruncToFloat( float F )
	{
		return (float)TruncToInt(F); // same as generic implementation, but this will call the faster trunc
	}
	static __forceinline int32 RoundToInt( float F )
	{
		return _mm_cvt_ss2si( _mm_set_ss(F + F + 0.5f) ) >> 1;
	}
	static __forceinline int32 FloorToInt(float F)
	{
		return _mm_cvt_ss2si(_mm_set_ss(F + F - 0.5f)) >> 1;
	}
	static __forceinline float FloorToFloat(float F)
	{
		return (float)FloorToInt(F);
	}
	static __forceinline float InvSqrt(float F)
	{
		// UnrealPlatformMathSSE::InvSqrt
		const __m128 fOneHalf = _mm_set_ss(0.5f);
		__m128 Y0, X0, X1, X2, FOver2;
		float temp;

		Y0 = _mm_set_ss(F);
		X0 = _mm_rsqrt_ss(Y0);	// 1/sqrt estimate (12 bits)
		FOver2 = _mm_mul_ss(Y0, fOneHalf);

		// 1st Newton-Raphson iteration
		X1 = _mm_mul_ss(X0, X0);
		X1 = _mm_sub_ss(fOneHalf, _mm_mul_ss(FOver2, X1));
		X1 = _mm_add_ss(X0, _mm_mul_ss(X0, X1));

		// 2nd Newton-Raphson iteration
		X2 = _mm_mul_ss(X1, X1);
		X2 = _mm_sub_ss(fOneHalf, _mm_mul_ss(FOver2, X2));
		X2 = _mm_add_ss(X1, _mm_mul_ss(X1, X2));

		_mm_store_ss(&temp, X2);
		return temp;
	}
};
typedef FWindowsPlatformMath FPlatformMath;

// FMath (Math/UnrealMathUtility.h) derives from FPlatformMath.
struct FMath : public FPlatformMath
{
	static FVector VRand();   // inline in Math/Vector.h

	static __forceinline float FRandRange(float InMin, float InMax)
	{
		return InMin + (InMax - InMin) * FRand();
	}

	static __forceinline float Asin( float Value ) { return asinf( (Value<-1.f) ? -1.f : ((Value<1.f) ? Value : 1.f) ); }
	static __forceinline float Acos( float Value ) { return acosf( (Value<-1.f) ? -1.f : ((Value<1.f) ? Value : 1.f) ); }

	static __forceinline float FloatSelect( float Comparand, float ValueGEZero, float ValueLTZero )
	{
		return Comparand >= 0.f ? ValueGEZero : ValueLTZero;
	}

#define FASTASIN_HALF_PI (1.5707963050f)
	static __forceinline float FastAsin(float Value)
	{
		// Clamp input to [-1,1].
		bool nonnegative = (Value >= 0.0f);
		float x = FMath::Abs(Value);
		float omx = 1.0f - x;
		if (omx < 0.0f)
		{
			omx = 0.0f;
		}
		float root = FMath::Sqrt(omx);
		// 7-degree minimax approximation
		float result = ((((((-0.0012624911f * x + 0.0066700901f) * x - 0.0170881256f) * x + 0.0308918810f) * x - 0.0501743046f) * x + 0.0889789874f) * x - 0.2145988016f) * x + FASTASIN_HALF_PI;
		result *= root;  // acos(|x|)
		// acos(x) = pi - acos(-x) when x < 0, asin(x) = pi/2 - acos(x)
		return (nonnegative ? FASTASIN_HALF_PI - result : result - FASTASIN_HALF_PI);
	}
#undef FASTASIN_HALF_PI

	template< class T >
	static __forceinline T Square( const T A ) { return A*A; }

	static __forceinline bool IsNearlyEqual(float A, float B, float ErrorTolerance = SMALL_NUMBER)
	{
		return Abs<float>( A - B ) <= ErrorTolerance;
	}

	static __forceinline bool IsNearlyZero(float Value, float ErrorTolerance = SMALL_NUMBER)
	{
		return Abs<float>( Value ) <= ErrorTolerance;
	}

	// Defined after FVector2D (Math/Vector2D.h).
	static float GetRangePct(FVector2D const& Range, float Value);
	static float GetRangeValue(FVector2D const& Range, float Pct);

	static __forceinline float GetMappedRangeValueClamped(const FVector2D& InputRange, const FVector2D& OutputRange, const float Value)
	{
		const float ClampedPct = Clamp<float>(GetRangePct(InputRange, Value), 0.f, 1.f);
		return GetRangeValue(OutputRange, ClampedPct);
	}

	static __forceinline float GetMappedRangeValueUnclamped(const FVector2D& InputRange, const FVector2D& OutputRange, const float Value)
	{
		return GetRangeValue(OutputRange, GetRangePct(InputRange, Value));
	}

	template< class T >
	static __forceinline T Clamp( const T X, const T Min, const T Max )
	{
		return X<Min ? Min : X<Max ? X : Max;
	}

	template<class T>
	static __forceinline auto RadiansToDegrees(T const& RadVal) -> decltype(RadVal * (180.f / PI))
	{
		return RadVal * (180.f / PI);
	}

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

	template< class T, class U >
	static __forceinline T Lerp( const T& A, const T& B, const U& Alpha )
	{
		return (T)(A + Alpha * (B-A));
	}

	template< class T >
	static __forceinline T InterpEaseIn(const T& A, const T& B, float Alpha, float Exp)
	{
		float const ModifiedAlpha = Pow(Alpha, Exp);
		return Lerp<T>(A, B, ModifiedAlpha);
	}

	template< class T >
	static __forceinline T InterpEaseOut(const T& A, const T& B, float Alpha, float Exp)
	{
		float const ModifiedAlpha = 1.f - Pow(1.f - Alpha, Exp);
		return Lerp<T>(A, B, ModifiedAlpha);
	}

	template< class T >
	static __forceinline T InterpEaseInOut( const T& A, const T& B, float Alpha, float Exp )
	{
		return Lerp<T>(A, B, (Alpha < 0.5f) ?
			InterpEaseIn(0.f, 1.f, Alpha * 2.f, Exp) * 0.5f :
			InterpEaseOut(0.f, 1.f, Alpha * 2.f - 1.f, Exp) * 0.5f + 0.5f);
	}

	template< class T >
	static __forceinline T InterpStep(const T& A, const T& B, float Alpha, int32 Steps)
	{
		if (Steps <= 1 || Alpha <= 0)
		{
			return A;
		}
		else if (Alpha >= 1)
		{
			return B;
		}

		const float StepsAsFloat = static_cast<float>(Steps);
		const float NumIntervals = StepsAsFloat - 1.f;
		float const ModifiedAlpha = FloorToFloat(Alpha * StepsAsFloat) / NumIntervals;
		return Lerp<T>(A, B, ModifiedAlpha);
	}

	template< class T >
	static __forceinline T InterpSinIn(const T& A, const T& B, float Alpha)
	{
		float const ModifiedAlpha = -1.f * Cos(Alpha * HALF_PI) + 1.f;
		return Lerp<T>(A, B, ModifiedAlpha);
	}

	template< class T >
	static __forceinline T InterpSinOut(const T& A, const T& B, float Alpha)
	{
		float const ModifiedAlpha = Sin(Alpha * HALF_PI);
		return Lerp<T>(A, B, ModifiedAlpha);
	}

	template< class T >
	static __forceinline T InterpSinInOut(const T& A, const T& B, float Alpha)
	{
		return Lerp<T>(A, B, (Alpha < 0.5f) ?
			InterpSinIn(0.f, 1.f, Alpha * 2.f) * 0.5f :
			InterpSinOut(0.f, 1.f, Alpha * 2.f - 1.f) * 0.5f + 0.5f);
	}

	template< class T >
	static __forceinline T InterpExpoIn(const T& A, const T& B, float Alpha)
	{
		float const ModifiedAlpha = (Alpha == 0.f) ? 0.f : Pow(2.f, 10.f * (Alpha - 1.f));
		return Lerp<T>(A, B, ModifiedAlpha);
	}

	template< class T >
	static __forceinline T InterpExpoOut(const T& A, const T& B, float Alpha)
	{
		float const ModifiedAlpha = (Alpha == 1.f) ? 1.f : -Pow(2.f, -10.f * Alpha) + 1.f;
		return Lerp<T>(A, B, ModifiedAlpha);
	}

	template< class T >
	static __forceinline T InterpExpoInOut(const T& A, const T& B, float Alpha)
	{
		return Lerp<T>(A, B, (Alpha < 0.5f) ?
			InterpExpoIn(0.f, 1.f, Alpha * 2.f) * 0.5f :
			InterpExpoOut(0.f, 1.f, Alpha * 2.f - 1.f) * 0.5f + 0.5f);
	}

	template< class T >
	static __forceinline T InterpCircularIn(const T& A, const T& B, float Alpha)
	{
		float const ModifiedAlpha = -1.f * (Sqrt(1.f - Alpha * Alpha) - 1.f);
		return Lerp<T>(A, B, ModifiedAlpha);
	}

	template< class T >
	static __forceinline T InterpCircularOut(const T& A, const T& B, float Alpha)
	{
		Alpha -= 1.f;
		float const ModifiedAlpha = Sqrt(1.f - Alpha  * Alpha);
		return Lerp<T>(A, B, ModifiedAlpha);
	}

	template< class T >
	static __forceinline T InterpCircularInOut(const T& A, const T& B, float Alpha)
	{
		return Lerp<T>(A, B, (Alpha < 0.5f) ?
			InterpCircularIn(0.f, 1.f, Alpha * 2.f) * 0.5f :
			InterpCircularOut(0.f, 1.f, Alpha * 2.f - 1.f) * 0.5f + 0.5f);
	}

	static float MakePulsatingValue( const double InCurrentTime, const float InPulsesPerSecond, const float InPhase = 0.0f )
	{
		return 0.5f + 0.5f * FMath::Sin( ( ( 0.25f + InPhase ) * PI * 2.0 ) + ( InCurrentTime * PI * 2.0 ) * InPulsesPerSecond );
	}

	// Out of line in Core (Math/UnrealMath.cpp, CORE_API).
	static FVector ClosestPointOnSegment(const FVector &Point, const FVector &StartPoint, const FVector &EndPoint);
	static float PointDistToSegment(const FVector &Point, const FVector &StartPoint, const FVector &EndPoint);
	static float PointDistToLine(const FVector &Point, const FVector &Direction, const FVector &Origin);
	static FLinearColor CInterpTo(const FLinearColor& Current, const FLinearColor& Target, float DeltaTime, float InterpSpeed);
	static FVector VInterpConstantTo(const FVector Current, const FVector& Target, float DeltaTime, float InterpSpeed);
	static FVector VInterpTo( const FVector& Current, const FVector& Target, float DeltaTime, float InterpSpeed );
	static FVector2D Vector2DInterpConstantTo( const FVector2D& Current, const FVector2D& Target, float DeltaTime, float InterpSpeed );
	static FVector2D Vector2DInterpTo( const FVector2D& Current, const FVector2D& Target, float DeltaTime, float InterpSpeed );
	static float FInterpTo( float Current, float Target, float DeltaTime, float InterpSpeed );
	static float FInterpConstantTo( float Current, float Target, float DeltaTime, float InterpSpeed );
	static FRotator RInterpConstantTo( const FRotator& Current, const FRotator& Target, float DeltaTime, float InterpSpeed );
	static FRotator RInterpTo( const FRotator& Current, const FRotator& Target, float DeltaTime, float InterpSpeed);
	static FVector2D GetAzimuthAndElevation(const FVector &Direction, const FVector &AxisX, const FVector &AxisY, const FVector &AxisZ);
};

struct FRotator
{
	float Pitch;
	float Yaw;
	float Roll;
	__forceinline FRotator() { }
	__forceinline FRotator( float InPitch, float InYaw, float InRoll ) : Pitch(InPitch), Yaw(InYaw), Roll(InRoll) { }
	explicit FRotator( const FQuat& Quat );   // CORE_API, Math/UnrealMath.cpp

	__forceinline FRotator operator+( const FRotator& R ) const
	{
		return FRotator( Pitch+R.Pitch, Yaw+R.Yaw, Roll+R.Roll );
	}
	__forceinline FRotator operator-( const FRotator& R ) const
	{
		return FRotator( Pitch-R.Pitch, Yaw-R.Yaw, Roll-R.Roll );
	}
	__forceinline FRotator operator*( float Scale ) const
	{
		return FRotator( Pitch*Scale, Yaw*Scale, Roll*Scale );
	}

	__forceinline bool operator==( const FRotator& R ) const
	{
		return Pitch==R.Pitch && Yaw==R.Yaw && Roll==R.Roll;
	}

	// VectorRegister forms (PLATFORM_ENABLE_VECTORINTRINSICS): QuatRecovered.h.
	void Normalize();
	FRotator GetNormalized() const;
	bool IsNearlyZero(float Tolerance=KINDA_SMALL_NUMBER) const;

	FVector Vector() const;
	FQuat Quaternion() const;   // CORE_API (vectorized; out of line)
	FRotator GetInverse() const;   // CORE_API

	static float ClampAxis( float Angle );
	static float NormalizeAxis( float Angle );
};

__forceinline FRotator operator*( float Scale, const FRotator& R )
{
	return R.operator*( Scale );
}

__forceinline float FRotator::ClampAxis( float Angle )
{
	// returns Angle in the range (-360,360)
	Angle = FMath::Fmod(Angle, 360.f);

	if (Angle < 0.f)
	{
		// shift to [0,360) range
		Angle += 360.f;
	}

	return Angle;
}

__forceinline float FRotator::NormalizeAxis( float Angle )
{
	// returns Angle in the range [0,360)
	Angle = ClampAxis(Angle);

	if (Angle > 180.f)
	{
		// shift to (-180,180]
		Angle -= 360.f;
	}

	return Angle;
}

// Math/Vector.h. DiagnosticCheckNaN() is empty in shipping.
struct FVector
{
	float X;
	float Y;
	float Z;

	static const FVector ZeroVector;   // CORE_API

	__forceinline FVector() { }
	explicit __forceinline FVector(float InF) : X(InF), Y(InF), Z(InF) { }
	__forceinline FVector(float InX, float InY, float InZ) : X(InX), Y(InY), Z(InZ) { }
	explicit __forceinline FVector(EForceInit) : X(0.0f), Y(0.0f), Z(0.0f) {}

	__forceinline FVector operator-() const { return FVector(-X, -Y, -Z); }
	__forceinline FVector operator+(const FVector& V) const { return FVector(X + V.X, Y + V.Y, Z + V.Z); }
	__forceinline FVector operator-(const FVector& V) const { return FVector(X - V.X, Y - V.Y, Z - V.Z); }
	__forceinline FVector operator*(float Scale) const { return FVector(X * Scale, Y * Scale, Z * Scale); }
	__forceinline FVector operator/(float Scale) const
	{
		const float RScale = 1.f/Scale;
		return FVector(X * RScale, Y * RScale, Z * RScale);
	}
	__forceinline float operator|(const FVector& V) const { return X*V.X + Y*V.Y + Z*V.Z; }
	__forceinline FVector operator^(const FVector& V) const
	{
		return FVector
			(
			Y * V.Z - Z * V.Y,
			Z * V.X - X * V.Z,
			X * V.Y - Y * V.X
			);
	}
	__forceinline FVector operator+=(const FVector& V)
	{
		X += V.X; Y += V.Y; Z += V.Z;
		return *this;
	}

	__forceinline float Size() const { return FMath::Sqrt(X*X + Y*Y + Z*Z); }
	__forceinline float SizeSquared() const { return X*X + Y*Y + Z*Z; }

	__forceinline FVector GetSafeNormal(float Tolerance = SMALL_NUMBER) const
	{
		const float SquareSum = X*X + Y*Y + Z*Z;

		// Not sure if it's safe to add tolerance in there. Might introduce too many errors
		if(SquareSum == 1.f)
		{
			return *this;
		}
		else if(SquareSum < Tolerance)
		{
			return FVector::ZeroVector;
		}
		const float Scale = FMath::InvSqrt(SquareSum);
		return FVector(X*Scale, Y*Scale, Z*Scale);
	}

	__forceinline FVector GetClampedToSize(float Min, float Max) const;

	__forceinline bool Normalize(float Tolerance=SMALL_NUMBER)
	{
		const float SquareSum = X*X + Y*Y + Z*Z;
		if(SquareSum > Tolerance)
		{
			const float Scale = FMath::InvSqrt(SquareSum);
			X *= Scale; Y *= Scale; Z *= Scale;
			return true;
		}
		return false;
	}

	// Inline in Math/Vector.h; the reference calls an out-of-line copy, defined in UnrealMath.cpp.
	FVector RotateAngleAxis( const float AngleDeg, const FVector& Axis ) const;

	FRotator ToOrientationRotator() const;
	FRotator Rotation() const;
};

__forceinline FVector operator*(float Scale, const FVector& V)
{
	return V.operator*(Scale);
}

__forceinline FVector FVector::GetClampedToSize(float Min, float Max) const
{
	float VecSize = Size();
	const FVector VecDir = (VecSize > SMALL_NUMBER) ? (*this/VecSize) : FVector::ZeroVector;

	VecSize = FMath::Clamp(VecSize, Min, Max);

	return VecSize * VecDir;
}

// Math/Vector2D.h
struct FVector2D
{
	float X;
	float Y;

	static const FVector2D ZeroVector;   // CORE_API

	__forceinline FVector2D() { }
	__forceinline FVector2D(float InX, float InY) : X(InX), Y(InY) { }

	__forceinline FVector2D operator+(const FVector2D& V) const { return FVector2D(X + V.X, Y + V.Y); }
	__forceinline FVector2D operator-(const FVector2D& V) const { return FVector2D(X - V.X, Y - V.Y); }
	__forceinline FVector2D operator*(float Scale) const { return FVector2D(X * Scale, Y * Scale); }
	__forceinline FVector2D operator/(float Scale) const
	{
		const float RScale = 1.f/Scale;
		return FVector2D(X * RScale, Y * RScale);
	}

	__forceinline float Size() const { return FMath::Sqrt(X*X + Y*Y); }
	__forceinline float SizeSquared() const { return X*X + Y*Y; }
};

// Not the public 4.20.0 form (GetRangePct(Range.X, Range.Y, Value), which tests IsNearlyZero of
// the divisor): the reference's UKismetMathLibrary::MapRangeClamped/Unclamped compare the range
// ends exactly and yield Range.X for an empty range, the pre-4.20 body
// (docs/ENGINE_DIFFERENCES.md).
__forceinline float FMath::GetRangePct(FVector2D const& Range, float Value)
{
	return (Range.X != Range.Y) ? (Value - Range.X) / (Range.Y - Range.X) : Range.X;
}

__forceinline float FMath::GetRangeValue(FVector2D const& Range, float Pct)
{
	return Lerp<float>(Range.X, Range.Y, Pct);
}

// Math/Color.h
struct FLinearColor
{
	float R, G, B, A;
	__forceinline FLinearColor() {}
	__forceinline FLinearColor(float InR,float InG,float InB,float InA = 1.0f): R(InR), G(InG), B(InB), A(InA) {}

	__forceinline FLinearColor operator+(const FLinearColor& ColorB) const
	{
		return FLinearColor(
			this->R + ColorB.R,
			this->G + ColorB.G,
			this->B + ColorB.B,
			this->A + ColorB.A
			);
	}
	__forceinline FLinearColor operator-(const FLinearColor& ColorB) const
	{
		return FLinearColor(
			this->R - ColorB.R,
			this->G - ColorB.G,
			this->B - ColorB.B,
			this->A - ColorB.A
			);
	}
	__forceinline FLinearColor operator*(float Scalar) const
	{
		return FLinearColor(
			this->R * Scalar,
			this->G * Scalar,
			this->B * Scalar,
			this->A * Scalar
			);
	}

	static inline float Dist( const FLinearColor &V1, const FLinearColor &V2 )
	{
		return FMath::Sqrt( FMath::Square(V2.R-V1.R) + FMath::Square(V2.G-V1.G) + FMath::Square(V2.B-V1.B) + FMath::Square(V2.A-V1.A) );
	}

	static const FLinearColor White;     // CORE_API
};

// Math/Plane.h
__declspec(align(16)) struct FPlane
	: public FVector
{
public:
	float W;

	__forceinline FPlane() { }
	__forceinline FPlane(FVector InNormal, float InW)
		:	FVector(InNormal), W(InW)
	{}
	__forceinline FPlane(FVector InBase, const FVector &InNormal)
		:	FVector(InNormal)
		,	W(InBase | InNormal)
	{}
};

#include "FortniteGameCode/AxisRecovered.h"   // Math/Axis.h

// Math/Matrix.h, Matrix.inl
__declspec(align(16)) struct FMatrix
{
public:
	union
	{
		__declspec(align(16)) float M[4][4];
	};

	// User-declared as in 4.20 (Matrix.inl defines it empty). It also keeps /GS from treating a
	// matrix local as a buffer: the reference's FRotationMatrix temporaries have no cookie.
	__forceinline FMatrix() { }

	__forceinline FMatrix(const FVector& InX,const FVector& InY,const FVector& InZ,const FVector& InW)
	{
		M[0][0] = InX.X; M[0][1] = InX.Y;  M[0][2] = InX.Z;  M[0][3] = 0.0f;
		M[1][0] = InY.X; M[1][1] = InY.Y;  M[1][2] = InY.Z;  M[1][3] = 0.0f;
		M[2][0] = InZ.X; M[2][1] = InZ.Y;  M[2][2] = InZ.Z;  M[2][3] = 0.0f;
		M[3][0] = InW.X; M[3][1] = InW.Y;  M[3][2] = InW.Z;  M[3][3] = 1.0f;
	}

	FRotator Rotator() const;   // CORE_API, Math/UnrealMath.cpp

	// Inline in Matrix.inl (not FORCEINLINE); the reference calls an out-of-line copy, defined in
	// UnrealMath.cpp.
	float Determinant() const;

	inline FVector GetScaledAxis( EAxis::Type InAxis ) const
	{
		switch ( InAxis )
		{
		case EAxis::X:
			return FVector(M[0][0], M[0][1], M[0][2]);

		case EAxis::Y:
			return FVector(M[1][0], M[1][1], M[1][2]);

		case EAxis::Z:
			return FVector(M[2][0], M[2][1], M[2][2]);

		default:
			// ensure(0) is compiled out in shipping
			return FVector::ZeroVector;
		}
	}

	inline void GetScaledAxes(FVector &X, FVector &Y, FVector &Z) const
	{
		X.X = M[0][0]; X.Y = M[0][1]; X.Z = M[0][2];
		Y.X = M[1][0]; Y.Y = M[1][1]; Y.Z = M[1][2];
		Z.X = M[2][0]; Z.Y = M[2][1]; Z.Z = M[2][2];
	}
};

// Math/RotationTranslationMatrix.h, RotationMatrix.h. FRotationMatrix's constructor is inline
// there, but the reference calls an out-of-line copy (0x009C4CB0), so it is only declared.
class FRotationTranslationMatrix
	: public FMatrix
{
public:
	FRotationTranslationMatrix(const FRotator& Rot, const FVector& Origin);
};

class FRotationMatrix
	: public FRotationTranslationMatrix
{
public:
	FRotationMatrix(const FRotator& Rot);

	// CORE_API, Math/UnrealMath.cpp
	static FMatrix MakeFromX(FVector const& XAxis);
	static FMatrix MakeFromY(FVector const& YAxis);
	static FMatrix MakeFromZ(FVector const& ZAxis);
	static FMatrix MakeFromXY(FVector const& XAxis, FVector const& YAxis);
	static FMatrix MakeFromXZ(FVector const& XAxis, FVector const& ZAxis);
	static FMatrix MakeFromYX(FVector const& YAxis, FVector const& XAxis);
	static FMatrix MakeFromYZ(FVector const& YAxis, FVector const& ZAxis);
	static FMatrix MakeFromZX(FVector const& ZAxis, FVector const& XAxis);
	static FMatrix MakeFromZY(FVector const& ZAxis, FVector const& YAxis);
};

// Math/Quat.h. The members that use VectorRegister code and the unit's GlobalVectorConstants
// (operator*, Normalize, GetNormalized, Slerp) are defined in QuatRecovered.h, which a unit
// includes after defining its constants.
__declspec(align(16)) struct FQuat
{
public:
	float X;
	float Y;
	float Z;
	float W;

	__forceinline FQuat() { }
	__forceinline FQuat( float InX, float InY, float InZ, float InW )
		: X(InX)
		, Y(InY)
		, Z(InZ)
		, W(InW)
	{ }
	__forceinline FQuat(const FQuat& Q)   // user-provided in 4.20: copies member by member
		: X(Q.X)
		, Y(Q.Y)
		, Z(Q.Z)
		, W(Q.W)
	{ }
	explicit __forceinline FQuat(const FRotator& R)
	{
		*this = R.Quaternion();
	}
	__forceinline FQuat( FVector Axis, float AngleRad )
	{
		const float half_a = 0.5f * AngleRad;
		float s, c;
		FMath::SinCos(&s, &c, half_a);

		X = s * Axis.X;
		Y = s * Axis.Y;
		Z = s * Axis.Z;
		W = c;
	}

	FQuat operator*( const FQuat& Q ) const;

	__forceinline FQuat operator+(const FQuat& Q) const
	{
		return FQuat(X + Q.X, Y + Q.Y, Z + Q.Z, W + Q.W);
	}
	__forceinline FQuat operator*(const float Scale) const
	{
		return FQuat(Scale * X, Scale * Y, Scale * Z, Scale * W);
	}
	__forceinline float operator|(const FQuat& Q) const
	{
		return X * Q.X + Y * Q.Y + Z * Q.Z + W * Q.W;
	}

	void Normalize(float Tolerance = SMALL_NUMBER);
	FQuat GetNormalized(float Tolerance = SMALL_NUMBER) const;

	__forceinline FQuat Inverse() const
	{
		return FQuat(-X, -Y, -Z, W);
	}

	FRotator Rotator() const;   // CORE_API, Math/UnrealMath.cpp

	static FQuat Slerp_NotNormalized(const FQuat &Quat1, const FQuat &Quat2, float Slerp);   // CORE_API
	static FQuat Slerp(const FQuat &Quat1, const FQuat &Quat2, float Slerp);
	static FQuat SlerpFullPath_NotNormalized(const FQuat &quat1, const FQuat &quat2, float Alpha);   // CORE_API
	static FQuat SlerpFullPath(const FQuat &quat1, const FQuat &quat2, float Alpha);
	static FQuat Squad(const FQuat& quat1, const FQuat& tang1, const FQuat& quat2, const FQuat& tang2, float Alpha);   // CORE_API
	static FQuat FindBetweenNormals(const FVector& Normal1, const FVector& Normal2);   // CORE_API
	static FQuat FindBetweenVectors(const FVector& Vector1, const FVector& Vector2);   // CORE_API
};

// Math/Box.h
struct FBox
{
	FVector Min;
	FVector Max;
	uint8 IsValid;

	__forceinline FBox() { }
	__forceinline FBox( const FVector& InMin, const FVector& InMax )
		: Min(InMin)
		, Max(InMax)
		, IsValid(1)
	{ }

	__forceinline bool IsInsideOrOn( const FVector& In ) const
	{
		return ((In.X >= Min.X) && (In.X <= Max.X) && (In.Y >= Min.Y) && (In.Y <= Max.Y) && (In.Z >= Min.Z) && (In.Z <= Max.Z));
	}
};

// Math/RandomStream.h
struct FRandomStream
{
	__forceinline FRandomStream() : InitialSeed(0), Seed(0) { }
	__forceinline FRandomStream( int32 InSeed ) : InitialSeed(InSeed), Seed(InSeed) { }

	__forceinline void Initialize( int32 InSeed )
	{
		InitialSeed = InSeed;
		Seed = InSeed;
	}

	__forceinline void Reset() const
	{
		Seed = InitialSeed;
	}

	__forceinline int32 GetInitialSeed() const
	{
		return InitialSeed;
	}

	__forceinline void GenerateNewSeed()
	{
		Initialize(FMath::Rand());
	}

	__forceinline float GetFraction() const
	{
		MutateSeed();

		const float SRandTemp = 1.0f;
		float Result;

		*(int32*)&Result = (*(int32*)&SRandTemp & 0xff800000) | (Seed & 0x007fffff);

		return FMath::Fractional(Result);
	}

	__forceinline float FRand() const
	{
		return GetFraction();
	}

	__forceinline int32 RandHelper( int32 A ) const
	{
		// GetFraction guarantees a result in the [0,1) range.
		return ((A > 0) ? FMath::TruncToInt(GetFraction() * ((float)A - DELTA)) : 0);
	}

	__forceinline int32 RandRange( int32 Min, int32 Max ) const
	{
		const int32 Range = (Max - Min) + 1;

		return Min + RandHelper(Range);
	}

	__forceinline float FRandRange( float InMin, float InMax ) const
	{
		return InMin + (InMax - InMin) * FRand();
	}

protected:
	__forceinline void MutateSeed() const
	{
		Seed = (Seed * 196314165) + 907633515;
	}

private:
	int32 InitialSeed;
	mutable int32 Seed;
};

// Misc/Timespan.h
namespace ETimespan
{
	const int64 MaxTicks = 9223372036854775807;
	const int64 MinTicks = -9223372036854775807 - 1;
	const int64 NanosecondsPerTick = 100;
	const int64 TicksPerDay = 864000000000;
	const int64 TicksPerHour = 36000000000;
	const int64 TicksPerMicrosecond = 10;
	const int64 TicksPerMillisecond = 10000;
	const int64 TicksPerMinute = 600000000;
	const int64 TicksPerSecond = 10000000;
	const int64 TicksPerWeek = 6048000000000;
}

struct FTimespan
{
	__forceinline FTimespan() : Ticks(0) { }
	__forceinline FTimespan(int32 Days, int32 Hours, int32 Minutes, int32 Seconds, int32 FractionNano)
	{
		Assign(Days, Hours, Minutes, Seconds, FractionNano);
	}

	__forceinline int32 GetDays() const { return (int32)(Ticks / ETimespan::TicksPerDay); }
	__forceinline int32 GetFractionMilli() const { return (int32)((Ticks % ETimespan::TicksPerSecond) / ETimespan::TicksPerMillisecond); }
	__forceinline int32 GetFractionNano() const { return (int32)((Ticks % ETimespan::TicksPerSecond) * ETimespan::NanosecondsPerTick); }
	__forceinline int32 GetHours() const { return (int32)((Ticks / ETimespan::TicksPerHour) % 24); }
	__forceinline int32 GetMinutes() const { return (int32)((Ticks / ETimespan::TicksPerMinute) % 60); }
	__forceinline int32 GetSeconds() const { return (int32)((Ticks / ETimespan::TicksPerSecond) % 60); }

protected:
	void Assign(int32 Days, int32 Hours, int32 Minutes, int32 Seconds, int32 FractionNano);   // CORE_API, Misc/Timespan.cpp

private:
	int64 Ticks;
};
