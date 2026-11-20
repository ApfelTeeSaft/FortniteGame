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
};

template <typename T>
struct TChar
{
	typedef T CharType;
	static inline bool IsWhitespace(CharType Char);
};

template <> inline bool TChar<WIDECHAR>::IsWhitespace(CharType Char) { return ::iswspace(Char) != 0; }

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

typedef TCString<TCHAR> FCString;
