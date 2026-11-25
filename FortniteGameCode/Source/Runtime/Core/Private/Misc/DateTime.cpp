// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: Core. Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/Core/Private/Misc/DateTime.cpp.
// Reconstruction written from image evidence; see analysis/functions.json.

#define FNGC_CORE_MATH_EXTRAS 1   // FDateTime, FColor, FVector4, ... (MathDecls.h)
#define FNGC_STRING_EXTRAS 1      // FString's parse members (ContainersRecovered.h)
#include "FortniteGameCode/MathDecls.h"
#include "FortniteGameCode/ContainersRecovered.h"   // FString
#include "Misc/RecoveredCString.h"                 // FCString::Strtoi

/* FDateTime constants
 *****************************************************************************/

const int32 FDateTime::DaysPerMonth[] = { 0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31 };
const int32 FDateTime::DaysToMonth[] = { 0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365 };

// UE_LOG(LogCore, Fatal, ...) for invalid values is compiled out of the shipping client (no
// Validate call remains).
// Original FortniteClient-Win64-Shipping.exe: RVA 0x011AC210 (end 0x011AC329)
// Original VA: 0x00000001411AC210 | File offset: 0x011AB810
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::MakeDateTime (0x02089C30) and FDateTime::UtcNow/Now/ParseIso8601;
//   the DaysToMonth table (0x03480AD8); first of the FDateTime run (??0).
FDateTime::FDateTime(int32 Year, int32 Month, int32 Day, int32 Hour, int32 Minute, int32 Second, int32 Millisecond)
{
	int32 TotalDays = 0;

	if ((Month > 2) && IsLeapYear(Year))
	{
		++TotalDays;
	}

	--Year;											// the current year is not a full year yet
	--Month;										// the current month is not a full month yet

	TotalDays += Year * 365;
	TotalDays += Year / 4;							// leap year day every four years...
	TotalDays -= Year / 100;						// ...except every 100 years...
	TotalDays += Year / 400;						// ...but also every 400 years
	TotalDays += DaysToMonth[Month];				// days in this year up to last month
	TotalDays += Day - 1;							// days in this month minus today

	Ticks = TotalDays * ETimespan::TicksPerDay
		+ Hour * ETimespan::TicksPerHour
		+ Minute * ETimespan::TicksPerMinute
		+ Second * ETimespan::TicksPerSecond
		+ Millisecond * ETimespan::TicksPerMillisecond;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011B86F0 (end 0x011B883F)
// Original VA: 0x00000001411B86F0 | File offset: 0x011B7CF0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: Fliegel-van Flandern date from GetJulianDay; sorts before GetDay (0x011B8840).
void FDateTime::GetDate(int32& OutYear, int32& OutMonth, int32& OutDay) const
{
	// Based on FORTRAN code in:
	// Fliegel, H. F. and van Flandern, T. C.,
	// Communications of the ACM, Vol. 11, No. 10 (October 1968).

	int32 i, j, k, l, n;

	l = FMath::FloorToInt(GetJulianDay() + 0.5) + 68569;
	n = 4 * l / 146097;
	l = l - (146097 * n + 3) / 4;
	i = 4000 * (l + 1) / 1461001;
	l = l - 1461 * i / 4 + 31;
	j = 80 * l / 2447;
	k = l - 2447 * j / 80;
	l = j / 11;
	j = j + 2 - 12 * l;
	i = 100 * (n - 49) + i + l;

	OutYear = i;
	OutMonth = j;
	OutDay = k;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011B8840 (end 0x011B8928), no .pdata (leaf)
// Original VA: 0x00000001411B8840 | File offset: 0x011B7E40
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::BreakDateTime (0x02072380) and execGetDay; GetDate inlined.
int32 FDateTime::GetDay() const
{
	int32 Year, Month, Day;
	GetDate(Year, Month, Day);

	return Day;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011B8930 (end 0x011B896A), no .pdata (leaf)
// Original VA: 0x00000001411B8930 | File offset: 0x011B7F30
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: (Ticks / TicksPerDay) % 7; sorts between GetDay and GetDayOfYear.
EDayOfWeek FDateTime::GetDayOfWeek() const
{
	// January 1, 0001 was a Monday
	return static_cast<EDayOfWeek>((Ticks / ETimespan::TicksPerDay) % 7);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011B8970 (end 0x011B8B1F)
// Original VA: 0x00000001411B8970 | File offset: 0x011B7F70
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by execGetDayOfYear; GetDate inlined, then DaysInMonth (0x011B30C0) per month.
int32 FDateTime::GetDayOfYear() const
{
	int32 Year, Month, Day;
	GetDate(Year, Month, Day);

	for (int32 CurrentMonth = 1; CurrentMonth < Month; ++CurrentMonth)
	{
		Day += DaysInMonth(Year, CurrentMonth);
	}

	return Day;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011B96B0 (end 0x011B9705), no .pdata (leaf)
// Original VA: 0x00000001411B96B0 | File offset: 0x011B8CB0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by execGetHour12; (Ticks / TicksPerHour) % 24 mapped to 1..12.
int32 FDateTime::GetHour12() const
{
	int32 Hour = GetHour();

	if (Hour < 1)
	{
		return 12;
	}

	if (Hour > 12)
	{
		return (Hour - 12);
	}

	return Hour;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011B99A0 (end 0x011B9A82), no .pdata (leaf)
// Original VA: 0x00000001411B99A0 | File offset: 0x011B8FA0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::BreakDateTime (0x02072380); GetDate inlined.
int32 FDateTime::GetMonth() const
{
	int32 Year, Month, Day;
	GetDate(Year, Month, Day);

	return Month;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011BA970 (end 0x011BAA50), no .pdata (leaf)
// Original VA: 0x00000001411BA970 | File offset: 0x011B9F70
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::BreakDateTime (0x02072380); GetDate inlined.
int32 FDateTime::GetYear() const
{
	int32 Year, Month, Day;
	GetDate(Year, Month, Day);

	return Year;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011C8860 (end 0x011C887E)
// Original VA: 0x00000001411C8860 | File offset: 0x011C7E60
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: tail of ToString(TEXT("%Y-%m-%dT%H:%M:%S.%sZ")) (0x011C8880); sorts before ToString.
FString FDateTime::ToIso8601() const
{
	return ToString(TEXT("%Y-%m-%dT%H:%M:%S.%sZ"));
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011C9270 (end 0x011C928E)
// Original VA: 0x00000001411C9270 | File offset: 0x011C8870
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: ToString(TEXT("%Y.%m.%d-%H.%M.%S")) through the formatting overload (0x011C8880).
FString FDateTime::ToString() const
{
	return ToString(TEXT("%Y.%m.%d-%H.%M.%S"));
}

/* FDateTime static interface
 *****************************************************************************/

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011B30C0 (end 0x011B3129), no .pdata (leaf)
// Original VA: 0x00000001411B30C0 | File offset: 0x011B26C0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by FDateTime::Validate (0x011CC310) and GetDayOfYear; the DaysPerMonth table.
int32 FDateTime::DaysInMonth(int32 Year, int32 Month)
{
	// check((Month >= 1) && (Month <= 12)) is compiled out.

	if ((Month == 2) && IsLeapYear(Year))
	{
		return 29;
	}

	return DaysPerMonth[Month];
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011B3130 (end 0x011B318A), no .pdata (leaf)
// Original VA: 0x00000001411B3130 | File offset: 0x011B2730
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by execDaysInYear; IsLeapYear inlined; sorts after DaysInMonth.
int32 FDateTime::DaysInYear(int32 Year)
{
	if (IsLeapYear(Year))
	{
		return 366;
	}

	return 365;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011BC210 (end 0x011BC26A), no .pdata (leaf)
// Original VA: 0x00000001411BC210 | File offset: 0x011BB810
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by execIsLeapYear; sorts between GetYear and Parse.
bool FDateTime::IsLeapYear(int32 Year)
{
	if ((Year % 4) == 0)
	{
		return (((Year % 100) != 0) || ((Year % 400) == 0));
	}

	return false;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011BFB90 (end 0x011BFC0F)
// Original VA: 0x00000001411BFB90 | File offset: 0x011BF190
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: FPlatformTime::SystemTime (0x01200190), then the constructor; sorts before Param/Parse.
FDateTime FDateTime::Now()
{
	int32 Year, Month, Day, DayOfWeek;
	int32 Hour, Minute, Second, Millisecond;

	FPlatformTime::SystemTime(Year, Month, DayOfWeek, Day, Hour, Minute, Second, Millisecond);

	return FDateTime(Year, Month, Day, Hour, Minute, Second, Millisecond);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011C0050 (end 0x011C02E4)
// Original VA: 0x00000001411C0050 | File offset: 0x011BF650
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: the target execDateTimeFromString (0x0243CC30) calls (KismetMathLibrary.inl's DateTimeFromString
//   inlined); FString::Replace (0x01108D80), ReplaceInline (0x011092B0) twice, ParseIntoArray (0x01105410),
//   _wtoi through the import table, Validate inlined (DaysInMonth 0x011B30C0) and the constructor (0x011AC210).
bool FDateTime::Parse(const FString& DateTimeString, FDateTime& OutDateTime)
{
	// first replace -, : and . with space
	FString FixedString = DateTimeString.Replace(TEXT("-"), TEXT(" "));
	FixedString.ReplaceInline(TEXT(":"), TEXT(" "), ESearchCase::CaseSensitive);
	FixedString.ReplaceInline(TEXT("."), TEXT(" "), ESearchCase::CaseSensitive);

	// split up on a single delimiter
	TArray<FString> Tokens;
	FixedString.ParseIntoArray(Tokens, TEXT(" "), true);

	// make sure it parsed it properly (within reason)
	if ((Tokens.Num() < 6) || (Tokens.Num() > 7))
	{
		return false;
	}

	const int32 Year = FCString::Atoi(*Tokens[0]);
	const int32 Month = FCString::Atoi(*Tokens[1]);
	const int32 Day = FCString::Atoi(*Tokens[2]);
	const int32 Hour = FCString::Atoi(*Tokens[3]);
	const int32 Minute = FCString::Atoi(*Tokens[4]);
	const int32 Second = FCString::Atoi(*Tokens[5]);
	const int32 Millisecond = Tokens.Num() > 6 ? FCString::Atoi(*Tokens[6]) : 0;

	if (!Validate(Year, Month, Day, Hour, Minute, Second, Millisecond))
	{
		return false;
	}

	// convert the tokens to numbers
	OutDateTime.Ticks = FDateTime(Year, Month, Day, Hour, Minute, Second, Millisecond).Ticks;

	return true;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011C30B0 (end 0x011C3395)
// Original VA: 0x00000001411C30B0 | File offset: 0x011C26B0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by execDateTimeFromIsoString; wcstoul (FCString::Strtoi) per field, Validate,
//   the constructor and FTimespan::FromMinutes inlined.
bool FDateTime::ParseIso8601(const TCHAR* DateTimeString, FDateTime& OutDateTime)
{
	// DateOnly: YYYY-MM-DD
	// DateTime: YYYY-mm-ddTHH:MM:SS(.ssss)(Z|+th:tm|-th:tm)

	const TCHAR* Ptr = DateTimeString;
	TCHAR* Next = nullptr;

	int32 Year = 0, Month = 0, Day = 0;
	int32 Hour = 0, Minute = 0, Second = 0, Millisecond = 0;
	int32 TzHour = 0, TzMinute = 0;

	// get date
	Year = FCString::Strtoi(Ptr, &Next, 10);

	if ((Next <= Ptr) || (*Next == TCHAR('\0')))
	{
		return false;
	}

	Ptr = Next + 1; // skip separator
	Month = FCString::Strtoi(Ptr, &Next, 10);

	if ((Next <= Ptr) || (*Next == TCHAR('\0')))
	{
		return false;
	}

	Ptr = Next + 1; // skip separator
	Day = FCString::Strtoi(Ptr, &Next, 10);

	if (Next <= Ptr)
	{
		return false;
	}

	// check whether this is date and time
	if (*Next == TCHAR('T'))
	{
		Ptr = Next + 1;

		// parse time
		Hour = FCString::Strtoi(Ptr, &Next, 10);

		if ((Next <= Ptr) || (*Next == TCHAR('\0')))
		{
			return false;
		}

		Ptr = Next + 1; // skip separator
		Minute = FCString::Strtoi(Ptr, &Next, 10);

		if ((Next <= Ptr) || (*Next == TCHAR('\0')))
		{
			return false;
		}

		Ptr = Next + 1; // skip separator
		Second = FCString::Strtoi(Ptr, &Next, 10);

		if (Next <= Ptr)
		{
			return false;
		}

		// check for milliseconds
		if (*Next == TCHAR('.'))
		{
			Ptr = Next + 1;
			Millisecond = FCString::Strtoi(Ptr, &Next, 10);

			// should be no more than 3 digits
			if ((Next <= Ptr) || (Next > Ptr + 3))
			{
				return false;
			}

			for (int32 Digits = Next - Ptr; Digits < 3; ++Digits)
			{
				Millisecond *= 10;
			}
		}

		// see if the timezone offset is included
		if (*Next == TCHAR('+') || *Next == TCHAR('-'))
		{
			// include the separator since it's + or -
			Ptr = Next;

			// parse the timezone offset
			TzHour = FCString::Strtoi(Ptr, &Next, 10);

			if ((Next <= Ptr) || (*Next == TCHAR('\0')))
			{
				return false;
			}

			Ptr = Next + 1; // skip separator
			TzMinute = FCString::Strtoi(Ptr, &Next, 10);

			if (Next <= Ptr)
			{
				return false;
			}
		}
		else if ((*Next != TCHAR('\0')) && (*Next != TCHAR('Z')))
		{
			return false;
		}
	}
	else if (*Next != TCHAR('\0'))
	{
		return false;
	}

	if (!Validate(Year, Month, Day, Hour, Minute, Second, Millisecond))
	{
		return false;
	}

	FDateTime Final(Year, Month, Day, Hour, Minute, Second, Millisecond);

	// adjust for the timezone (bringing the DateTime into UTC)
	int32 TzOffsetMinutes = (TzHour < 0) ? TzHour * 60 - TzMinute : TzHour * 60 + TzMinute;
	Final -= FTimespan::FromMinutes(TzOffsetMinutes);
	OutDateTime = Final;

	return true;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011CC290 (end 0x011CC30F)
// Original VA: 0x00000001411CC290 | File offset: 0x011CB890
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by execUtcNow; FPlatformTime::UtcTime (0x01200490), then the constructor.
FDateTime FDateTime::UtcNow()
{
	int32 Year, Month, Day, DayOfWeek;
	int32 Hour, Minute, Second, Millisecond;

	FPlatformTime::UtcTime(Year, Month, DayOfWeek, Day, Hour, Minute, Second, Millisecond);

	return FDateTime(Year, Month, Day, Hour, Minute, Second, Millisecond);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011CC310 (end 0x011CC377)
// Original VA: 0x00000001411CC310 | File offset: 0x011CB910
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by UKismetMathLibrary::MakeDateTime (0x02089C30); DaysInMonth; sorts after UtcNow.
bool FDateTime::Validate(int32 Year, int32 Month, int32 Day, int32 Hour, int32 Minute, int32 Second, int32 Millisecond)
{
	return (Year >= 1) && (Year <= 9999) &&
		(Month >= 1) && (Month <= 12) &&
		(Day >= 1) && (Day <= DaysInMonth(Year, Month)) &&
		(Hour >= 0) && (Hour <= 23) &&
		(Minute >= 0) && (Minute <= 59) &&
		(Second >= 0) && (Second <= 59) &&
		(Millisecond >= 0) && (Millisecond <= 999);
}
