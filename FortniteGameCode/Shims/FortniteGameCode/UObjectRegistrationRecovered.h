// ABI declarations for UHT-generated registration code: FName construction, deferred struct
// registration and C++ struct ops (UE4.20 Core NameTypes.h, CoreUObject UObjectBase.h and
// Class.h). Not recovered code. Included only by generated USTRUCT translation units.
//
// FName here has the engine's shipping layout (ComparisonIndex, Number: 8 bytes, passed by value
// in a register) and its out-of-line TCHAR constructor. EngineDecls.h declares a layout-only
// FName for the hand-recovered Core sources; the two headers are never combined.
#pragma once

#include "FortniteGameCode/UE4CodeGenRecovered.h"

enum EFindName
{
	FNAME_Find,
	FNAME_Add,
	FNAME_Replace_Not_Safe_For_Threading,
};

class FName
{
public:
	FName(const TCHAR* Name, EFindName FindType = FNAME_Add);

private:
	int32 ComparisonIndex;
	int32 Number;
};

// UObjectBase.h
void UObjectCompiledInDeferStruct(UScriptStruct* (*InRegister)(), const TCHAR* PackageName, const FName ObjectName, bool bDynamic, const TCHAR* DynamicPathName);

// Stand-in for TMap<FName, FName>& GetConvertedDynamicPackageNameToTypeName(); only reached for
// dynamic (Blueprint-converted) types, which compiled-in structs never are.
struct FDynamicPackageNameToTypeNameRecovered
{
	void Add(const FName& Key, const FName& Value);
};
FDynamicPackageNameToTypeNameRecovered& GetConvertedDynamicPackageNameToTypeName();

struct FCompiledInDeferStruct
{
	FCompiledInDeferStruct(UScriptStruct* (*InRegister)(), const TCHAR* PackageName, const TCHAR* Name, bool bDynamic, const TCHAR* DynamicPackageName, const TCHAR* DynamicPathName)
	{
		if (bDynamic)
		{
			GetConvertedDynamicPackageNameToTypeName().Add(FName(DynamicPackageName), FName(Name));
		}
		UObjectCompiledInDeferStruct(InRegister, PackageName, Name, bDynamic, DynamicPathName);
	}
};

// Class.h: the parts of UScriptStruct that registration code touches. ICppStructOps keeps the
// engine layout (vtable pointer, Size, Alignment) and constructor; the engine's further pure
// virtual operations (construct, copy, serialize, ...) are omitted because no recovered code
// calls them. The vtable is therefore a stand-in: its address is resolved from the reference,
// never its contents.
class UScriptStruct : public UObject
{
public:
	struct ICppStructOps
	{
		ICppStructOps(int32 InSize, int32 InAlignment)
			: Size(InSize)
			, Alignment(InAlignment)
		{
		}
		virtual ~ICppStructOps() {}

	private:
		int32 Size;
		int32 Alignment;
	};

	template<class CPPSTRUCT>
	struct TCppStructOps : public ICppStructOps
	{
		TCppStructOps()
			: ICppStructOps(sizeof(CPPSTRUCT), alignof(CPPSTRUCT))
		{
		}
	};

	static void DeferCppStructOps(FName Target, ICppStructOps* InCppStructOps);
};
