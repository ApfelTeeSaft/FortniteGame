// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: Core. Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/Core/Private/Misc/CommandLine.cpp.
// The fatal-log line numbers are part of the machine code (FMsg/FDebug arguments), so each
// UE_CLOG site is placed at its original source line with #line.

#include "FortniteGameCode/EngineDecls.h"

bool FCommandLine::bIsInitialized = false;
TCHAR FCommandLine::CmdLine[FCommandLine::MaxCommandLineSize] = TEXT("");
TCHAR FCommandLine::OriginalCmdLine[FCommandLine::MaxCommandLineSize] = TEXT("");
TCHAR FCommandLine::LoggingCmdLine[FCommandLine::MaxCommandLineSize] = TEXT("");
TCHAR FCommandLine::LoggingOriginalCmdLine[FCommandLine::MaxCommandLineSize] = TEXT("");

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01199E30 (end 0x01199E38, leaf, no .pdata)
// Original VA: 0x0000000141199E30 | File offset: 0x01199430
// Recovery: high-confidence inferred (UE4 name) | Matching: exact (vs decrypted image)
// Evidence: the only movzx eax, byte [bIsInitialized]; ret leaf in decrypted .text. Located by
//   that signature, so the match mainly confirms the location. Outside the .pdata denominator.
bool FCommandLine::IsInitialized()
{
	return bIsInitialized;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01193BC0 (end 0x01193C2C)
// Original VA: 0x0000000141193BC0 | File offset: 0x011931C0
// Recovery: high-confidence inferred (UE4 name) | Matching: relocation-equivalent (literal copies unresolved)
// Evidence: called by SafeTestD3D11CreateDevice and D3D11RHI_ShouldCreateWithD3DDebug to
//   produce FParse::Param's first argument. Fatal log at line 29 (0x1D) with "Unknown" as file.
const TCHAR* FCommandLine::Get()
{
#line 29
	FNGC_CLOG_FATAL(!bIsInitialized, LogInit, TEXT("Attempting to get the command line but it hasn't been initialized yet."));
	return CmdLine;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x01194B20 (end 0x01194B8C)
// Original VA: 0x0000000141194B20 | File offset: 0x01194120
// Recovery: high-confidence inferred (UE4 name) | Matching: relocation-equivalent (literal copies unresolved)
// Evidence: the only 0x6C-byte function equal in every non-relocation byte; line 35 (0x23).
const TCHAR* FCommandLine::GetForLogging()
{
#line 35
	FNGC_CLOG_FATAL(!bIsInitialized, LogInit, TEXT("Attempting to get the command line but it hasn't been initialized yet."));
	return LoggingCmdLine;
}

// Original FortniteClient-Win64-Shipping.exe: not present in the reference image
// Recovery: high-confidence inferred (UE4 name) | Matching: n/a
// Evidence: no function matches even with the line immediate (41) ignored, while the other
//   getters match exactly that way. Most likely discarded by /OPT:REF as unreferenced. Kept
//   because the original translation unit compiled it.
const TCHAR* FCommandLine::GetOriginal()
{
#line 41
	FNGC_CLOG_FATAL(!bIsInitialized, LogInit, TEXT("Attempting to get the command line but it hasn't been initialized yet."));
	return OriginalCmdLine;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x011953C0 (end 0x0119542C)
// Original VA: 0x00000001411953C0 | File offset: 0x011949C0
// Recovery: high-confidence inferred (UE4 name) | Matching: relocation-equivalent (literal copies unresolved)
// Evidence: the only 0x6C-byte function equal in every non-relocation byte; line 47 (0x2F).
const TCHAR* FCommandLine::GetOriginalForLogging()
{
#line 47
	FNGC_CLOG_FATAL(!bIsInitialized, LogInit, TEXT("Attempting to get the command line but it hasn't been initialized yet."));
	return LoggingOriginalCmdLine;
}
