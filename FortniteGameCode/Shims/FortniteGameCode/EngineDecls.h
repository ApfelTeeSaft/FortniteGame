// ABI declarations of engine types and functions referenced by recovered code. Not recovered code.
// Layouts and signatures follow the supplied UE4.20.0 Core headers for a monolithic Win64 Shipping
// build (CORE_API empty, DO_CHECK 0, logging compiled in). Access specifiers are kept because MSVC
// encodes them in the decorated names of static data members.
#pragma once

#include <stddef.h>

typedef wchar_t TCHAR;
typedef wchar_t WIDECHAR;
typedef char ANSICHAR;
typedef signed int int32;
typedef unsigned int uint32;
typedef unsigned char uint8;
typedef size_t SIZE_T;

#ifndef TEXT
#define TEXT(x) L##x
#endif
#define FORCEINLINE __forceinline
#define VARARGS __cdecl

#include "FortniteGameCode/LogVerbosity.h"

class FName
{
public:
	int32 ComparisonIndex;
	uint32 Number;
};

struct FLogCategoryBase
{
	FORCEINLINE FName GetCategoryName() const
	{
		return CategoryFName;
	}

protected:
	ELogVerbosity::Type Verbosity;
	bool DebugBreakOnLog;
	uint8 DefaultVerbosity;
	ELogVerbosity::Type CompileTimeVerbosity;
	FName CategoryFName;
};

template<uint8 InDefaultVerbosity, uint8 InCompileTimeVerbosity>
struct FLogCategory : public FLogCategoryBase
{
	enum
	{
		CompileTimeVerbosity = InCompileTimeVerbosity
	};
};

// DECLARE_LOG_CATEGORY_EXTERN(LogInit, Log, All) in CoreGlobals.h
extern struct FLogCategoryLogInit : public FLogCategory<ELogVerbosity::Log, ELogVerbosity::All>
{
} LogInit;

struct FMsg
{
	static void VARARGS Logf_InternalImpl(const ANSICHAR* File, int32 Line, const FName& Category, ELogVerbosity::Type Verbosity, const TCHAR* Fmt, ...);

	template <typename FmtType, typename... Types>
	static void Logf_Internal(const ANSICHAR* File, int32 Line, const FName& Category, ELogVerbosity::Type Verbosity, const FmtType& Fmt, Types... Args)
	{
		Logf_InternalImpl(File, Line, Category, Verbosity, Fmt, Args...);
	}
};

struct FDebug
{
	static void VARARGS AssertFailed(const ANSICHAR* Expr, const ANSICHAR* File, int32 Line, const TCHAR* Format = TEXT(""), ...);
};

// Shipping expansion of UE_CLOG(Condition, Category, Fatal, Format) in UE4.20 LogMacros.h with
// DO_CHECK 0: UE_LOG_SOURCE_FILE(__FILE__) is "Unknown", there is no IsSuppressed test for Fatal,
// and _DebugBreakAndPromptForRemote() is empty.
#define FNGC_CLOG_FATAL(Condition, CategoryName, Format) \
	{ \
		{ \
			if (Condition) \
			{ \
				{ \
					FMsg::Logf_Internal("Unknown", __LINE__, CategoryName.GetCategoryName(), ELogVerbosity::Fatal, Format); \
					FDebug::AssertFailed("", "Unknown", __LINE__, Format); \
				} \
			} \
		} \
	}

#include "FortniteGameCode/CommandLineDecls.h"
