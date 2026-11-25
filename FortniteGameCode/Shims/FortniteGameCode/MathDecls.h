// ABI declarations of Core math types and functions recovered code uses: Math/Vector.h,
// Vector2D.h, Rotator.h, Box.h, Color.h, RandomStream.h, UnrealMathUtility.h,
// GenericPlatform/GenericPlatformMath.h, Windows/WindowsPlatformMath.h, UnrealPlatformMathSSE.h,
// Misc/Timespan.h. Not recovered code. Only the members recovered code defines or calls are
// declared; the inline helpers are the 4.20 forms the reference's code shows (fabsf/sqrtf become
// andps/sqrtss under /fp:fast). Shared by Core's recovered math and, through ScriptRecovered.h,
// by the UHT world, so both see one definition of each type.
#pragma once

// FNGC_CORE_MATH_EXTRAS: the declarations the Core units and KismetMathLibrary.cpp use for dates,
// colours and the rotator helpers (FDateTime, FColor's constructors, FVector4, ...). Only those
// units define it. The generated UHT units do not see them: adding declarations to the headers
// they include changes the order in which MSVC v140 emits their functions and literals (for
// example InputCore.1's FKey literals), as including <intrin.h> did (TextRecovered.h).
#ifndef FNGC_CORE_MATH_EXTRAS
#define FNGC_CORE_MATH_EXTRAS 0
#endif

#include <math.h>
#include <stdlib.h>
#include <xmmintrin.h>   // as UnrealPlatformMathSSE.h

// Windows/WindowsPlatformCompilerSetup.h disables this for all UE4 code (FMath::MakePulsatingValue
// narrows its double expression).
#pragma warning(disable : 4244) // 'expression' : conversion from 'type' to 'type', possible loss of data
// Windows/WindowsPlatform.h: disabled for all UE4 code (FmodReportError's body is compiled out).
#pragma warning(disable : 4100) // unreferenced formal parameter
#if FNGC_CORE_MATH_EXTRAS
// Windows/WindowsPlatformCompilerSetup.h: TArray's destructor keeps an unused DebugGet pointer, and
// DefaultCalculateSlackReserve narrows QuantizeSize's SIZE_T to int32 (the Core units that use
// containers include MathDecls.h first).
#pragma warning(disable : 4189 4267)
#endif

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
#if FNGC_CORE_MATH_EXTRAS
struct FColor;
struct FVector4;
struct FPlane;
struct FBox;
class FDefaultAllocator;
#endif
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
#if FNGC_CORE_MATH_EXTRAS
	static __forceinline double FloorToDouble( double F ) { return floor(F); }
	static __forceinline double CeilToDouble( double F ) { return ceil(F); }
	static __forceinline double RoundToZero(double F)
	{
		return (F < 0.0) ? CeilToDouble(F) : FloorToDouble(F);
	}
	template< class T >
	static constexpr __forceinline T Sign( const T A )
	{
		return (A > (T)0) ? (T)1 : ((A < (T)0) ? (T)-1 : (T)0);
	}
