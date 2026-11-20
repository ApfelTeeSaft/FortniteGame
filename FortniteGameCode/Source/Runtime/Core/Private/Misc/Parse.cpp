// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: Core. Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/Core/Private/Misc/Parse.cpp.

#include "FortniteGameCode/EngineDecls.h"
#include "Misc/RecoveredCString.h"

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011BFED0 (end 0x011C0048)
// Original VA: 0x00000001411BFED0 | File offset: 0x011BF4D0
// Recovery: high-confidence inferred (UE4 name) | Matching: exact (vs decrypted image; imports resolved by name)
// Evidence: callee of SafeTestD3D11CreateDevice / D3D11RHI_ShouldCreateWithD3DDebug with
//   (FCommandLine::Get(), L"d3ddebug"). The body inlines TCString::Strifind with quote skipping
//   (_wcsnicmp import), the wcslen loop and TChar::IsWhitespace (iswspace import).
bool FParse::Param(const TCHAR* Stream, const TCHAR* Param)
{
	const TCHAR* Start = Stream;
	if (*Stream)
	{
		while ((Start = FCString::Strifind(Start, Param, true)) != NULL)
		{
			if (Start > Stream && (Start[-1] == '-' || Start[-1] == '/') &&
				(Stream > (Start - 2) || FChar::IsWhitespace(Start[-2])))
			{
				const TCHAR* End = Start + FCString::Strlen(Param);
				if (End == NULL || *End == 0 || FChar::IsWhitespace(*End))
				{
					return true;
				}
			}

			Start++;
		}
	}
	return false;
}
