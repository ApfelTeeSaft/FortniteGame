// ABI declarations of Core's command-line functions (Misc/CommandLine.h, Misc/Parse.h) and the
// GenericPlatformMisc members recovered code uses. Not recovered code. Self-contained, so that
// both EngineDecls.h and the UHT shim headers (UHTRecovered.h) can include it.
#pragma once

#include <stddef.h>

typedef wchar_t TCHAR;
typedef signed int int32;

#ifndef TEXT
#define TEXT(x) L##x
#endif

struct FCommandLine
{
	static const int32 MaxCommandLineSize = 16384;

	static bool IsInitialized();
	static const TCHAR* Get();
	static const TCHAR* GetForLogging();
	static const TCHAR* GetOriginal();
	static const TCHAR* GetOriginalForLogging();

private:
	static bool bIsInitialized;
	static TCHAR CmdLine[MaxCommandLineSize];
	static TCHAR OriginalCmdLine[MaxCommandLineSize];
	static TCHAR LoggingCmdLine[MaxCommandLineSize];
	static TCHAR LoggingOriginalCmdLine[MaxCommandLineSize];
};

struct FParse
{
	static bool Param(const TCHAR* Stream, const TCHAR* Param);
};

// GenericPlatform/GenericPlatformMisc.h (only the members recovered code defines or calls)
struct FGenericPlatformMisc
{
	static bool AllowThreadHeartBeat();
};