#endif

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
#if FNGC_CORE_MATH_EXTRAS
	}
	static __forceinline int32 CeilToInt(float F)
	{
		// Note: unlike the Generic solution and the float solution, we implicitly use banker's rounding here.
		return -(_mm_cvt_ss2si(_mm_set_ss(-0.5f - (F + F))) >> 1);
	}
	static __forceinline float CeilToFloat(float F)
	{
		return (float)CeilToInt(F);
#endif
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
#if FNGC_CORE_MATH_EXTRAS
	static FVector GetReflectionVector(const FVector& Direction, const FVector& SurfaceNormal);
	static float ClampAngle(float AngleDegrees, float MinAngleDegrees, float MaxAngleDegrees);
	static float FixedTurn(float InCurrent, float InDesired, float InDeltaRate);
	static void SegmentDistToSegment(FVector A1, FVector B1, FVector A2, FVector B2, FVector& OutP1, FVector& OutP2);
	static void SegmentDistToSegmentSafe(FVector A1, FVector B1, FVector A2, FVector B2, FVector& OutP1, FVector& OutP2);
	static bool PointsAreCoplanar(const TArray<FVector, FDefaultAllocator>& Points, const float Tolerance = 0.1f);
	static FVector ClosestPointOnLine(const FVector& LineStart, const FVector& LineEnd, const FVector& Point);
	static FVector ClosestPointOnInfiniteLine(const FVector& LineStart, const FVector& LineEnd, const FVector& Point);
	static FVector2D ClosestPointOnSegment2D(const FVector2D &Point, const FVector2D &StartPoint, const FVector2D &EndPoint);
	static float PointDistToSegmentSquared(const FVector &Point, const FVector &StartPoint, const FVector &EndPoint);
	static float GetTForSegmentPlaneIntersect(const FVector& StartPoint, const FVector& EndPoint, const FPlane& Plane);
	static bool SegmentPlaneIntersection(const FVector& StartPoint, const FVector& EndPoint, const FPlane& Plane, FVector& out_IntersectionPoint);
	static FVector GetBaryCentric2D(const FVector& Point, const FVector& A, const FVector& B, const FVector& C);
	static FVector ComputeBaryCentric2D(const FVector& Point, const FVector& A, const FVector& B, const FVector& C);
	static void SphereDistToLine(FVector SphereOrigin, float SphereRadius, FVector LineOrigin, FVector LineDir, FVector& OutClosestPoint);
	static FVector2D RandPointInCircle(float CircleRadius);
	static FVector RandPointInBox(const FBox& Box);
	static void WindRelativeAnglesDegrees(float InAngle0, float& InOutAngle1);
	static void ApplyScaleToFloat(float& Dst, const FVector& DeltaScale, float Magnitude = 1.0f);
	static void CartesianToPolar(const FVector2D InCart, FVector2D& OutPolar);
	static void PolarToCartesian(const FVector2D InPolar, FVector2D& OutCart);
#if FNGC_CORE_MATH_EXTRAS
	static bool PlaneAABBIntersection(const FPlane& P, const FBox& AABB);
	static bool SphereConeIntersection(const FVector& SphereCenter, float SphereRadius, const FVector& ConeAxis, float ConeAngleSin, float ConeAngleCos);
	static FQuat QInterpConstantTo(const FQuat& Current, const FQuat& Target, float DeltaTime, float InterpSpeed);
	static FQuat QInterpTo(const FQuat& Current, const FQuat& Target, float DeltaTime, float InterpSpeed);
#endif

	template< class T >
	static __forceinline T Max3( const T A, const T B, const T C )
	{
		return Max ( Max( A, B ), C );
	}
	template< class T >
	static __forceinline T Min3( const T A, const T B, const T C )
	{
		return Min ( Min( A, B ), C );
	}
#endif
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
#if FNGC_CORE_MATH_EXTRAS
	FVector RotateVector( const FVector& V ) const;   // CORE_API
	FVector UnrotateVector( const FVector& V ) const;   // CORE_API
	FVector Euler() const;   // CORE_API
	static FRotator MakeFromEuler( const FVector& Euler );   // CORE_API
	void GetWindingAndRemainder( FRotator& Winding, FRotator& Remainder ) const;   // CORE_API
#endif

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

#if FNGC_CORE_MATH_EXTRAS
	__forceinline FVector(const FVector4& V);   // Math/Vector4.h

	__forceinline FVector operator-=(const FVector& V)
	{
		X -= V.X; Y -= V.Y; Z -= V.Z;
		return *this;
	}
	__forceinline FVector operator*(const FVector& V) const { return FVector(X * V.X, Y * V.Y, Z * V.Z); }

	__forceinline bool IsZero() const
	{
		return X==0.f && Y==0.f && Z==0.f;
	}

	__forceinline bool IsNearlyZero(float Tolerance=KINDA_SMALL_NUMBER) const
	{
		return
			FMath::Abs(X)<=Tolerance
			&&	FMath::Abs(Y)<=Tolerance
			&&	FMath::Abs(Z)<=Tolerance;
	}

	__forceinline FVector operator/=(float V)
	{
		const float RV = 1.f/V;
		X *= RV; Y *= RV; Z *= RV;
		return *this;
	}

	__forceinline FVector GetUnsafeNormal() const
	{
		const float Scale = FMath::InvSqrt(X*X+Y*Y+Z*Z);
		return FVector(X*Scale, Y*Scale, Z*Scale);
	}

	static __forceinline FVector CrossProduct(const FVector& A, const FVector& B)
	{
		return A ^ B;
	}

	static __forceinline float DotProduct(const FVector& A, const FVector& B)
	{
		return A | B;
	}

	static __forceinline float PointPlaneDist(const FVector &Point, const FVector &PlaneBase, const FVector &PlaneNormal)
	{
		return (Point - PlaneBase) | PlaneNormal;
	}

	// CORE_API, Math/UnrealMath.cpp
	void FindBestAxisVectors( FVector& Axis1, FVector& Axis2 ) const;
	static void CreateOrthonormalBasis(FVector& XAxis,FVector& YAxis,FVector& ZAxis);
	FQuat ToOrientationQuat() const;

#endif
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
#if FNGC_CORE_MATH_EXTRAS
	__forceinline float operator|(const FVector2D& V) const { return X*V.X + Y*V.Y; }
#endif
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

#if FNGC_CORE_MATH_EXTRAS
// Math/Color.h (PLATFORM_LITTLE_ENDIAN, _MSC_VER). EngineStructsRecovered.h has the plain form the
// UHT units use.
struct FColor
{
public:
#pragma warning(push)
#pragma warning(disable : 4201) // nameless struct/union (UE4.20 disables it)
	union { struct{ uint8 B,G,R,A; }; uint32 AlignmentDummy; };
#pragma warning(pop)

	uint32& DWColor(void) {return *((uint32*)this);}
	const uint32& DWColor(void) const {return *((uint32*)this);}

	__forceinline FColor() {}
	__forceinline explicit FColor(EForceInit)
	{
		// put these into the body for proper ordering with INTEL vs non-INTEL_BYTE_ORDER
		R = G = B = A = 0;
	}
	__forceinline FColor( uint8 InR, uint8 InG, uint8 InB, uint8 InA = 255 )
	{
		// put these into the body for proper ordering with INTEL vs non-INTEL_BYTE_ORDER
		R = InR;
		G = InG;
		B = InB;
		A = InA;
	}

	// CORE_API, Math/Color.cpp
	FLinearColor FromRGBE() const;
	static FColor MakeRandomColor();
	static FColor MakeFromColorTemperature( float Temp );
	static FColor MakeRedToGreenColorFromScalar(float Scalar);
};

// Math/Vector4.h
__declspec(align(16)) struct FVector4
{
public:
	float X;
	float Y;
	float Z;
	float W;

	__forceinline FVector4(const FVector& InVector, float InW = 1.0f);
	// CORE_API, Math/UnrealMath.cpp
	FRotator ToOrientationRotator() const;
	FRotator Rotation() const;
	FQuat ToOrientationQuat() const;

	explicit __forceinline FVector4(float InX = 0.0f, float InY = 0.0f, float InZ = 0.0f, float InW = 0.0f)
		: X(InX)
		, Y(InY)
		, Z(InZ)
		, W(InW)
	{
	}
};

#endif
// Math/Color.h
struct FLinearColor
{
	float R, G, B, A;
#if FNGC_CORE_MATH_EXTRAS

	// Pow table for fast FColor -> FLinearColor conversion. CORE_API data, Math/Color.cpp.
	static float Pow22OneOver255Table[256];
	static float sRGBToLinearTable[256];

#endif
	__forceinline FLinearColor() {}
	__forceinline FLinearColor(float InR,float InG,float InB,float InA = 1.0f): R(InR), G(InG), B(InB), A(InA) {}
#if FNGC_CORE_MATH_EXTRAS

	// CORE_API, Math/Color.cpp
	FLinearColor(const FColor& Color);
	FLinearColor(const FVector& Vector);
	explicit FLinearColor(const FVector4& Vector);
	FColor ToRGBE() const;
	static FLinearColor FromSRGBColor(const FColor& Color);
	static FLinearColor FromPow22Color(const FColor& Color);
	static FLinearColor FGetHSV(uint8 H,uint8 S,uint8 V);
	static FLinearColor MakeRandomColor();
	static FLinearColor MakeFromColorTemperature( float Temp );
	FLinearColor LinearRGBToHSV() const;
	FLinearColor HSVToLinearRGB() const;
	static FLinearColor LerpUsingHSV( const FLinearColor& From, const FLinearColor& To, const float Progress );
	FColor Quantize() const;
	FColor QuantizeRound() const;
	FColor ToFColor(const bool bSRGB) const;
	FLinearColor Desaturate( float Desaturation ) const;

	__forceinline float ComputeLuminance() const
	{
		return R * 0.3f + G * 0.59f + B * 0.11f;
	}

	static const FLinearColor Black;   // CORE_API

	__forceinline FLinearColor operator/(float Scalar) const
	{
		const float	InvScalar = 1.0f / Scalar;
		return FLinearColor(
			this->R * InvScalar,
			this->G * InvScalar,
			this->B * InvScalar,
			this->A * InvScalar
			);
	}
#endif

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
#if FNGC_CORE_MATH_EXTRAS

__forceinline FVector4::FVector4(const FVector& InVector,float InW)
	: X(InVector.X)
	, Y(InVector.Y)
	, Z(InVector.Z)
	, W(InW)
{
}

__forceinline FVector::FVector( const FVector4& V )
	: X(V.X), Y(V.Y), Z(V.Z)
{
}

__forceinline FLinearColor operator*(float Scalar,const FLinearColor& Color)
{
	return Color.operator*( Scalar );
}
#endif

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
#if FNGC_CORE_MATH_EXTRAS
	__forceinline FPlane(float InX, float InY, float InZ, float InW)
		:	FVector(InX,InY,InZ)
		,	W(InW)
	{}

	__forceinline float PlaneDot(const FVector &P) const
	{
		return X*P.X + Y*P.Y + Z*P.Z - W;
	}
#endif
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
#if FNGC_CORE_MATH_EXTRAS

	// Matrix.inl; the VectorRegister forms are in QuatRecovered.h.
	FVector4 TransformFVector4(const FVector4& V) const;
	FVector4 TransformVector(const FVector& V) const;
	FVector InverseTransformVector(const FVector &V) const;
	FMatrix operator*(const FMatrix& Other) const;
	FMatrix Inverse() const;
	FMatrix InverseFast() const;
	FQuat ToQuat() const;   // CORE_API, Math/UnrealMath.cpp
	void RemoveScaling(float Tolerance=SMALL_NUMBER);
	__forceinline FMatrix(const FPlane& InX,const FPlane& InY,const FPlane& InZ,const FPlane& InW);
	static const FMatrix Identity;   // CORE_API, Math/UnrealMath.cpp

	inline void SetAxis( int32 i, const FVector& Axis )
	{
		// checkSlow(i >= 0 && i <= 2) is compiled out.
		M[i][0] = Axis.X;
		M[i][1] = Axis.Y;
		M[i][2] = Axis.Z;
	}

	inline FVector GetOrigin() const
	{
		return FVector(M[3][0],M[3][1],M[3][2]);
	}
	inline FMatrix GetTransposed() const
	{
		FMatrix	Result;

		Result.M[0][0] = M[0][0];
		Result.M[0][1] = M[1][0];
		Result.M[0][2] = M[2][0];
		Result.M[0][3] = M[3][0];

		Result.M[1][0] = M[0][1];
		Result.M[1][1] = M[1][1];
		Result.M[1][2] = M[2][1];
		Result.M[1][3] = M[3][1];

		Result.M[2][0] = M[0][2];
		Result.M[2][1] = M[1][2];
		Result.M[2][2] = M[2][2];
		Result.M[2][3] = M[3][2];

		Result.M[3][0] = M[0][3];
		Result.M[3][1] = M[1][3];
		Result.M[3][2] = M[2][3];
		Result.M[3][3] = M[3][3];

		return Result;
	}
#endif

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

#if FNGC_CORE_MATH_EXTRAS
__forceinline FMatrix::FMatrix(const FPlane& InX,const FPlane& InY,const FPlane& InZ,const FPlane& InW)
{
	M[0][0] = InX.X; M[0][1] = InX.Y;  M[0][2] = InX.Z;  M[0][3] = InX.W;
	M[1][0] = InY.X; M[1][1] = InY.Y;  M[1][2] = InY.Z;  M[1][3] = InY.W;
	M[2][0] = InZ.X; M[2][1] = InZ.Y;  M[2][2] = InZ.Z;  M[2][3] = InZ.W;
	M[3][0] = InW.X; M[3][1] = InW.Y;  M[3][2] = InW.Z;  M[3][3] = InW.W;
}
#endif

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
#if FNGC_CORE_MATH_EXTRAS
	FVector Euler() const;   // CORE_API, Math/UnrealMath.cpp
	explicit FQuat(const FMatrix& M);   // inline in Math/Quat.h, QuatRecovered.h
	static const FQuat Identity;   // CORE_API, Math/UnrealMath.cpp
	FQuat Log() const;   // CORE_API, Math/UnrealMath.cpp
	FQuat Exp() const;
	void ToSwingTwist(const FVector& InTwistAxis, FQuat& OutSwing, FQuat& OutTwist) const;
	static FQuat SquadFullPath(const FQuat& quat1, const FQuat& tang1, const FQuat& quat2, const FQuat& tang2, float Alpha);
	static void CalcTangents(const FQuat& PrevP, const FQuat& P, const FQuat& NextP, float Tension, FQuat& OutTan);
	bool Equals(const FQuat& Q, float Tolerance=KINDA_SMALL_NUMBER) const;   // QuatRecovered.h
	__forceinline float SizeSquared() const
	{
		return (X * X + Y * Y + Z * Z + W * W);
	}
	__forceinline float AngularDistance(const FQuat& Q) const;
	static FQuat MakeFromEuler(const FVector& Euler);   // CORE_API, Math/UnrealMath.cpp
#endif
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

#if FNGC_CORE_MATH_EXTRAS
	// Inline in Math/RandomStream.h; the reference keeps an out-of-line copy (0x01C85C00), which
	// UKismetMathLibrary::RandomUnitVectorFromStream calls. KismetMathLibrary.cpp emits it.
	FVector GetUnitVector() const
	{
		FVector Result;
		float L;

		do
		{
			// Check random vectors in the unit sphere so result is statistically uniform.
			Result.X = GetFraction() * 2.f - 1.f;
			Result.Y = GetFraction() * 2.f - 1.f;
			Result.Z = GetFraction() * 2.f - 1.f;
			L = Result.SizeSquared();
		}
		while(L > 1.f || L < KINDA_SMALL_NUMBER);

		return Result.GetUnsafeNormal();
	}

	__forceinline FVector VRand() const
	{
		return GetUnitVector();
	}

#endif
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

class FString;   // FTimespan::Parse

struct FTimespan
{
	__forceinline FTimespan() : Ticks(0) { }
#if FNGC_CORE_MATH_EXTRAS
	__forceinline FTimespan(int64 InTicks) : Ticks(InTicks) { }   // check() is compiled out
	__forceinline int64 GetTicks() const { return Ticks; }
	// Not the public 4.20.0 form (RoundToZero(Minutes * TicksPerMinute + 0.5)): the reference's
	// FDateTime::ParseIso8601 truncates the product (docs/ENGINE_DIFFERENCES.md).
	static FTimespan FromMinutes(double Minutes)
	{
		return FTimespan(Minutes * ETimespan::TicksPerMinute);
	}
	// The same older form: UKismetMathLibrary's From* natives truncate the product too.
	static FTimespan FromDays(double Days)
	{
		return FTimespan(Days * ETimespan::TicksPerDay);
	}
	static FTimespan FromHours(double Hours)
	{
		return FTimespan(Hours * ETimespan::TicksPerHour);
	}
	static FTimespan FromMilliseconds(double Milliseconds)
	{
		return FTimespan(Milliseconds * ETimespan::TicksPerMillisecond);
	}
	static FTimespan FromSeconds(double Seconds)
	{
		return FTimespan(Seconds * ETimespan::TicksPerSecond);
	}
	static FTimespan MaxValue()
	{
		return FTimespan(ETimespan::MaxTicks);
	}
	static FTimespan MinValue()
	{
		return FTimespan(ETimespan::MinTicks);
	}
	double GetTotalDays() const
	{
		return ((double)Ticks / ETimespan::TicksPerDay);
	}
	double GetTotalHours() const
	{
		return ((double)Ticks / ETimespan::TicksPerHour);
	}
	double GetTotalMilliseconds() const
	{
		return ((double)Ticks / ETimespan::TicksPerMillisecond);
	}
	double GetTotalMinutes() const
	{
		return ((double)Ticks / ETimespan::TicksPerMinute);
	}
	double GetTotalSeconds() const
	{
		return ((double)Ticks / ETimespan::TicksPerSecond);
	}

	static bool Parse(const FString& TimespanString, FTimespan& OutTimespan);   // CORE_API, Misc/Timespan.cpp
#endif
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

#if FNGC_CORE_MATH_EXTRAS
// Misc/DateTime.h
enum class EDayOfWeek
{
	Monday = 0,
	Tuesday,
	Wednesday,
	Thursday,
	Friday,
	Saturday,
	Sunday
};

class FString;

struct FDateTime
{
protected:
	static const int32 DaysPerMonth[];   // Misc/DateTime.cpp
	static const int32 DaysToMonth[];

public:
	FDateTime() : Ticks(0) { }
	FDateTime(int64 InTicks) : Ticks(InTicks) { }
	FDateTime(int32 Year, int32 Month, int32 Day, int32 Hour = 0, int32 Minute = 0, int32 Second = 0, int32 Millisecond = 0);

	FDateTime& operator-=(const FTimespan& Other)
	{
		Ticks -= Other.GetTicks();
		return *this;
	}

	void GetDate(int32& OutYear, int32& OutMonth, int32& OutDay) const;
	int32 GetDay() const;
	EDayOfWeek GetDayOfWeek() const;
	int32 GetDayOfYear() const;
	int32 GetHour() const
	{
		return (int32)((Ticks / ETimespan::TicksPerHour) % 24);
	}
	int32 GetHour12() const;
	double GetJulianDay() const
	{
		return (double)(1721425.5 + Ticks / ETimespan::TicksPerDay);
	}
	int32 GetMillisecond() const
	{
		return (int32)((Ticks / ETimespan::TicksPerMillisecond) % 1000);
	}
	int32 GetMinute() const
	{
		return (int32)((Ticks / ETimespan::TicksPerMinute) % 60);
	}
	int32 GetMonth() const;
	int32 GetSecond() const
	{
		return (int32)((Ticks / ETimespan::TicksPerSecond) % 60);
	}
	int64 GetTicks() const
	{
		return Ticks;
	}
	int32 GetYear() const;
	bool IsMorning() const
	{
		return (GetHour() < 12);
	}

	FString ToIso8601() const;
	FString ToString() const;
	FString ToString( const wchar_t* Format ) const;

	static int32 DaysInMonth(int32 Year, int32 Month);
	static int32 DaysInYear(int32 Year);
	static bool IsLeapYear( int32 Year );
	static FDateTime Now();
	static bool Parse(const FString& DateTimeString, FDateTime& OutDateTime);
	static bool ParseIso8601(const wchar_t* DateTimeString, FDateTime& OutDateTime);
	static FDateTime UtcNow();
	static bool Validate(int32 Year, int32 Month, int32 Day, int32 Hour, int32 Minute, int32 Second, int32 Millisecond);

private:
	int64 Ticks;
};

// Windows/WindowsPlatformTime.h (CORE_API, Windows/WindowsPlatformTime.cpp)
struct FWindowsPlatformTime
{
	static void SystemTime( int32& Year, int32& Month, int32& DayOfWeek, int32& Day, int32& Hour, int32& Min, int32& Sec, int32& MSec );
	static void UtcTime( int32& Year, int32& Month, int32& DayOfWeek, int32& Day, int32& Hour, int32& Min, int32& Sec, int32& MSec );
};
typedef FWindowsPlatformTime FPlatformTime;

#endif