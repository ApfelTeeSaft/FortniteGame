// ABI declarations of engine functions referenced by recovered code. Not recovered code.
// Signatures follow the supplied UE4.20.0 Core headers (monolithic build: CORE_API empty).
#pragma once

typedef wchar_t TCHAR;
#ifndef TEXT
#define TEXT(x) L##x
#endif

struct FCommandLine
{
	static const TCHAR* Get();
};

struct FParse
{
	static bool Param(const TCHAR* Stream, const TCHAR* Param);
};
