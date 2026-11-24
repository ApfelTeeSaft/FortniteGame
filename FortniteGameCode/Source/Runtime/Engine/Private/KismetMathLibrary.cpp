// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: Engine. Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/Engine/Private/KismetMathLibrary.cpp.
// Reconstruction written from image evidence; see analysis/functions.json.

// Kismet/KismetMathLibrary.h
namespace EEasingFunc
{
	enum Type
	{
		Linear,
		Step,
		SinusoidalIn,
		SinusoidalOut,
		SinusoidalInOut,
		EaseIn,
		EaseOut,
		EaseInOut,
		ExpoIn,
		ExpoOut,
		ExpoInOut,
		CircularIn,
		CircularOut,
		CircularInOut,
	};
}

// Hand-written natives of UKismetMathLibrary, declared in its generated class body
// (tools/codegen/uht_classes.py, EXTRA_MEMBERS).
#define FNGC_EXTRA_MEMBERS_UKismetMathLibrary \
	static FVector RandomUnitVector(); \
	static FVector GetForwardVector(FRotator InRot); \
	static bool RandomBoolWithWeight(float Weight); \
	static float GenericPercent_FloatFloat(float A, float B); \
	static float Log(float A, float Base = 1.f); \
	static int32 FMod(float Dividend, float Divisor, float& Remainder); \
	static float MakePulsatingValue(float InCurrentTime, float InPulsesPerSecond = 1.0f, float InPhase = 0.0f); \
	static void MaxOfIntArray(const TArray<int32>& IntArray, int32& IndexOfMaxValue, int32& MaxValue); \
	static void MinOfIntArray(const TArray<int32>& IntArray, int32& IndexOfMinValue, int32& MinValue); \
	static void MaxOfFloatArray(const TArray<float>& FloatArray, int32& IndexOfMaxValue, float& MaxValue); \
	static void MinOfFloatArray(const TArray<float>& FloatArray, int32& IndexOfMinValue, float& MinValue); \
	static void MaxOfByteArray(const TArray<uint8>& ByteArray, int32& IndexOfMaxValue, uint8& MaxValue); \
	static void MinOfByteArray(const TArray<uint8>& ByteArray, int32& IndexOfMinValue, uint8& MinValue); \
	static float Lerp(float A, float B, float Alpha); \
	static float Ease(float A, float B, float Alpha, TEnumAsByte<EEasingFunc::Type> EasingFunc, float BlendExp = 2, int32 Steps = 2); \
	static FVector VLerp(FVector A, FVector B, float Alpha); \
	static FVector VEase(FVector A, FVector B, float Alpha, TEnumAsByte<EEasingFunc::Type> EasingFunc, float BlendExp = 2, int32 Steps = 2); \
	static FRotator RandomRotator(bool bRoll = false); \
	static FVector FindClosestPointOnLine(FVector Point, FVector LineOrigin, FVector LineDirection); \
	static FVector ClampVectorSize(FVector A, float Min, float Max); \
	static FVector GetVectorArrayAverage(const TArray<FVector>& Vectors); \
	static float ClampAxis(float Angle); \
	static float NormalizeAxis(float Angle); \
	static FTimespan MakeTimespan(int32 Days, int32 Hours, int32 Minutes, int32 Seconds, int32 Milliseconds); \
	static FTimespan MakeTimespan2(int32 Days, int32 Hours, int32 Minutes, int32 Seconds, int32 FractionNano); \
	static void BreakTimespan(FTimespan InTimespan, int32& Days, int32& Hours, int32& Minutes, int32& Seconds, int32& Milliseconds); \
	static void BreakTimespan2(FTimespan InTimespan, int32& Days, int32& Hours, int32& Minutes, int32& Seconds, int32& FractionNano); \
	static FVector CreateVectorFromYawPitch(float Yaw, float Pitch, float Length = 1.0f ); \
	static void GetYawPitchFromVector(FVector InVec, float& Yaw, float& Pitch); \
	static void ResetRandomStream(const FRandomStream& Stream); \
	static void SeedRandomStream(FRandomStream& Stream); \
	static bool IsPointInBox(FVector Point, FVector BoxOrigin, FVector BoxExtent); \
	static FVector GetRightVector(FRotator InRot); \
	static FVector GetUpVector(FRotator InRot); \
	static void GetAxes(FRotator A, FVector& X, FVector& Y, FVector& Z); \
	static void BreakRotIntoAxes(const FRotator& InRot, FVector& X, FVector& Y, FVector& Z); \
	static FPlane MakePlaneFromPointAndNormal(FVector Point, FVector Normal); \
	static bool LinePlaneIntersection(const FVector& LineStart, const FVector& LineEnd, const FPlane& APlane, float& T, FVector& Intersection); \
	static bool LinePlaneIntersection_OriginNormal(const FVector& LineStart, const FVector& LineEnd, FVector PlaneOrigin, FVector PlaneNormal, float& T, FVector& Intersection); \
	static float Hypotenuse(float Width, float Height); \
	static bool InRange_FloatFloat(float Value, float Min, float Max, bool InclusiveMin = true, bool InclusiveMax = true); \
	static bool InRange_IntInt(int32 Value, int32 Min, int32 Max, bool InclusiveMin = true, bool InclusiveMax = true); \
	static float MapRangeUnclamped(float Value, float InRangeA, float InRangeB, float OutRangeA, float OutRangeB); \
	static float MapRangeClamped(float Value, float InRangeA, float InRangeB, float OutRangeA, float OutRangeB); \
	static float NormalizeToRange(float Value, float RangeMin, float RangeMax); \
	static FRandomStream MakeRandomStream(int32 InitialSeed); \
	static void BreakRandomStream(const FRandomStream& InRandomStream, int32& InitialSeed); \
	static void SetRandomStreamSeed(FRandomStream& Stream, int32 NewSeed); \
	static bool RandomBoolFromStream(const FRandomStream& Stream); \
	static float RandomFloatFromStream(const FRandomStream& Stream); \
	static float RandomFloatInRangeFromStream(float Min, float Max, const FRandomStream& Stream); \
	static bool RandomBoolWithWeightFromStream(float Weight, const FRandomStream& RandomStream); \
	static int32 RandomIntegerFromStream(int32 Max, const FRandomStream& Stream); \
	static int32 RandomIntegerInRangeFromStream(int32 Min, int32 Max, const FRandomStream& Stream); \
	static FRotator RandomRotatorFromStream(bool bRoll, const FRandomStream& Stream); \
	static FRotator ComposeRotators(FRotator A, FRotator B); \
	static FRotator TransformRotation(const FTransform& T, FRotator Rotation); \
	static FRotator InverseTransformRotation(const FTransform& T, FRotator Rotation); \
	static FRotator RLerp(FRotator A, FRotator B, float Alpha, bool bShortestPath); \
	static FRotator REase(FRotator A, FRotator B, float Alpha, bool bShortestPath, TEnumAsByte<EEasingFunc::Type> EasingFunc, float BlendExp = 2, int32 Steps = 2); \
	static FRotator RotatorFromAxisAndAngle(FVector Axis, float Angle); \
	static FRotator MakeRotationFromAxes(FVector Forward, FVector Right, FVector Up); \
	static FVector RotateAngleAxis(FVector InVect, float AngleDeg, FVector Axis); \
	static void ReportError_Divide_ByteByte(); \
	static void ReportError_Percent_ByteByte(); \
	static void ReportError_Divide_IntInt(); \
	static void ReportError_Percent_IntInt(); \
	static void ReportError_Sqrt(); \
	static void ReportError_Divide_VectorFloat(); \
	static void ReportError_Divide_VectorInt(); \
	static void ReportError_Divide_VectorVector(); \
	static void ReportError_ProjectVectorOnToVector(); \
	static void ReportError_Divide_Vector2DFloat(); \
	static void ReportError_Divide_Vector2DVector2D(); \
	static void ReportError_DaysInMonth();

