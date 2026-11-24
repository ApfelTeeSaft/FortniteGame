// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: Core. Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/Core/Private/GenericPlatform/GenericPlatformMath.cpp.
// Reconstruction written from image evidence; see analysis/functions.json.

#include "FortniteGameCode/MathDecls.h"

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01112E50 (end 0x01112F38)
// Original VA: 0x0000000141112E50 | File offset: 0x01112450
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called twice by FVector::ToOrientationRotator (0x011A6B30); the minimax polynomial
//   with the 4.20 coefficients. The compiler folds the static array into scalar constants, so the
//   negative coefficients become subtractions of positive ones, as in the reference.
float FGenericPlatformMath::Atan2(float Y, float X)
{
	//return atan2f(Y,X);
	// atan2f occasionally returns NaN with perfectly valid input (possibly due to a compiler or library bug).
	// We are replacing it with a minimax approximation with a max relative error of 7.15255737e-007 compared to the C library function.

	const float absX = FMath::Abs(X);
	const float absY = FMath::Abs(Y);
	const bool yAbsBigger = (absY > absX);
	float t0 = yAbsBigger ? absY : absX; // Max(absY, absX)
	float t1 = yAbsBigger ? absX : absY; // Min(absX, absY)

	if (t0 == 0.f)
		return 0.f;

	float t3 = t1 / t0;
	float t4 = t3 * t3;

	static const float c[7] = {
		+7.2128853633444123e-03f,
		-3.5059680836411644e-02f,
		+8.1675882859940430e-02f,
		-1.3374657325451267e-01f,
		+1.9856563505717162e-01f,
		-3.3324998579202170e-01f,
		+1.0f
	};

	t0 = c[0];
	t0 = t0 * t4 + c[1];
	t0 = t0 * t4 + c[2];
	t0 = t0 * t4 + c[3];
	t0 = t0 * t4 + c[4];
	t0 = t0 * t4 + c[5];
	t0 = t0 * t4 + c[6];
	t3 = t0 * t3;

	t3 = yAbsBigger ? (0.5f * PI) - t3 : t3;
	t3 = (X < 0.0f) ? PI - t3 : t3;
	t3 = (Y < 0.0f) ? -t3 : t3;

	return t3;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0126F320 (end 0x0126F323), no .pdata (leaf)
// Original VA: 0x000000014126F320
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: the call FMath::Fmod's zero-divisor branch makes (UKismetMathLibrary::GenericPercent_FloatFloat,
//   ClampAxis, NormalizeAxis, FMod). In shipping ensureMsgf is compiled out and the body is empty:
//   `ret 0`, which /OPT:ICF folds with every other empty function at this address.
void FGenericPlatformMath::FmodReportError(float X, float Y)
{
	// if (Y == 0) { ensureMsgf(Y != 0, TEXT("FMath::FMod(X=%f, Y=%f) : Y is zero, this is invalid and would result in NaN!"), X, Y); }
}
