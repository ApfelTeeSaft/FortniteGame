// FTransform and the vector helpers its constructors use, from the UE4.20 headers: Core's
// Math/UnrealMathSSE.h (PLATFORM_ENABLE_VECTORINTRINSICS), UnrealMathVectorConstants.h and
// TransformVectorized.h. Not recovered code.
//
// UnityPrologue.h includes this, so the GlobalVectorConstants come after each unit's StaticEnum
// functions. In the reference, the StaticEnum singletons precede the unit's plain .bss, which
// these engine-header constants open (their initializers start the unit's .CRT$XCU entries).
#pragma once

#include "FortniteGameCode/UE4CodeGenRecovered.h"

#include <emmintrin.h>   // as UnrealMathSSE.h

// Core: Math/UnrealMathSSE.h (PLATFORM_ENABLE_VECTORINTRINSICS)
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

// Math/UnrealMathVectorConstants.h: per translation unit, dynamically initialised. Only the two
// FTransform's default constructor reads are defined. MSVC keeps every one a unit defines, and
// the reference's units hold only the ones they use, so defining the whole list would add ~50
// statics to every unit.
namespace GlobalVectorConstants
{
	static const VectorRegister FloatOne = MakeVectorRegister(1.0f, 1.0f, 1.0f, 1.0f);

	/** Bitmask to AND out the XYZ components in a vector */
	static const VectorRegister XYZMask = MakeVectorRegister((uint32)0xffffffff, (uint32)0xffffffff, (uint32)0xffffffff, (uint32)0x00000000);
}

#define VectorZero()					_mm_setzero_ps()
#define VectorOne()						(GlobalVectorConstants::FloatOne)
#define VectorSet_W0( Vec )		_mm_and_ps( Vec, GlobalVectorConstants::XYZMask )

__forceinline VectorRegister VectorSet_W1( const VectorRegister& Vector )
{
	// Temp = (Vector[2]. Vector[3], 1.0f, 1.0f)
	VectorRegister Temp = _mm_movehl_ps( VectorOne(), Vector );

	// Return (Vector[0], Vector[1], Vector[2], 1.0f)
	return _mm_shuffle_ps( Vector, Temp, SHUFFLEMASK(0,1,0,3) );
}

// Math/TransformVectorized.h. noexport: no StaticStruct. DiagnosticCheckNaN_All() is empty in
// shipping (ENABLE_NAN_DIAGNOSTIC 0).
__declspec(align(16)) struct FTransform
{
protected:
	VectorRegister	Rotation;
	VectorRegister	Translation;
	VectorRegister Scale3D;
public:
	__forceinline FTransform()
	{
		// Rotation = {0,0,0,1)
		Rotation = VectorSet_W1( VectorZero() );
		// Translation = {0,0,0,0)
		Translation = VectorZero();
		// Scale3D = {1,1,1,0);
		Scale3D = VectorSet_W0( VectorOne() );
	}

	__forceinline FTransform(const FTransform& InTransform) :
		Rotation(InTransform.Rotation),
		Translation(InTransform.Translation),
		Scale3D(InTransform.Scale3D)
	{
	}

	__forceinline FTransform& operator=(const FTransform& Other)
	{
		this->Rotation = Other.Rotation;
		this->Translation = Other.Translation;
		this->Scale3D = Other.Scale3D;

		return *this;
	}
};
