// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: Core. Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/Core/Private/Windows/WindowsPlatformTime.cpp.
// Reconstruction written from image evidence; see analysis/functions.json.

#define FNGC_CORE_MATH_EXTRAS 1   // FDateTime, FColor, FVector4, ... (MathDecls.h)
#include "FortniteGameCode/MathDecls.h"

// The Win32 declarations used (minwinbase.h, sysinfoapi.h), instead of including Windows.h.
typedef unsigned short WORD;
typedef struct _SYSTEMTIME
{
	WORD wYear;
	WORD wMonth;
	WORD wDayOfWeek;
	WORD wDay;
	WORD wHour;
	WORD wMinute;
	WORD wSecond;
	WORD wMilliseconds;
} SYSTEMTIME, *LPSYSTEMTIME;
extern "C" __declspec(dllimport) void __stdcall GetSystemTime(LPSYSTEMTIME lpSystemTime);
extern "C" __declspec(dllimport) void __stdcall GetLocalTime(LPSYSTEMTIME lpSystemTime);

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01200190 (end 0x01200244)
// Original VA: 0x0000000141200190 | File offset: 0x011FF790
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by FDateTime::Now (0x011BFB90); GetLocalTime into a SYSTEMTIME (/GS cookie).
void FWindowsPlatformTime::SystemTime( int32& Year, int32& Month, int32& DayOfWeek, int32& Day, int32& Hour, int32& Min, int32& Sec, int32& MSec )
{
	SYSTEMTIME st;
	GetLocalTime( &st );

	Year		= st.wYear;
	Month		= st.wMonth;
	DayOfWeek	= st.wDayOfWeek;
	Day			= st.wDay;
	Hour		= st.wHour;
	Min			= st.wMinute;
	Sec			= st.wSecond;
	MSec		= st.wMilliseconds;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01200490 (end 0x01200544)
// Original VA: 0x0000000141200490 | File offset: 0x011FFA90
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by FDateTime::UtcNow (0x011CC290); GetSystemTime into a SYSTEMTIME (/GS cookie).
void FWindowsPlatformTime::UtcTime( int32& Year, int32& Month, int32& DayOfWeek, int32& Day, int32& Hour, int32& Min, int32& Sec, int32& MSec )
{
	SYSTEMTIME st;
	GetSystemTime( &st );

	Year		= st.wYear;
	Month		= st.wMonth;
	DayOfWeek	= st.wDayOfWeek;
	Day			= st.wDay;
	Hour		= st.wHour;
	Min			= st.wMinute;
	Sec			= st.wSecond;
	MSec		= st.wMilliseconds;
}
