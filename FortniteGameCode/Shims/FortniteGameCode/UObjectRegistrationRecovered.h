// ABI declarations for UHT-generated registration code: FName construction, deferred struct
// registration and C++ struct ops (UE4.20 Core NameTypes.h, CoreUObject UObjectBase.h and
// Class.h). Not recovered code. Included through UHTRecovered.h.
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

// UObjectBase.h: deferred enum registration. UEnum itself is declared in Classes.gen.h; its
// ECppForm comes from FNGC_EXTRA_MEMBERS_UEnum below.
class UEnum;
#define FNGC_EXTRA_MEMBERS_UEnum \
	enum class ECppForm \
	{ \
		Regular, \
		Namespaced, \
		EnumClass \
	};
void UObjectCompiledInDeferEnum(UEnum* (*InRegister)(), const TCHAR* PackageName, const FName ObjectName, bool bDynamic, const TCHAR* DynamicPathName);
UEnum* GetStaticEnum(UEnum* (*InRegister)(), UObject* EnumOuter, const TCHAR* EnumName);

struct FCompiledInDeferEnum
{
	FCompiledInDeferEnum(UEnum* (*InRegister)(), const TCHAR* PackageName, const TCHAR* Name, bool bDynamic, const TCHAR* DynamicPackageName, const TCHAR* DynamicPathName)
	{
		if (bDynamic)
		{
			GetConvertedDynamicPackageNameToTypeName().Add(FName(DynamicPackageName), FName(Name));
		}
		UObjectCompiledInDeferEnum(InRegister, PackageName, Name, bDynamic, DynamicPathName);
	}
};

// UObjectGlobals.h (UE4CodeGen_Private), shipping layout without metadata.
typedef long long int64;
typedef unsigned char uint8;
class FText;
namespace UE4CodeGen_Private
{
	enum class EDynamicType
	{
		NotDynamic,
		Dynamic
	};

	struct FEnumeratorParam
	{
		const char* NameUTF8;
		int64 Value;
	};

	struct FEnumParams
	{
		UObject* (*OuterFunc)();
		EDynamicType DynamicType;
		const char* NameUTF8;
		EObjectFlags ObjectFlags;
		FText (*DisplayNameFunc)(int32);
		uint8 CppForm; // this is of type UEnum::ECppForm
		const char* CppTypeUTF8;
		const FEnumeratorParam* EnumeratorParams;
		int32 NumEnumerators;
	};

	void ConstructUEnum(UEnum*& OutEnum, const FEnumParams& Params);

	struct FPackageParams
	{
		const char* NameUTF8;
		uint32 PackageFlags; // EPackageFlags
		uint32 BodiesHash;
		uint32 DeclarationsHash;
		UObject* (*const *SingletonFuncArray)();
		int32 NumSingletons;
	};

	void ConstructUPackage(UPackage*& OutPackage, const FPackageParams& Params);
}

// ObjectMacros.h (EPackageFlags); only the flag init.gen.cpp code names.
enum EPackageFlags
{
	PKG_None = 0x00000000,
	PKG_CompiledIn = 0x00000010,
};

// Class.h: the parts of UScriptStruct that registration code touches, added to its declaration
// in Classes.gen.h. ICppStructOps keeps the engine layout (vtable pointer, Size, Alignment) and
// constructor; the engine's further pure virtual operations (construct, copy, serialize, ...)
// are omitted because no recovered code calls them. The vtable is therefore a stand-in: its
// address is resolved from the reference, never its contents.
#define FNGC_EXTRA_MEMBERS_UScriptStruct \
	struct ICppStructOps \
	{ \
		ICppStructOps(int32 InSize, int32 InAlignment) \
			: Size(InSize) \
			, Alignment(InAlignment) \
		{ \
		} \
		virtual ~ICppStructOps() {} \
	private: \
		int32 Size; \
		int32 Alignment; \
	}; \
	template<class CPPSTRUCT> \
	struct TCppStructOps : public ICppStructOps \
	{ \
		TCppStructOps() \
			: ICppStructOps(sizeof(CPPSTRUCT), alignof(CPPSTRUCT)) \
		{ \
		} \
	}; \
	static void DeferCppStructOps(FName Target, ICppStructOps* InCppStructOps);
