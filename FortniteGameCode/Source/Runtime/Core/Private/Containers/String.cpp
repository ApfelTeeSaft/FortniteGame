// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: Core. Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/Core/Private/Containers/String.cpp.
// Reconstruction written from image evidence; see analysis/functions.json.
//
// The FString members FDateTime::Parse and FTimespan::Parse call. The object also emits the
// copies of TCString<TCHAR>::Stristr and IsNumeric (Misc/RecoveredCString.h) the reference keeps.

#define FNGC_CORE_MATH_EXTRAS 1   // FDateTime, FColor, FVector4, ... (MathDecls.h)
#define FNGC_STRING_EXTRAS 1      // FString's parse members (ContainersRecovered.h)
#include "FortniteGameCode/MathDecls.h"
#include "FortniteGameCode/ContainersRecovered.h"   // FString
#include "Misc/RecoveredCString.h"                 // FCString

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01103630 (end 0x011038A9)
// Original VA: 0x0000000141103630 | File offset: 0x01102C30
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: FTimespan::Parse (0x011DEC10) calls it twice for Contains("."), Contains(",")
//   (IgnoreCase, FromStart, INDEX_NONE); TCString::Stristr (0x00276040), wcsstr, and the reverse
//   search through ToUpper (0x0110D720).
int32 FString::Find(const TCHAR* SubStr, ESearchCase::Type SearchCase, ESearchDir::Type SearchDir, int32 StartPosition) const
{
	if ( SubStr == nullptr )
	{
		return INDEX_NONE;
	}
	if( SearchDir == ESearchDir::FromStart)
	{
		const TCHAR* Start = **this;
		if ( StartPosition != INDEX_NONE )
		{
			Start += FMath::Clamp(StartPosition, 0, Len() - 1);
		}
		const TCHAR* Tmp = SearchCase == ESearchCase::IgnoreCase
			? FCString::Stristr(Start, SubStr)
			: FCString::Strstr(Start, SubStr);

		return Tmp ? (Tmp-**this) : INDEX_NONE;
	}
	else
	{
		// if ignoring, do a onetime ToUpper on both strings, to avoid ToUppering multiple
		// times in the loop below
		if ( SearchCase == ESearchCase::IgnoreCase)
		{
			return ToUpper().Find(FString(SubStr).ToUpper(), ESearchCase::CaseSensitive, SearchDir, StartPosition);
		}
		else
		{
			const int32 SearchStringLength=FMath::Max(1, FCString::Strlen(SubStr));

			if ( StartPosition == INDEX_NONE || StartPosition >= Len() )
			{
				StartPosition = Len();
			}

			for( int32 i = StartPosition - SearchStringLength; i >= 0; i-- )
			{
				int32 j;
				for( j=0; SubStr[j]; j++ )
				{
					if( (*this)[i+j]!=SubStr[j] )
					{
						break;
					}
				}

				if( !SubStr[j] )
				{
					return i;
				}
			}
			return INDEX_NONE;
		}
	}
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0110D720 (end 0x0110D7C6)
// Original VA: 0x000000014110D720 | File offset: 0x0110CD20
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: FString::Find's reverse case-insensitive search calls it on *this: the copy
//   (TArray<TCHAR>::ResizeForCopy 0x005756A0, memcpy), then ToUpperInline's towupper loop inlined.
FString FString::ToUpper() const &
{
	FString New = *this;
	New.ToUpperInline();
	return New;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0110D7D0 (end 0x0110D860)
// Original VA: 0x000000014110D7D0 | File offset: 0x0110CDD0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: its masked body also matches ToLower() && (0x0110D630); this one calls towupper
//   (import slot 0x04DDC5A4, as Stristr) and sorts after ToUpper() const & (0x0110D720).
FString FString::ToUpper() &&
{
	this->ToUpperInline();
	return MoveTemp(*this);
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0110D860 (end 0x0110D8B6)
// Original VA: 0x000000014110D860 | File offset: 0x0110CE60
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: its masked body also matches ToLowerInline (0x0110D6C0); this one calls towupper
//   (import slot 0x04DDC5A4) and sorts after ToUpper() && (0x0110D7D0).
void FString::ToUpperInline()
{
	const int32 StringLength = Len();
	TCHAR* RawData = Data.GetData();
	for (int32 i = 0; i < StringLength; ++i)
	{
		RawData[i] = FChar::ToUpper(RawData[i]);
	}
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0110A820 (end 0x0110A8BA)
// Original VA: 0x000000014110A820 | File offset: 0x01109E20
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: FTimespan::Parse (0x011DEC10) calls it for StartsWith("-"); _wcsnicmp or wcsncmp
//   by the search case, after wcslen of the prefix.
bool FString::StartsWith(const TCHAR* InPrefix, ESearchCase::Type SearchCase) const
{
	if (SearchCase == ESearchCase::IgnoreCase)
	{
		return InPrefix && *InPrefix && !FCString::Strnicmp(**this, InPrefix, FCString::Strlen(InPrefix));
	}
	else
	{
		return InPrefix && *InPrefix && !FCString::Strncmp(**this, InPrefix, FCString::Strlen(InPrefix));
	}
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01104260 (end 0x01104271), no .pdata (leaf)
// Original VA: 0x0000000141104260 | File offset: 0x01103860
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: FTimespan::Parse (0x011DEC10) calls it for each non-empty token; IsEmpty, then a
//   tail jump to TCString<TCHAR>::IsNumeric (0x007B94B0).
bool FString::IsNumeric() const
{
	if (IsEmpty())
	{
		return 0;
	}

	return FCString::IsNumeric(Data.GetData());
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01105410 (end 0x0110563B)
// Original VA: 0x0000000141105410 | File offset: 0x01104A10
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: FDateTime::Parse (0x011C0050) and FTimespan::Parse (0x011DEC10) call it; Reset, wcsstr,
//   and the two Emplace forms (TArray<FString>::ResizeGrow 0x025605C0; FString(Count, Src) with
//   wcsncpy, FString(Src) with FGenericPlatformString::Memcpy).
int32 FString::ParseIntoArray( TArray<FString>& OutArray, const TCHAR* pchDelim, const bool InCullEmpty ) const
{
	// Make sure the delimit string is not null or empty
	// check(pchDelim) is compiled out.
	OutArray.Reset();
	const TCHAR *Start = Data.GetData();
	const int32 DelimLength = FCString::Strlen(pchDelim);
	// Not the 4.20.0 condition (Start && *Start != TEXT('\0') && DelimLength): the reference does not
	// test the first character (docs/ENGINE_DIFFERENCES.md).
	if (Start && DelimLength)
	{
		while( const TCHAR *At = FCString::Strstr(Start,pchDelim) )
		{
			if (!InCullEmpty || At-Start)
			{
				OutArray.Emplace(At-Start,Start);
			}
			Start = At + DelimLength;
		}
		if (!InCullEmpty || *Start)
		{
			OutArray.Emplace(Start);
		}

	}
	return OutArray.Num();
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01108D80 (end 0x01109047)
// Original VA: 0x0000000141108D80 | File offset: 0x01108380
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: FDateTime::Parse (0x011C0050) calls it for Replace("-", " ") (IgnoreCase); Stristr
//   (0x00276040) or wcsstr, the inlined AppendChars, and the copy for an empty search.
FString FString::Replace(const TCHAR* From, const TCHAR* To, ESearchCase::Type SearchCase) const
{
	// Previous code used to accidentally accept a nullptr replacement string - this is no longer accepted.
	// check(To) is compiled out.

	if (IsEmpty() || !From || !*From)
	{
		return *this;
	}

	// get a pointer into the character data
	const TCHAR* Travel = Data.GetData();

	// precalc the lengths of the replacement strings
	int32 FromLength = FCString::Strlen(From);
	int32 ToLength   = FCString::Strlen(To);

	FString Result;
	while (true)
	{
		// look for From in the remaining string
		const TCHAR* FromLocation = SearchCase == ESearchCase::IgnoreCase ? FCString::Stristr(Travel, From) : FCString::Strstr(Travel, From);
		if (!FromLocation)
			break;

		// copy everything up to FromLocation
		Result.AppendChars(Travel, FromLocation - Travel);

		// copy over the To
		Result.AppendChars(To, ToLength);

		Travel = FromLocation + FromLength;
	}

	// copy anything left over
	Result += Travel;

	return Result;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011092B0 (end 0x011096BE)
// Original VA: 0x00000001411092B0 | File offset: 0x011088B0
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: FDateTime::Parse (0x011C0050) and FTimespan::Parse (0x011DEC10) call it (six calls);
//   the in-place path for equal lengths and the rebuilding path through Contains and +=.
int32 FString::ReplaceInline(const TCHAR* SearchText, const TCHAR* ReplacementText, ESearchCase::Type SearchCase)
{
	int32 ReplacementCount = 0;

	if (Len() > 0
		&& SearchText != nullptr && *SearchText != 0
		&& ReplacementText != nullptr && (SearchCase == ESearchCase::IgnoreCase || FCString::Strcmp(SearchText, ReplacementText) != 0))
	{
		const int32 NumCharsToReplace = FCString::Strlen(SearchText);
		const int32 NumCharsToInsert = FCString::Strlen(ReplacementText);

		if (NumCharsToInsert == NumCharsToReplace)
		{
			TCHAR* Pos = SearchCase == ESearchCase::IgnoreCase ? FCString::Stristr(&(*this)[0], SearchText) : FCString::Strstr(&(*this)[0], SearchText);
			while (Pos != nullptr)
			{
				ReplacementCount++;

				// FCString::Strcpy now inserts a terminating zero so can't use that
				for (int32 i = 0; i < NumCharsToInsert; i++)
				{
					Pos[i] = ReplacementText[i];
				}

				if (Pos + NumCharsToReplace - **this < Len())
				{
					Pos = SearchCase == ESearchCase::IgnoreCase ? FCString::Stristr(Pos + NumCharsToReplace, SearchText) : FCString::Strstr(Pos + NumCharsToReplace, SearchText);
				}
				else
				{
					break;
				}
			}
		}
		else if (Contains(SearchText, SearchCase))
		{
			FString Copy(*this);
			Empty(Len());

			// get a pointer into the character data
			TCHAR* WritePosition = (TCHAR*)Copy.Data.GetData();
			// look for From in the remaining string
			TCHAR* SearchPosition = SearchCase == ESearchCase::IgnoreCase ? FCString::Stristr(WritePosition, SearchText) : FCString::Strstr(WritePosition, SearchText);
			while (SearchPosition != nullptr)
			{
				ReplacementCount++;

				// replace the first letter of the From with 0 so we can do a strcpy (FString +=)
				*SearchPosition = 0;

				// copy everything up to the SearchPosition
				(*this) += WritePosition;

				// copy over the ReplacementText
				(*this) += ReplacementText;

				// restore the letter, just so we don't have 0's in the string
				*SearchPosition = *SearchText;

				WritePosition = SearchPosition + NumCharsToReplace;
				SearchPosition = SearchCase == ESearchCase::IgnoreCase ? FCString::Stristr(WritePosition, SearchText) : FCString::Strstr(WritePosition, SearchText);
			}

			// copy anything left over
			(*this) += WritePosition;
		}
	}

	return ReplacementCount;
}