#include "FortniteGameCode/UHTRecovered.h"

// The engine headers' GlobalVectorConstants (UnrealMathVectorConstants.h) of this unit: the 21
// whose leaf dynamic initializers store to its .bss in the reference (0x04897730-0x04897890,
// around the Blueprint warning ids; the initializers at 0x001D0730-0x001D0A30), in header order.
// QuatRecovered.h reads them.
#include "FortniteGameCode/VectorRecovered.h"
namespace GlobalVectorConstants
{
#define SIGN_BIT ((1 << 31))
	static const VectorRegister FloatOne = MakeVectorRegister(1.0f, 1.0f, 1.0f, 1.0f);
	static const VectorRegister FloatZero = MakeVectorRegister(0.0f, 0.0f, 0.0f, 0.0f);
	static const VectorRegister FloatMinusOne = MakeVectorRegister(-1.0f, -1.0f, -1.0f, -1.0f);
	static const VectorRegister Float0001 = MakeVectorRegister( 0.0f, 0.0f, 0.0f, 1.0f );
	static const VectorRegister SmallLengthThreshold = MakeVectorRegister(1.e-8f, 1.e-8f, 1.e-8f, 1.e-8f);
	static const VectorRegister FloatOneHalf = MakeVectorRegister( 0.5f, 0.5f, 0.5f, 0.5f );
	static const VectorRegister SmallNumber = MakeVectorRegister( SMALL_NUMBER, SMALL_NUMBER, SMALL_NUMBER, SMALL_NUMBER );
	static const VectorRegister QINV_SIGN_MASK = MakeVectorRegister( -1.f, -1.f, -1.f, 1.f );
	static const VectorRegister QMULTI_SIGN_MASK0 = MakeVectorRegister( 1.f, -1.f, 1.f, -1.f );
	static const VectorRegister QMULTI_SIGN_MASK1 = MakeVectorRegister( 1.f, 1.f, -1.f, -1.f );
	static const VectorRegister QMULTI_SIGN_MASK2 = MakeVectorRegister( -1.f, 1.f, 1.f, -1.f );
	static const VectorRegister DEG_TO_RAD = MakeVectorRegister(PI/(180.f), PI/(180.f), PI/(180.f), PI/(180.f));
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

// Kismet/KismetMathLibrary.inl (KISMET_MATH_FORCEINLINE: inline outside debug builds).
__forceinline float UKismetMathLibrary::Lerp(float A, float B, float V)
{
	return A + V*(B-A);
}

__forceinline FVector UKismetMathLibrary::VLerp(FVector A, FVector B, float V)
{
	return A + V*(B-A);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0207AC60 (end 0x0207B080)
// Original VA: 0x000000014207AC60 | File offset: 0x0207A260
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: the static helper Ease (0x0207AC10), VEase, REase and TEase call: a 13-case jump table
//   (EEasingFunc::Step .. CircularInOut; Linear falls to the default), after the code inside
//   the function's .pdata range. Its address sorts right after UKismetMathLibrary::Ease.
float EaseAlpha(float InAlpha, uint8 EasingFunc, float BlendExp, int32 Steps)
{
	switch (EasingFunc)
	{
	case EEasingFunc::Step:					return FMath::InterpStep<float>(0.f, 1.f, InAlpha, Steps);
	case EEasingFunc::SinusoidalIn:			return FMath::InterpSinIn<float>(0.f, 1.f, InAlpha);
	case EEasingFunc::SinusoidalOut:		return FMath::InterpSinOut<float>(0.f, 1.f, InAlpha);
	case EEasingFunc::SinusoidalInOut:		return FMath::InterpSinInOut<float>(0.f, 1.f, InAlpha);
	case EEasingFunc::EaseIn:				return FMath::InterpEaseIn<float>(0.f, 1.f, InAlpha, BlendExp);
	case EEasingFunc::EaseOut:				return FMath::InterpEaseOut<float>(0.f, 1.f, InAlpha, BlendExp);
	case EEasingFunc::EaseInOut:			return FMath::InterpEaseInOut<float>(0.f, 1.f, InAlpha, BlendExp);
	case EEasingFunc::ExpoIn:				return FMath::InterpExpoIn<float>(0.f, 1.f, InAlpha);
	case EEasingFunc::ExpoOut:				return FMath::InterpExpoOut<float>(0.f, 1.f, InAlpha);
	case EEasingFunc::ExpoInOut:			return FMath::InterpExpoInOut<float>(0.f, 1.f, InAlpha);
	case EEasingFunc::CircularIn:			return FMath::InterpCircularIn<float>(0.f, 1.f, InAlpha);
	case EEasingFunc::CircularOut:			return FMath::InterpCircularOut<float>(0.f, 1.f, InAlpha);
	case EEasingFunc::CircularInOut:		return FMath::InterpCircularInOut<float>(0.f, 1.f, InAlpha);
	}
	return InAlpha;
}

// The Blueprint warning ids, in their declaration order: their .bss slots are 8 bytes apart in
// the reference (DivideByZeroWarning 0x04897810 in Log, InvalidDateWarning 0x04897828 in
// ReportError_DaysInMonth). The constructor that registers them is not recovered.
const FName DivideByZeroWarning = FName("DivideByZeroWarning");
const FName NegativeSqrtWarning = FName("NegativeSqrtWarning");
const FName ZeroLengthProjectionWarning = FName("ZeroLengthProjectionWarning");
const FName InvalidDateWarning = FName("InvalidDateWarning");

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208EAA0 (end 0x0208EAB5), no .pdata (leaf)
// Original VA: 0x000000014208EAA0 | File offset: 0x0208E0A0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: a 21-byte leaf tail-calling FFrame::KismetExecutionMessage (0x0137CC10) with the
//   "Divide by zero: Divide_ByteByte" literal and DivideByZeroWarning. The inlined Kismet math functions call these from
//   their exec thunks (analysis/native-implementations.json lists the address under the
//   UFunction's name); the twelve leaves sort alphabetically by name.
void UKismetMathLibrary::ReportError_Divide_ByteByte()
{
	FFrame::KismetExecutionMessage(TEXT("Divide by zero: Divide_ByteByte"), ELogVerbosity::Warning, DivideByZeroWarning);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208EB80 (end 0x0208EB95), no .pdata (leaf)
// Original VA: 0x000000014208EB80 | File offset: 0x0208E180
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: a 21-byte leaf tail-calling FFrame::KismetExecutionMessage (0x0137CC10) with the
//   "Modulo by zero" literal and DivideByZeroWarning. The inlined Kismet math functions call these from
//   their exec thunks (analysis/native-implementations.json lists the address under the
//   UFunction's name); the twelve leaves sort alphabetically by name.
void UKismetMathLibrary::ReportError_Percent_ByteByte()
{
	FFrame::KismetExecutionMessage(TEXT("Modulo by zero"), ELogVerbosity::Warning, DivideByZeroWarning);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208EAC0 (end 0x0208EAD5), no .pdata (leaf)
// Original VA: 0x000000014208EAC0 | File offset: 0x0208E0C0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: a 21-byte leaf tail-calling FFrame::KismetExecutionMessage (0x0137CC10) with the
//   "Divide by zero: Divide_IntInt" literal and DivideByZeroWarning. The inlined Kismet math functions call these from
//   their exec thunks (analysis/native-implementations.json lists the address under the
//   UFunction's name); the twelve leaves sort alphabetically by name.
void UKismetMathLibrary::ReportError_Divide_IntInt()
{
	FFrame::KismetExecutionMessage(TEXT("Divide by zero: Divide_IntInt"), ELogVerbosity::Warning, DivideByZeroWarning);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208EBA0 (end 0x0208EBB5), no .pdata (leaf)
// Original VA: 0x000000014208EBA0 | File offset: 0x0208E1A0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: a 21-byte leaf tail-calling FFrame::KismetExecutionMessage (0x0137CC10) with the
//   "Modulo by zero" literal and DivideByZeroWarning. The inlined Kismet math functions call these from
//   their exec thunks (analysis/native-implementations.json lists the address under the
//   UFunction's name); the twelve leaves sort alphabetically by name.
void UKismetMathLibrary::ReportError_Percent_IntInt()
{
	FFrame::KismetExecutionMessage(TEXT("Modulo by zero"), ELogVerbosity::Warning, DivideByZeroWarning);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208EBE0 (end 0x0208EBF5), no .pdata (leaf)
// Original VA: 0x000000014208EBE0 | File offset: 0x0208E1E0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: a 21-byte leaf tail-calling FFrame::KismetExecutionMessage (0x0137CC10) with the
//   "Attempt to take Sqrt() of negative number - returning 0." literal and NegativeSqrtWarning. The inlined Kismet math functions call these from
//   their exec thunks (analysis/native-implementations.json lists the address under the
//   UFunction's name); the twelve leaves sort alphabetically by name.
void UKismetMathLibrary::ReportError_Sqrt()
{
	FFrame::KismetExecutionMessage(TEXT("Attempt to take Sqrt() of negative number - returning 0."), ELogVerbosity::Warning, NegativeSqrtWarning);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208EB20 (end 0x0208EB35), no .pdata (leaf)
// Original VA: 0x000000014208EB20 | File offset: 0x0208E120
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: a 21-byte leaf tail-calling FFrame::KismetExecutionMessage (0x0137CC10) with the
//   "Divide by zero: Divide_VectorFloat" literal and DivideByZeroWarning. The inlined Kismet math functions call these from
//   their exec thunks (analysis/native-implementations.json lists the address under the
//   UFunction's name); the twelve leaves sort alphabetically by name.
void UKismetMathLibrary::ReportError_Divide_VectorFloat()
{
	FFrame::KismetExecutionMessage(TEXT("Divide by zero: Divide_VectorFloat"), ELogVerbosity::Warning, DivideByZeroWarning);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208EB40 (end 0x0208EB55), no .pdata (leaf)
// Original VA: 0x000000014208EB40 | File offset: 0x0208E140
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: a 21-byte leaf tail-calling FFrame::KismetExecutionMessage (0x0137CC10) with the
//   "Divide by zero: Divide_VectorInt" literal and DivideByZeroWarning. The inlined Kismet math functions call these from
//   their exec thunks (analysis/native-implementations.json lists the address under the
//   UFunction's name); the twelve leaves sort alphabetically by name.
void UKismetMathLibrary::ReportError_Divide_VectorInt()
{
	FFrame::KismetExecutionMessage(TEXT("Divide by zero: Divide_VectorInt"), ELogVerbosity::Warning, DivideByZeroWarning);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208EB60 (end 0x0208EB75), no .pdata (leaf)
// Original VA: 0x000000014208EB60 | File offset: 0x0208E160
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: a 21-byte leaf tail-calling FFrame::KismetExecutionMessage (0x0137CC10) with the
//   "Divide by zero: Divide_VectorVector" literal and DivideByZeroWarning. The inlined Kismet math functions call these from
//   their exec thunks (analysis/native-implementations.json lists the address under the
//   UFunction's name); the twelve leaves sort alphabetically by name.
void UKismetMathLibrary::ReportError_Divide_VectorVector()
{
	FFrame::KismetExecutionMessage(TEXT("Divide by zero: Divide_VectorVector"), ELogVerbosity::Warning, DivideByZeroWarning);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208EB00 (end 0x0208EB15), no .pdata (leaf)
// Original VA: 0x000000014208EB00 | File offset: 0x0208E100
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: a 21-byte leaf tail-calling FFrame::KismetExecutionMessage (0x0137CC10) with the
//   "Divide by zero: Divide_Vector2DVector2D" literal and DivideByZeroWarning. The inlined Kismet math functions call these from
//   their exec thunks (analysis/native-implementations.json lists the address under the
//   UFunction's name); the twelve leaves sort alphabetically by name.
void UKismetMathLibrary::ReportError_Divide_Vector2DVector2D()
{
	FFrame::KismetExecutionMessage(TEXT("Divide by zero: Divide_Vector2DVector2D"), ELogVerbosity::Warning, DivideByZeroWarning);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208EBC0 (end 0x0208EBD5), no .pdata (leaf)
// Original VA: 0x000000014208EBC0 | File offset: 0x0208E1C0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: a 21-byte leaf tail-calling FFrame::KismetExecutionMessage (0x0137CC10) with the
//   "Divide by zero: ProjectVectorOnToV..." literal and ZeroLengthProjectionWarning. The inlined Kismet math functions call these from
//   their exec thunks (analysis/native-implementations.json lists the address under the
//   UFunction's name); the twelve leaves sort alphabetically by name.
void UKismetMathLibrary::ReportError_ProjectVectorOnToVector()
{
	FFrame::KismetExecutionMessage(TEXT("Divide by zero: ProjectVectorOnToVector with zero Target vector"), ELogVerbosity::Warning, ZeroLengthProjectionWarning);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208EAE0 (end 0x0208EAF5), no .pdata (leaf)
// Original VA: 0x000000014208EAE0 | File offset: 0x0208E0E0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: a 21-byte leaf tail-calling FFrame::KismetExecutionMessage (0x0137CC10) with the
//   "Divide by zero: Divide_Vector2DFloat" literal and DivideByZeroWarning. The inlined Kismet math functions call these from
//   their exec thunks (analysis/native-implementations.json lists the address under the
//   UFunction's name); the twelve leaves sort alphabetically by name.
void UKismetMathLibrary::ReportError_Divide_Vector2DFloat()
{
	FFrame::KismetExecutionMessage(TEXT("Divide by zero: Divide_Vector2DFloat"), ELogVerbosity::Warning, DivideByZeroWarning);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208EA80 (end 0x0208EA95), no .pdata (leaf)
// Original VA: 0x000000014208EA80 | File offset: 0x0208E080
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: a 21-byte leaf tail-calling FFrame::KismetExecutionMessage (0x0137CC10) with the
//   "Invalid month (must be between 1 and 12): DaysInMonth" literal and InvalidDateWarning. The inlined Kismet math functions call these from
//   their exec thunks (analysis/native-implementations.json lists the address under the
//   UFunction's name); the twelve leaves sort alphabetically by name.
void UKismetMathLibrary::ReportError_DaysInMonth()
{
	FFrame::KismetExecutionMessage(TEXT("Invalid month (must be between 1 and 12): DaysInMonth"), ELogVerbosity::Warning, InvalidDateWarning);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208D1E0 (end 0x0208D227)
// Original VA: 0x000000014208D1E0 | File offset: 0x0208C7E0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execRandomBoolWithWeight; one rand() per call, scaled by 1/RAND_MAX (FMath::FRandRange(0, 1)).
bool UKismetMathLibrary::RandomBoolWithWeight(float Weight)
{
	//If the Weight equals to 0.0f then always return false
	if (Weight <= 0.0f)
	{
		return false;
	}
	else
	{
		//If the Weight is higher or equal to the random number then return true
		return Weight >= FMath::FRandRange(0.0f, 1.0f);
	}

}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0207F8A0 (end 0x0207F915)
// Original VA: 0x000000014207F8A0 | File offset: 0x0207EEA0
// Recovery: high-confidence inferred (UE4 name; called by execPercent_FloatFloat) | Matching: see analysis/functions.json
// Evidence: execPercent_FloatFloat (CustomThunk) calls it, so natives.py lists it as Percent_FloatFloat;
//   the body is GenericPercent_FloatFloat's (B != 0 ? FMath::Fmod(A, B) : 0), and its address
//   sorts between FromSeconds (0x0207E500) and GetAxes (0x0207FD00).
float UKismetMathLibrary::GenericPercent_FloatFloat(float A, float B)
{
	return (B != 0.f) ? FMath::Fmod(A, B) : 0.f;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02089BC0 (end 0x02089C26)
// Original VA: 0x0000000142089BC0 | File offset: 0x020891C0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execLog; KismetExecutionMessage with DivideByZeroWarning when Base <= 0, else
//   logf(A) / logf(Base).
float UKismetMathLibrary::Log(float A, float Base)
{
	float Result = 0.f;
	if(Base <= 0.f)
	{
		FFrame::KismetExecutionMessage(TEXT("Divide by zero: Log"), ELogVerbosity::Warning, DivideByZeroWarning);
	}
	else
	{
		Result = FMath::Loge(A) / FMath::Loge(Base);
	}
	return Result;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0207CFB0 (end 0x0207D09C)
// Original VA: 0x000000014207CFB0 | File offset: 0x0207C5B0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execFMod; the quotient's sign times FloorToInt(|quotient|), then FMath::Fmod.
int32 UKismetMathLibrary::FMod(float Dividend, float Divisor, float& Remainder)
{
	int32 Result;
	if (Divisor != 0.f)
	{
		const float Quotient = Dividend / Divisor;
		Result = (Quotient < 0.f ? -1 : 1) * FMath::FloorToInt(FMath::Abs(Quotient));
		Remainder = FMath::Fmod(Dividend, Divisor);
	}
	else
	{
		FFrame::KismetExecutionMessage(TEXT("Attempted modulo 0 - returning 0."), ELogVerbosity::Warning, DivideByZeroWarning);

		Result = 0;
		Remainder = 0.f;
	}

	return Result;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02089F40 (end 0x02089F86)
// Original VA: 0x0000000142089F40 | File offset: 0x02089540
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execMakePulsatingValue; 0.5 + 0.5 * sinf(...), computed in float under /fp:fast.
float UKismetMathLibrary::MakePulsatingValue(float InCurrentTime, float InPulsesPerSecond, float InPhase)
{
	return FMath::MakePulsatingValue((double)InCurrentTime, InPulsesPerSecond, InPhase);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208A7D0 (end 0x0208A83B)
// Original VA: 0x000000014208A7D0 | File offset: 0x02089DD0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execMaxOfIntArray; FMath::Max over the array, INDEX_NONE and T() when empty.
void UKismetMathLibrary::MaxOfIntArray(const TArray<int32>& IntArray, int32& IndexOfMaxValue, int32& MaxValue)
{
	MaxValue = FMath::Max(IntArray, &IndexOfMaxValue);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208AAD0 (end 0x0208AB3B)
// Original VA: 0x000000014208AAD0 | File offset: 0x0208A0D0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execMinOfIntArray; FMath::Min over the array, INDEX_NONE and T() when empty.
void UKismetMathLibrary::MinOfIntArray(const TArray<int32>& IntArray, int32& IndexOfMinValue, int32& MinValue)
{
	MinValue = FMath::Min<int32>(IntArray, &IndexOfMinValue);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208A6F0 (end 0x0208A7CD)
// Original VA: 0x000000014208A6F0 | File offset: 0x02089CF0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execMaxOfFloatArray; FMath::Max over the array, INDEX_NONE and T() when empty.
void UKismetMathLibrary::MaxOfFloatArray(const TArray<float>& FloatArray, int32& IndexOfMaxValue, float& MaxValue)
{
	MaxValue = FMath::Max(FloatArray, &IndexOfMaxValue);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208A9F0 (end 0x0208AACD)
// Original VA: 0x000000014208A9F0 | File offset: 0x02089FF0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execMinOfFloatArray; FMath::Min over the array, INDEX_NONE and T() when empty.
void UKismetMathLibrary::MinOfFloatArray(const TArray<float>& FloatArray, int32& IndexOfMinValue, float& MinValue)
{
	MinValue = FMath::Min(FloatArray, &IndexOfMinValue);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208A680 (end 0x0208A6EA)
// Original VA: 0x000000014208A680 | File offset: 0x02089C80
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execMaxOfByteArray; FMath::Max over the array, INDEX_NONE and T() when empty.
void UKismetMathLibrary::MaxOfByteArray(const TArray<uint8>& ByteArray, int32& IndexOfMaxValue, uint8& MaxValue)
{
	MaxValue = FMath::Max(ByteArray, &IndexOfMaxValue);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208A980 (end 0x0208A9EA)
// Original VA: 0x000000014208A980 | File offset: 0x02089F80
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execMinOfByteArray; FMath::Min over the array, INDEX_NONE and T() when empty.
void UKismetMathLibrary::MinOfByteArray(const TArray<uint8>& ByteArray, int32& IndexOfMinValue, uint8& MinValue)
{
	MinValue = FMath::Min(ByteArray, &IndexOfMinValue);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0207AC10 (end 0x0207AC59)
// Original VA: 0x000000014207AC10 | File offset: 0x0207A210
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execEase; Lerp(A, B, EaseAlpha(...)) with the TEnumAsByte argument passed by reference
//   (it has a user copy constructor).
float UKismetMathLibrary::Ease(float A, float B, float Alpha, TEnumAsByte<EEasingFunc::Type> EasingFunc, float BlendExp, int32 Steps)
{
	return Lerp(A, B, EaseAlpha(Alpha, EasingFunc, BlendExp, Steps));
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02095830 (end 0x020958E4)
// Original VA: 0x0000000142095830 | File offset: 0x02094E30
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execVEase; VLerp(A, B, EaseAlpha(...)).
FVector UKismetMathLibrary::VEase(FVector A, FVector B, float Alpha, TEnumAsByte<EEasingFunc::Type> EasingFunc, float BlendExp, int32 Steps)
{
	return VLerp(A, B, EaseAlpha(Alpha, EasingFunc, BlendExp, Steps));
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208D420 (end 0x0208D4A4)
// Original VA: 0x000000014208D420 | File offset: 0x0208CA20
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execRandomRotator; FRand() * 360 for yaw and pitch, and for roll when bRoll.
FRotator UKismetMathLibrary::RandomRotator(bool bRoll)
{
	FRotator RRot;
	RRot.Yaw = FMath::FRand() * 360.f;
	RRot.Pitch = FMath::FRand() * 360.f;

	if (bRoll)
	{
		RRot.Roll = FMath::FRand() * 360.f;
	}
	else
	{
		RRot.Roll = 0;
	}
	return RRot;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0207D4A0 (end 0x0207D629)
// Original VA: 0x000000014207D4A0 | File offset: 0x0207CAA0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execFindClosestPointOnLine; GetSafeNormal (FVector::ZeroVector, InvSqrt) of the direction.
FVector UKismetMathLibrary::FindClosestPointOnLine(FVector Point, FVector LineOrigin, FVector LineDirection)
{
	const FVector SafeDir = LineDirection.GetSafeNormal();
	const FVector ClosestPoint = LineOrigin + (SafeDir * ((Point-LineOrigin) | SafeDir));
	return ClosestPoint;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02075730 (end 0x0207582F)
// Original VA: 0x0000000142075730 | File offset: 0x02074D30
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execClampVectorSize; FVector::GetClampedToSize.
FVector UKismetMathLibrary::ClampVectorSize(FVector A, float Min, float Max)
{
	return A.GetClampedToSize(Min, Max);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02083DE0 (end 0x02083EE8)
// Original VA: 0x0000000142083DE0 | File offset: 0x020833E0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execGetVectorArrayAverage; the sum over the array divided by Num().
FVector UKismetMathLibrary::GetVectorArrayAverage(const TArray<FVector>& Vectors)
{
	FVector Sum(0.f);
	FVector Average(0.f);

	if (Vectors.Num() > 0)
	{
		for (int32 VecIdx=0; VecIdx<Vectors.Num(); VecIdx++)
		{
			Sum += Vectors[VecIdx];
		}

		Average = Sum / ((float)Vectors.Num());
	}

	return Average;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x020756B0 (end 0x02075730)
// Original VA: 0x00000001420756B0 | File offset: 0x02074CB0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execClampAxis; FRotator::ClampAxis (FMath::Fmod by 360, FmodReportError 0x0126F320).
float UKismetMathLibrary::ClampAxis(float Angle)
{
	return FRotator::ClampAxis(Angle);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208B950 (end 0x0208B9D9)
// Original VA: 0x000000014208B950 | File offset: 0x0208AF50
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execNormalizeAxis; FRotator::NormalizeAxis.
float UKismetMathLibrary::NormalizeAxis(float Angle)
{
	return FRotator::NormalizeAxis(Angle);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208A5B0 (end 0x0208A5DB)
// Original VA: 0x000000014208A5B0 | File offset: 0x02089BB0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execMakeTimespan; FTimespan's constructor calls FTimespan::Assign (0x011D5640, Core).
FTimespan UKismetMathLibrary::MakeTimespan(int32 Days, int32 Hours, int32 Minutes, int32 Seconds, int32 Milliseconds)
{
	return FTimespan(Days, Hours, Minutes, Seconds, Milliseconds * 1000 * 1000);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208A580 (end 0x0208A5A7)
// Original VA: 0x000000014208A580 | File offset: 0x02089B80
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execMakeTimespan2; FTimespan::Assign (0x011D5640).
FTimespan UKismetMathLibrary::MakeTimespan2(int32 Days, int32 Hours, int32 Minutes, int32 Seconds, int32 FractionNano)
{
	return FTimespan(Days, Hours, Minutes, Seconds, FractionNano);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x020727D0 (end 0x020728F3)
// Original VA: 0x00000001420727D0 | File offset: 0x02071DD0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execBreakTimespan; 64-bit tick divisions by the ETimespan constants.
void UKismetMathLibrary::BreakTimespan(FTimespan InTimespan, int32& Days, int32& Hours, int32& Minutes, int32& Seconds, int32& Milliseconds)
{
	Days = InTimespan.GetDays();
	Hours = InTimespan.GetHours();
	Minutes = InTimespan.GetMinutes();
	Seconds = InTimespan.GetSeconds();
	Milliseconds = InTimespan.GetFractionMilli();
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x020726C0 (end 0x020727CA)
// Original VA: 0x00000001420726C0 | File offset: 0x02071CC0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execBreakTimespan2; as BreakTimespan with the fraction in nanoseconds.
void UKismetMathLibrary::BreakTimespan2(FTimespan InTimespan, int32& Days, int32& Hours, int32& Minutes, int32& Seconds, int32& FractionNano)
{
	Days = InTimespan.GetDays();
	Hours = InTimespan.GetHours();
	Minutes = InTimespan.GetMinutes();
	Seconds = InTimespan.GetSeconds();
	FractionNano = InTimespan.GetFractionNano();
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02079F20 (end 0x0207A1E1)
// Original VA: 0x0000000142079F20 | File offset: 0x02079520
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execCreateVectorFromYawPitch; two FMath::SinCos expansions, as FRotator::Vector, times Length.
FVector UKismetMathLibrary::CreateVectorFromYawPitch(float Yaw, float Pitch, float Length /*= 1.0f */)
{
	// FRotator::Vector() behaviour
	float CP, SP, CY, SY;
	FMath::SinCos(&SP, &CP, FMath::DegreesToRadians(Pitch));
	FMath::SinCos(&SY, &CY, FMath::DegreesToRadians(Yaw));
	FVector V = FVector(CP*CY, CP*SY, SP) * Length;

	return V;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x020845D0 (end 0x02084748)
// Original VA: 0x00000001420845D0 | File offset: 0x02083BD0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execGetYawPitchFromVector; GetSafeNormal, then FGenericPlatformMath::Atan2 (0x01112E50) twice.
void UKismetMathLibrary::GetYawPitchFromVector(FVector InVec, float& Yaw, float& Pitch)
{
	FVector NormalizedVector = InVec.GetSafeNormal();
	// Find yaw.
	Yaw = FMath::RadiansToDegrees(FMath::Atan2(NormalizedVector.Y, NormalizedVector.X));

	// Find pitch.
	Pitch = FMath::RadiansToDegrees(FMath::Atan2(NormalizedVector.Z, FMath::Sqrt(NormalizedVector.X*NormalizedVector.X + NormalizedVector.Y*NormalizedVector.Y)));
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208EC00 (end 0x0208EC06), no .pdata (leaf)
// Original VA: 0x000000014208EC00 | File offset: 0x0208E200
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execResetRandomStream; a 6-byte leaf storing InitialSeed into the mutable Seed (FRandomStream::Reset).
void UKismetMathLibrary::ResetRandomStream(const FRandomStream& Stream)
{
	Stream.Reset();
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208FBC0 (end 0x0208FBDA)
// Original VA: 0x000000014208FBC0 | File offset: 0x0208F1C0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execSeedRandomStream; FRandomStream::GenerateNewSeed, Initialize(rand()).
void UKismetMathLibrary::SeedRandomStream(FRandomStream& Stream)
{
	Stream.GenerateNewSeed();
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02085E70 (end 0x02085F1E)
// Original VA: 0x0000000142085E70 | File offset: 0x02085470
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execIsPointInBox; FBox(Origin - Extent, Origin + Extent).IsInsideOrOn(Point).
bool UKismetMathLibrary::IsPointInBox(FVector Point, FVector BoxOrigin, FVector BoxExtent)
{
	const FBox Box(BoxOrigin - BoxExtent, BoxOrigin + BoxExtent);
	return Box.IsInsideOrOn(Point);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02082AC0 (end 0x02082AED)
// Original VA: 0x0000000142082AC0 | File offset: 0x020820C0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execGetRightVector; the out-of-line FRotationMatrix constructor (0x009C4CB0), then the matrix's Y axis.
FVector UKismetMathLibrary::GetRightVector(FRotator InRot)
{
	return FRotationMatrix(InRot).GetScaledAxis(EAxis::Y);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02083D60 (end 0x02083D8D)
// Original VA: 0x0000000142083D60 | File offset: 0x02083360
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execGetUpVector; the out-of-line FRotationMatrix constructor (0x009C4CB0), then the matrix's Z axis.
FVector UKismetMathLibrary::GetUpVector(FRotator InRot)
{
	return FRotationMatrix(InRot).GetScaledAxis(EAxis::Z);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0207FD00 (end 0x0207FD95)
// Original VA: 0x000000014207FD00 | File offset: 0x0207F300
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execGetAxes; the out-of-line FRotationMatrix constructor (0x009C4CB0), then its three axes from the named local.
void UKismetMathLibrary::GetAxes(FRotator A, FVector& X, FVector& Y, FVector& Z)
{
	FRotationMatrix R(A);
	R.GetScaledAxes(X, Y, Z);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02072560 (end 0x020725CA)
// Original VA: 0x0000000142072560 | File offset: 0x02071B60
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execBreakRotIntoAxes; the out-of-line FRotationMatrix constructor (0x009C4CB0), then its three axes through the returned temporary.
void UKismetMathLibrary::BreakRotIntoAxes(const FRotator& InRot, FVector& X, FVector& Y, FVector& Z)
{
	FRotationMatrix(InRot).GetScaledAxes(X, Y, Z);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02089DB0 (end 0x02089F32)
// Original VA: 0x0000000142089DB0 | File offset: 0x020893B0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execMakePlaneFromPointAndNormal; FPlane(Point, Normal.GetSafeNormal()).
FPlane UKismetMathLibrary::MakePlaneFromPointAndNormal(FVector Point, FVector Normal)
{
	return FPlane(Point, Normal.GetSafeNormal());
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02088D60 (end 0x02088E76)
// Original VA: 0x0000000142088D60 | File offset: 0x02088360
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execLinePlaneIntersection; -1 and FVector::ZeroVector outside the segment.
bool UKismetMathLibrary::LinePlaneIntersection(const FVector& LineStart, const FVector& LineEnd, const FPlane& APlane, float& T, FVector& Intersection)
{
	FVector RayDir = LineEnd - LineStart;

	// Check ray is not parallel to plane
	if ((RayDir | APlane) == 0.0f)
	{
		T = -1.0f;
		Intersection = FVector::ZeroVector;
		return false;
	}

	T = ((APlane.W - (LineStart | APlane)) / (RayDir | APlane));

	// Check intersection is not outside line segment
	if (T < 0.0f || T > 1.0f)
	{
		Intersection = FVector::ZeroVector;
		return false;
	}

	// Calculate intersection point
	Intersection = LineStart + RayDir * T;

	return true;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02088E80 (end 0x02088FDA)
// Original VA: 0x0000000142088E80 | File offset: 0x02088480
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execLinePlaneIntersection_OriginNormal; as LinePlaneIntersection, the plane given by a point.
bool UKismetMathLibrary::LinePlaneIntersection_OriginNormal(const FVector& LineStart, const FVector& LineEnd, FVector PlaneOrigin, FVector PlaneNormal, float& T, FVector& Intersection)
{
	FVector RayDir = LineEnd - LineStart;

	// Check ray is not parallel to plane
	if ((RayDir | PlaneNormal) == 0.0f)
	{
		T = -1.0f;
		Intersection = FVector::ZeroVector;
		return false;
	}

	T = (((PlaneOrigin - LineStart) | PlaneNormal) / (RayDir | PlaneNormal));

	// Check intersection is not outside line segment
	if (T < 0.0f || T > 1.0f)
	{
		Intersection = FVector::ZeroVector;
		return false;
	}

	// Calculate intersection point
	Intersection = LineStart + RayDir * T;

	return true;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02084810 (end 0x02084842), no .pdata (leaf)
// Original VA: 0x0000000142084810 | File offset: 0x02083E10
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: a leaf without .pdata the exec thunk calls (analysis/native-implementations.json); minss/maxss of the absolute values, then Max * sqrt(1 + Ratio^2).
float UKismetMathLibrary::Hypotenuse(float Width, float Height)
{
	// This implementation avoids overflow/underflow caused by squaring width and height:
	Width = FMath::Abs(Width);
	Height = FMath::Abs(Height);

	float Min = FGenericPlatformMath::Min(Width, Height);
	float Max = FGenericPlatformMath::Max(Width, Height);
	float Ratio = Min / Max;
	return Max * FMath::Sqrt(1.f + Ratio * Ratio);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02084D70 (end 0x02084DA9), no .pdata (leaf)
// Original VA: 0x0000000142084D70 | File offset: 0x02084370
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: a leaf without .pdata the exec thunk calls (analysis/native-implementations.json); the InclusiveMin test first (r9b).
bool UKismetMathLibrary::InRange_FloatFloat(float Value, float Min, float Max, bool InclusiveMin, bool InclusiveMax)
{
	return ((InclusiveMin ? (Value >= Min) : (Value > Min)) && (InclusiveMax ? (Value <= Max) : (Value < Max)));
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02084DB0 (end 0x02084DE7), no .pdata (leaf)
// Original VA: 0x0000000142084DB0 | File offset: 0x020843B0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: a leaf without .pdata the exec thunk calls (analysis/native-implementations.json); the integer form of InRange_FloatFloat.
bool UKismetMathLibrary::InRange_IntInt(int32 Value, int32 Min, int32 Max, bool InclusiveMin, bool InclusiveMax)
{
	return ((InclusiveMin ? (Value >= Min) : (Value > Min)) && (InclusiveMax ? (Value <= Max) : (Value < Max)));
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208A620 (end 0x0208A65D), no .pdata (leaf)
// Original VA: 0x000000014208A620 | File offset: 0x02089C20
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: a leaf without .pdata the exec thunk calls (analysis/native-implementations.json); FMath::GetMappedRangeValueUnclamped.
float UKismetMathLibrary::MapRangeUnclamped(float Value, float InRangeA, float InRangeB, float OutRangeA, float OutRangeB)
{
	return FMath::GetMappedRangeValueUnclamped(FVector2D(InRangeA, InRangeB), FVector2D(OutRangeA, OutRangeB), Value);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208A5E0 (end 0x0208A61C), no .pdata (leaf)
// Original VA: 0x000000014208A5E0 | File offset: 0x02089BE0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: a leaf without .pdata the exec thunk calls (analysis/native-implementations.json); FMath::GetMappedRangeValueClamped.
float UKismetMathLibrary::MapRangeClamped(float Value, float InRangeA, float InRangeB, float OutRangeA, float OutRangeB)
{
	return FMath::GetMappedRangeValueClamped(FVector2D(InRangeA, InRangeB), FVector2D(OutRangeA, OutRangeB), Value);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208B9E0 (end 0x0208BA18), no .pdata (leaf)
// Original VA: 0x000000014208B9E0 | File offset: 0x0208AFE0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: a leaf without .pdata the exec thunk calls (analysis/native-implementations.json); 0 or 1 for an empty range, else the fraction of the (swapped) range.
float UKismetMathLibrary::NormalizeToRange(float Value, float RangeMin, float RangeMax)
{
	if (RangeMin == RangeMax)
	{
		if (Value < RangeMin)
		{
			return 0.f;
		}
		else
		{
			return 1.f;
		}
	}

	if (RangeMin > RangeMax)
	{
		Swap(RangeMin, RangeMax);
	}
	return (Value - RangeMin) / (RangeMax - RangeMin);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02089F90 (end 0x02089F99), no .pdata (leaf)
// Original VA: 0x0000000142089F90 | File offset: 0x02089590
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: a leaf without .pdata the exec thunk calls (analysis/native-implementations.json); FRandomStream(InitialSeed) into the return slot.
FRandomStream UKismetMathLibrary::MakeRandomStream(int32 InitialSeed)
{
	return FRandomStream(InitialSeed);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02072550 (end 0x02072555), no .pdata (leaf)
// Original VA: 0x0000000142072550 | File offset: 0x02071B50
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: a leaf without .pdata the exec thunk calls (analysis/native-implementations.json); copies InitialSeed out.
void UKismetMathLibrary::BreakRandomStream(const FRandomStream& InRandomStream, int32& InitialSeed)
{
	InitialSeed = InRandomStream.GetInitialSeed();
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02090EB0 (end 0x02090EB6), no .pdata (leaf)
// Original VA: 0x0000000142090EB0 | File offset: 0x020904B0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: a leaf without .pdata the exec thunk calls (analysis/native-implementations.json); FRandomStream::Initialize.
void UKismetMathLibrary::SetRandomStreamSeed(FRandomStream& Stream, int32 NewSeed)
{
	Stream.Initialize(NewSeed);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208D180 (end 0x0208D1D4), no .pdata (leaf)
// Original VA: 0x000000014208D180 | File offset: 0x0208C780
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: a leaf without .pdata the exec thunk calls (analysis/native-implementations.json); FRandomStream's seed mutation (196314165, 907633515) and GetFraction's mantissa trick, RandRange(0, 1).
bool UKismetMathLibrary::RandomBoolFromStream(const FRandomStream& Stream)
{
	return (Stream.RandRange(0, 1) == 1) ? true : false;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208D290 (end 0x0208D2D2), no .pdata (leaf)
// Original VA: 0x000000014208D290 | File offset: 0x0208C890
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: a leaf without .pdata the exec thunk calls (analysis/native-implementations.json); FRandomStream's seed mutation (196314165, 907633515) and GetFraction's mantissa trick.
float UKismetMathLibrary::RandomFloatFromStream(const FRandomStream& Stream)
{
	return Stream.FRand();
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208D2E0 (end 0x0208D336), no .pdata (leaf)
// Original VA: 0x000000014208D2E0 | File offset: 0x0208C8E0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: a leaf without .pdata the exec thunk calls (analysis/native-implementations.json); FRandomStream's seed mutation (196314165, 907633515) and GetFraction's mantissa trick, scaled to [Min, Max).
float UKismetMathLibrary::RandomFloatInRangeFromStream(float Min, float Max, const FRandomStream& Stream)
{
	return Min + (Max - Min) * RandomFloatFromStream(Stream);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208D230 (end 0x0208D288), no .pdata (leaf)
// Original VA: 0x000000014208D230 | File offset: 0x0208C830
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: a leaf without .pdata the exec thunk calls (analysis/native-implementations.json); FRandomStream's seed mutation (196314165, 907633515) and GetFraction's mantissa trick, compared with Weight.
bool UKismetMathLibrary::RandomBoolWithWeightFromStream(float Weight, const FRandomStream& RandomStream)
{
	//If the Weight equals to 0.0f then always return false
	if (Weight <= 0.0f)
	{
		return false;
	}
	else
	{
		//Create the random float from the specified stream
		float Number = UKismetMathLibrary::RandomFloatFromStream(RandomStream);

		//If the Weight is higher or equal to number generated from stream then return true
		return Weight >= Number;
	}

}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208D340 (end 0x0208D3A6), no .pdata (leaf)
// Original VA: 0x000000014208D340 | File offset: 0x0208C940
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: a leaf without .pdata the exec thunk calls (analysis/native-implementations.json); FRandomStream's seed mutation (196314165, 907633515) and GetFraction's mantissa trick, RandHelper(Max).
int32 UKismetMathLibrary::RandomIntegerFromStream(int32 Max, const FRandomStream& Stream)
{
	return Stream.RandHelper(Max);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208D3B0 (end 0x0208D41E), no .pdata (leaf)
// Original VA: 0x000000014208D3B0 | File offset: 0x0208C9B0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: a leaf without .pdata the exec thunk calls (analysis/native-implementations.json); FRandomStream's seed mutation (196314165, 907633515) and GetFraction's mantissa trick, RandRange(Min, Max).
int32 UKismetMathLibrary::RandomIntegerInRangeFromStream(int32 Min, int32 Max, const FRandomStream& Stream)
{
	return Stream.RandRange(Min, Max);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208D4B0 (end 0x0208D5A7), no .pdata (leaf)
// Original VA: 0x000000014208D4B0 | File offset: 0x0208CAB0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: a leaf without .pdata the exec thunk calls (analysis/native-implementations.json); FRandomStream's seed mutation (196314165, 907633515) and GetFraction's mantissa trick, three times for a rotator with bRoll.
FRotator UKismetMathLibrary::RandomRotatorFromStream(bool bRoll, const FRandomStream& Stream)
{
	FRotator RRot;
	RRot.Yaw = RandomFloatFromStream(Stream) * 360.f;
	RRot.Pitch = RandomFloatFromStream(Stream) * 360.f;

	if (bRoll)
	{
		RRot.Roll = RandomFloatFromStream(Stream) * 360.f;
	}
	else
	{
		RRot.Roll = 0;
	}
	return RRot;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02076420 (end 0x020764D2)
// Original VA: 0x0000000142076420 | File offset: 0x02075A20
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execComposeRotators; FRotator::Quaternion (0x011A0970), the VectorQuaternionMultiply product (QMULTI_SIGN_MASK0-2), FQuat::Rotator (0x011A2050) through FRotator(const FQuat&) (0x01188C70).
FRotator UKismetMathLibrary::ComposeRotators(FRotator A, FRotator B)
{
	FQuat AQuat = FQuat(A);
	FQuat BQuat = FQuat(B);

	return FRotator(BQuat*AQuat);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02094CE0 (end 0x02094D78)
// Original VA: 0x0000000142094CE0 | File offset: 0x020942E0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execTransformRotation; FRotator::Quaternion (0x011A0970), the VectorQuaternionMultiply product (QMULTI_SIGN_MASK0-2), FQuat::Rotator (0x011A2050), the transform's rotation first.
FRotator UKismetMathLibrary::TransformRotation(const FTransform& T, FRotator Rotation)
{
	return T.TransformRotation(Rotation.Quaternion()).Rotator();
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02085B40 (end 0x02085C1B)
// Original VA: 0x0000000142085B40 | File offset: 0x02085140
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execInverseTransformRotation; as TransformRotation with the rotation's scalar inverse (sign-mask xorps).
FRotator UKismetMathLibrary::InverseTransformRotation(const FTransform& T, FRotator Rotation)
{
	return T.InverseTransformRotation(Rotation.Quaternion()).Rotator();
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208CF60 (end 0x0208D17A)
// Original VA: 0x000000014208CF60 | File offset: 0x0208C560
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execRLerp; for the shortest path FQuat::Slerp_NotNormalized (0x011A5A50), two vector
//   normalizations (Float0001, FloatOneHalf) and FQuat::Rotator, else A + Alpha * (B - A).
FRotator UKismetMathLibrary::RLerp(FRotator A, FRotator B, float Alpha, bool bShortestPath)
{
	FRotator DeltaAngle = B - A;

	// if shortest path, we use Quaternion to interpolate instead of using FRotator
	if (bShortestPath)
	{
		FQuat AQuat(A);
		FQuat BQuat(B);

		FQuat Result = FQuat::Slerp(AQuat, BQuat, Alpha);
		Result.Normalize();

		return Result.Rotator();
	}

	return A + Alpha*DeltaAngle;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208CEE0 (end 0x0208CF5B)
// Original VA: 0x000000014208CEE0 | File offset: 0x0208C4E0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execREase; RLerp (0x0208CF60) with EaseAlpha (0x0207AC60).
FRotator UKismetMathLibrary::REase(FRotator A, FRotator B, float Alpha, bool bShortestPath, TEnumAsByte<EEasingFunc::Type> EasingFunc, float BlendExp, int32 Steps)
{
	return RLerp(A, B, EaseAlpha(Alpha, EasingFunc, BlendExp, Steps), bShortestPath);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208F0A0 (end 0x0208F35F)
// Original VA: 0x000000014208F0A0 | File offset: 0x0208E6A0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execRotatorFromAxisAndAngle; the axis's safe normal, FQuat(Axis, Angle) by FMath::SinCos,
//   then FQuat::Rotator (0x011A2050).
FRotator UKismetMathLibrary::RotatorFromAxisAndAngle(FVector Axis, float Angle)
{
	FVector SafeAxis = Axis.GetSafeNormal(); // Make sure axis is unit length
	return FQuat(SafeAxis, FMath::DegreesToRadians(Angle)).Rotator();
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02089FA0 (end 0x0208A2D6)
// Original VA: 0x0000000142089FA0 | File offset: 0x020895A0
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execMakeRotationFromAxes; three FVector::Normalize, the matrix of the axes and
//   FVector::ZeroVector, then FMatrix::Rotator (0x011A1EC0).
FRotator UKismetMathLibrary::MakeRotationFromAxes(FVector Forward, FVector Right, FVector Up)
{
	Forward.Normalize();
	Right.Normalize();
	Up.Normalize();

	FMatrix RotMatrix(Forward, Right, Up, FVector::ZeroVector);

	return RotMatrix.Rotator();
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208EF30 (end 0x0208F09A)
// Original VA: 0x000000014208EF30 | File offset: 0x0208E530
// Recovery: high-confidence inferred (called by its exec thunk) | Matching: see analysis/functions.json
// Evidence: execRotateAngleAxis; the out-of-line FVector::RotateAngleAxis (0x00579DF0) with the axis's
//   safe normal.
FVector  UKismetMathLibrary::RotateAngleAxis(FVector InVect, float AngleDeg, FVector Axis)
{
	return InVect.RotateAngleAxis(AngleDeg, Axis.GetSafeNormal());
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0208D930 (end 0x0208D947)
// Original VA: 0x000000014208D930 | File offset: 0x0208CF30
// Recovery: high-confidence inferred (called by execRandomUnitVector) | Matching: see analysis/functions.json
// Evidence: the native implementation execRandomUnitVector calls (analysis/native-implementations.json),
//   forwarding its return slot to FMath::VRand (0x00AA95F0).
FVector UKismetMathLibrary::RandomUnitVector()
{
	return FMath::VRand();
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x020812F0 (end 0x02081310)
// Original VA: 0x00000001420812F0 | File offset: 0x020808F0
// Recovery: high-confidence inferred (called by execGetForwardVector) | Matching: see analysis/functions.json
// Evidence: the native implementation execGetForwardVector calls: a static function (it swaps the
//   return slot and its by-reference FRotator argument) calling FRotator::Vector (0x011A8000).
FVector UKismetMathLibrary::GetForwardVector(FRotator InRot)
{
	return InRot.Vector();
}
