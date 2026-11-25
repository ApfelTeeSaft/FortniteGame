// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: Core. Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/Core/Private/Misc/Timespan.cpp.
// Reconstruction written from image evidence; see analysis/functions.json.

#define FNGC_CORE_MATH_EXTRAS 1   // FDateTime, FColor, FVector4, ... (MathDecls.h)
#define FNGC_STRING_EXTRAS 1      // FString's parse members (ContainersRecovered.h)
#include "FortniteGameCode/MathDecls.h"
#include "FortniteGameCode/ContainersRecovered.h"   // FString
#include "Misc/RecoveredCString.h"                 // FCString::Atoi

/* FTimespan implementation
 *****************************************************************************/

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011DEC10 (end 0x011DF1BA)
// Original VA: 0x00000001411DEC10 | File offset: 0x011DE210
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: the target execTimespanFromString (0x02450E00) calls; FString::Find (0x01103630) twice for Contains,
//   ReplaceInline (0x011092B0) four times, StartsWith (0x0110A820), ParseIntoArray (0x01105410), IsNumeric
//   (0x01104260), the inlined AddDefaulted/InsertDefaulted (TArray<FString>::ResizeGrow 0x025605C0, memmove,
//   memset), Left and the fraction padding, then Assign inlined.
bool FTimespan::Parse(const FString& TimespanString, FTimespan& OutTimespan)
{
	// @todo gmp: implement stricter FTimespan parsing; this implementation is too forgiving

	// get string tokens
	const bool HasFractional = TimespanString.Contains(TEXT(".")) || TimespanString.Contains(TEXT(","));
	FString TokenString = TimespanString;
	TokenString.ReplaceInline(TEXT("."), TEXT(":"));
	TokenString.ReplaceInline(TEXT(","), TEXT(":"));

	const bool Negative = TokenString.StartsWith(TEXT("-"));
	TokenString.ReplaceInline(TEXT("-"), TEXT(":"));
	TokenString.ReplaceInline(TEXT("+"), TEXT(":"));

	TArray<FString> Tokens;
	TokenString.ParseIntoArray(Tokens, TEXT(":"), true);

	if (!HasFractional)
	{
		Tokens.AddDefaulted();
	}

	// poor man's token verification
	for (const FString& Token : Tokens)
	{
		if (!Token.IsEmpty() && !Token.IsNumeric())
		{
			return false;
		}
	}

	// add missing tokens
	if (Tokens.Num() < 5)
	{
		Tokens.InsertDefaulted(0, 5 - Tokens.Num());
	}
	else if (Tokens.Num() > 5)
	{
		return false;
	}

	// pad fractional token with zeros
	if (HasFractional)
	{
		const int32 FractionalLen = Tokens[4].Len();

		if (FractionalLen > 9)
		{
			Tokens[4] = Tokens[4].Left(9);
		}
		else if (FractionalLen < 9)
		{
			Tokens[4] += FString(TEXT("000000000")).Left(9 - FractionalLen);
		}
	}

	const int32 Days = FCString::Atoi(*Tokens[0]);
	const int32 Hours = FCString::Atoi(*Tokens[1]);
	const int32 Minutes = FCString::Atoi(*Tokens[2]);
	const int32 Seconds = FCString::Atoi(*Tokens[3]);
	const int32 FractionNano = FCString::Atoi(*Tokens[4]);

	if ((Days > (ETimespan::MaxTicks / ETimespan::TicksPerDay) - 1))
	{
		return false;
	}

	if ((Hours > 23) || (Minutes > 59) || (Seconds > 59) || (FractionNano > 999999999))
	{
		return false;
	}

	OutTimespan.Assign(Days, Hours, Minutes, Seconds, FractionNano);

	if (Negative)
	{
		OutTimespan.Ticks *= -1;
	}

	return true;
}

// check((TotalTicks >= ETimespan::MinTicks) && (TotalTicks <= ETimespan::MaxTicks)) is compiled out.
// Original FortniteClient-Win64-Shipping.exe: RVA 0x011D5640 (end 0x011D5695), no .pdata (leaf)
// Original VA: 0x00000001411D5640 | File offset: 0x011D4C40
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by FTimespan's constructor, inlined in UKismetMathLibrary::MakeTimespan (0x0208A5B0) and
//   MakeTimespan2 (0x0208A580); v140 folds the sum into (((Days * 24 + Hours) * 60 + Minutes) * 60
//   + Seconds) * TicksPerSecond.
void FTimespan::Assign(int32 Days, int32 Hours, int32 Minutes, int32 Seconds, int32 FractionNano)
{
	int64 TotalTicks = 0;

	TotalTicks += Days * ETimespan::TicksPerDay;
	TotalTicks += Hours * ETimespan::TicksPerHour;
	TotalTicks += Minutes * ETimespan::TicksPerMinute;
	TotalTicks += Seconds * ETimespan::TicksPerSecond;
	TotalTicks += FractionNano / ETimespan::NanosecondsPerTick;

	Ticks = TotalTicks;
}
