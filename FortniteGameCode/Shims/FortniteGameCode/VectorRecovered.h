// SSE vector helpers from the UE4.20 headers: Core's Math/UnrealMathSSE.h
// (PLATFORM_ENABLE_VECTORINTRINSICS) and the constants of Math/UnrealMathUtility.h that
// UnrealMathVectorConstants.h uses. Not recovered code.
//
// The GlobalVectorConstants themselves are defined per unity unit by tools/codegen/unity.py:
// each unit defines the ones whose initializers open its .CRT$XCU entries in the reference
// (analysis/unity-order.json), after its StaticEnum functions.
#pragma once

#include "FortniteGameCode/UE4CodeGenRecovered.h"

#include <emmintrin.h>   // as UnrealMathSSE.h

// Math/UnrealMathUtility.h
#define PI 					(3.1415926535897932f)
#define SMALL_NUMBER		(1.e-8f)
#define KINDA_SMALL_NUMBER	(1.e-4f)
#define BIG_NUMBER			(3.4e+38f)
#define DELTA			(0.00001f)
#define THRESH_QUAT_NORMALIZED			(0.01f)
// Math/VectorRegister.h
#define ZERO_ANIMWEIGHT_THRESH (0.00001f)

// Math/UnrealMathSSE.h
typedef __m128	VectorRegister;
typedef __m128i VectorRegisterInt;

#define SHUFFLEMASK(A0,A1,B2,B3) ( (A0) | ((A1)<<2) | ((B2)<<4) | ((B3)<<6) )

__forceinline VectorRegister MakeVectorRegister( uint32 X, uint32 Y, uint32 Z, uint32 W )
{
 	union { VectorRegister v; VectorRegisterInt i; } Tmp;
	Tmp.i = _mm_setr_epi32( X, Y, Z, W );
 	return Tmp.v;
}

__forceinline VectorRegister MakeVectorRegister( float X, float Y, float Z, float W )
{
	return _mm_setr_ps( X, Y, Z, W );
}

__forceinline VectorRegisterInt MakeVectorRegisterInt(int32 X, int32 Y, int32 Z, int32 W)
{
	return _mm_setr_epi32(X, Y, Z, W);
}
