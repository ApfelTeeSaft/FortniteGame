// Recovered inline string helpers of Core (UE4.20 Misc/CString.h, Misc/Char.h and
// GenericPlatform/MicrosoftPlatformString.h, WIDECHAR only). These helpers have no standalone
// copies to annotate with an RVA: the reference inlines them into their callers (e.g.
// FParse::Param at RVA 0x011BFED0). Only what recovered functions use is reconstructed.
#pragma once

#include <wchar.h>
#include <wctype.h>

#include "FortniteGameCode/EngineDecls.h"

struct FRecoveredPlatformString
{
	static FORCEINLINE int32 Strnicmp(const WIDECHAR* String1, const WIDECHAR* String2, SIZE_T Count)
	{
		return _wcsnicmp(String1, String2, Count);
	}

	static FORCEINLINE int32 Strlen(const WIDECHAR* String)
	{
		return (int32)wcslen(String);
	}

	static FORCEINLINE int32 Strtoi(const WIDECHAR* Start, WIDECHAR** End, int32 Base)
	{
		return wcstoul(Start, End, Base);   // _tcstoul
	}

	static FORCEINLINE int32 Atoi(const WIDECHAR* String)
	{
		return _wtoi(String);   // _tstoi
	}

	static FORCEINLINE int32 Strcmp(const WIDECHAR* String1, const WIDECHAR* String2)
	{
		return wcscmp(String1, String2);   // _tcscmp
	}

	static FORCEINLINE int32 Strncmp(const WIDECHAR* String1, const WIDECHAR* String2, SIZE_T Count)
	{
		return wcsncmp(String1, String2, Count);   // _tcsncmp
	}

	static FORCEINLINE const WIDECHAR* Strstr(const WIDECHAR* String, const WIDECHAR* Find)
	{
		return wcsstr(String, Find);   // _tcsstr
	}
};

template <typename T>
struct TChar
{
	typedef T CharType;
	static inline bool IsWhitespace(CharType Char);
	static inline CharType ToUpper(CharType Char);
	static inline bool IsDigit(CharType Char);
};

template <> inline bool TChar<WIDECHAR>::IsWhitespace(CharType Char) { return ::iswspace(Char) != 0; }
template <> inline TChar<WIDECHAR>::CharType TChar<WIDECHAR>::ToUpper(CharType In) { return ::towupper(In); }
template <> inline bool TChar<WIDECHAR>::IsDigit(CharType Char) { return ::iswdigit(Char) != 0; }

typedef TChar<TCHAR> FChar;

template <typename T>
struct TCString
{
	typedef T CharType;

	static FORCEINLINE int32 Strnicmp(const CharType* String1, const CharType* String2, SIZE_T Count)
	{
		return FRecoveredPlatformString::Strnicmp(String1, String2, Count);
	}

	static FORCEINLINE int32 Strlen(const CharType* String)
	{
		return FRecoveredPlatformString::Strlen(String);
	}

	static FORCEINLINE int32 Strtoi(const CharType* Start, CharType** End, int32 Base)
	{
		return FRecoveredPlatformString::Strtoi(Start, End, Base);
	}

	static FORCEINLINE int32 Atoi(const CharType* String)
	{
		return FRecoveredPlatformString::Atoi(String);
	}

	static FORCEINLINE int32 Strcmp(const CharType* String1, const CharType* String2)
	{
		return FRecoveredPlatformString::Strcmp(String1, String2);
	}

	static FORCEINLINE int32 Strncmp(const CharType* String1, const CharType* String2, SIZE_T Count)
	{
		return FRecoveredPlatformString::Strncmp(String1, String2, Count);
	}

	static FORCEINLINE const CharType* Strstr(const CharType* String, const CharType* Find)
	{
		return FRecoveredPlatformString::Strstr(String, Find);
	}

	static FORCEINLINE CharType* Strstr(CharType* String, const CharType* Find)
	{
		return (CharType*)FRecoveredPlatformString::Strstr(String, Find);
	}

	static const CharType* Stristr(const CharType* Str, const CharType* Find);
	static CharType* Stristr(CharType* Str, const CharType* Find) { return (CharType*)Stristr((const CharType*)Str, Find); }

	/**
	 * Returns whether this string contains only numeric characters.
	 * @param Str - string that will be checked
	 **/
	static bool IsNumeric(const CharType* Str)
	{
		if (*Str == '-' || *Str == '+')
		{
			Str++;
		}

		bool bHasDot = false;
		while (*Str != '\0')
		{
			if (*Str == '.')
			{
				if (bHasDot)
				{
					return false;
				}
				bHasDot = true;
			}
			else if (!TChar<CharType>::IsDigit(*Str))   // FChar::IsDigit
			{
				return false;
			}

			++Str;
		}

		return true;
	}

	static const CharType* Strifind(const CharType* Str, const CharType* Find, bool bSkipQuotedChars = false);
};

// The engine's c += 'A' - 'a' narrows an int to wchar_t (C4245 at /W4); keep the expression.
#pragma warning(push)
#pragma warning(disable : 4245)

// Case-insensitive search for Find in Str. Matches must not follow an alphanumeric
// character, and with bSkipQuotedChars nothing inside "..." matches.
template <typename T>
const typename TCString<T>::CharType* TCString<T>::Strifind(const CharType* Str, const CharType* Find, bool bSkipQuotedChars)
{
	if (Find == NULL || Str == NULL)
	{
		return NULL;
	}

	bool Alnum = 0;
	CharType f = (*Find < 'a' || *Find > 'z') ? (*Find) : (CharType)(*Find + 'A' - 'a');
	int32 Length = Strlen(Find++) - 1;
	CharType c = *Str++;

	if (bSkipQuotedChars)
	{
		bool bInQuotedStr = false;
		while (c)
		{
			if (c >= 'a' && c <= 'z')
			{
				c += 'A' - 'a';
			}
			if (!bInQuotedStr && !Alnum && c == f && !Strnicmp(Str, Find, Length))
			{
				return Str - 1;
			}
			Alnum = (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9');
			if (c == '"')
			{
				bInQuotedStr = !bInQuotedStr;
			}
			c = *Str++;
		}
	}
	else
	{
		while (c)
		{
			if (c >= 'a' && c <= 'z')
			{
				c += 'A' - 'a';
			}
			if (!Alnum && c == f && !Strnicmp(Str, Find, Length))
			{
				return Str - 1;
			}
			Alnum = (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9');
			c = *Str++;
		}
	}
	return NULL;
}

#pragma warning(pop)

template <typename T>
const typename TCString<T>::CharType* TCString<T>::Stristr(const CharType* Str, const CharType* Find)
{
	// both strings must be valid
	if( Find == NULL || Str == NULL )
	{
		return NULL;
	}

	// get upper-case first letter of the find string (to reduce the number of full strnicmps)
	CharType FindInitial = TChar<CharType>::ToUpper(*Find);
	// get length of find string, and increment past first letter
	int32   Length = Strlen(Find++) - 1;
	// get the first letter of the search string, and increment past it
	CharType StrChar = *Str++;
	// while we aren't at end of string...
	while (StrChar)
	{
		// make sure it's upper-case
		StrChar = TChar<CharType>::ToUpper(StrChar);
		// if it matches the first letter of the find string, do a case-insensitive string compare for the length of the find string
		if (StrChar == FindInitial && !Strnicmp(Str, Find, Length))
		{
			// if we found the string, then return a pointer to the beginning of it in the search string
			return Str-1;
		}
		// go to next letter
		StrChar = *Str++;
	}

	// if nothing was found, return NULL
	return NULL;
}

typedef TCString<TCHAR> FCString;
