// ABI declarations for UHT-generated reflection code (UE4.20 CoreUObject, UObjectGlobals.h
// UE4CodeGen_Private and ObjectMacros.h / Script.h flag enums). Not recovered code.
#pragma once

#include <stddef.h>

typedef unsigned int uint32;
typedef unsigned short uint16;
typedef int int32;
typedef size_t SIZE_T;
typedef wchar_t TCHAR;
#ifndef TEXT
#define TEXT(x) L##x
#endif

// Complete only so that UPackage* converts to UObject* as in engine code; no layout is implied.
class UObject {};
class UClass;
class UFunction;
class UScriptStruct;
class UPackage : public UObject {};

enum EObjectFlags
{
	RF_NoFlags = 0x00000000,
	RF_Public = 0x00000001,
	RF_MarkAsNative = 0x00000004,
	RF_Transient = 0x00000040,
};

// ENUM_CLASS_FLAGS(EObjectFlags) in UE4.20 (Misc/EnumClassFlags.h; CONSTEXPR is constexpr).
inline constexpr EObjectFlags operator|(EObjectFlags Lhs, EObjectFlags Rhs)
{
	return (EObjectFlags)((__underlying_type(EObjectFlags))Lhs | (__underlying_type(EObjectFlags))Rhs);
}

enum EFunctionFlags : uint32
{
	FUNC_None = 0x00000000,
};

struct FFrame;

// CoreUObject/Public/UObject/CoreNative.h and Script.h (RESULT_DECL is void*const Z_Param__Result).
typedef void (*FNativeFuncPtr)(UObject* Context, FFrame& TheStack, void* const Z_Param__Result);

struct FNameNativePtrPair
{
	const char* NameUTF8;
	FNativeFuncPtr Pointer;
};

struct FNativeFunctionRegistrar
{
	static void RegisterFunctions(class UClass* Class, const FNameNativePtrPair* InArray, int32 NumFunctions);
};

struct FClassFunctionLinkInfo
{
	UFunction* (*CreateFuncPtr)();
	const char* FuncNameUTF8;
};

struct FCppClassTypeInfoStatic
{
	bool bIsAbstract;
};

namespace UE4CodeGen_Private
{
	struct FPropertyParamsBase;
	struct FImplementedInterfaceParams;

	struct FClassParams
	{
		UClass* (*ClassNoRegisterFunc)();
		UObject* (*const *DependencySingletonFuncArray)();
		int32 NumDependencySingletons;
		uint32 ClassFlags;
		const FClassFunctionLinkInfo* FunctionLinkArray;
		int32 NumFunctions;
		const FPropertyParamsBase* const* PropertyArray;
		int32 NumProperties;
		const char* ClassConfigNameUTF8;
		const FCppClassTypeInfoStatic* CppClassInfo;
		const FImplementedInterfaceParams* ImplementedInterfaceArray;
		int32 NumImplementedInterfaces;
	};

	void ConstructUClass(UClass*& OutClass, const FClassParams& Params);

	struct FFunctionParams
	{
		UObject* (*OuterFunc)();
		const char* NameUTF8;
		EObjectFlags ObjectFlags;
		UFunction* (*SuperFunc)();
		EFunctionFlags FunctionFlags;
		SIZE_T StructureSize;
		const FPropertyParamsBase* const* PropertyArray;
		int32 NumProperties;
		uint16 RPCId;
		uint16 RPCResponseId;
	};

	void ConstructUFunction(UFunction*& OutFunction, const FFunctionParams& Params);

	struct FStructParams
	{
		UObject* (*OuterFunc)();
		UScriptStruct* (*SuperFunc)();
		void* (*StructOpsFunc)(); // really returns UScriptStruct::ICppStructOps*
		const char* NameUTF8;
		EObjectFlags ObjectFlags;
		uint32 StructFlags; // EStructFlags
		SIZE_T SizeOf;
		SIZE_T AlignOf;
		const FPropertyParamsBase* const* PropertyArray;
		int32 NumProperties;
	};

	void ConstructUScriptStruct(UScriptStruct*& OutStruct, const FStructParams& Params);
}

// CoreUObject/Public/UObject/Class.h (EStructFlags) and UObjectBase.h (GetStaticStruct).
enum EStructFlags
{
	STRUCT_NoFlags = 0x00000000,
};

UScriptStruct* GetStaticStruct(UScriptStruct* (*InRegister)(), UObject* StructOuter, const TCHAR* StructName, SIZE_T Size, uint32 Crc);
