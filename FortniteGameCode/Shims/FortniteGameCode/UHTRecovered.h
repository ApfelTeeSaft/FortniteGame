// Umbrella header for generated UHT code: codegen parameter types, registration declarations,
// the declarations IMPLEMENT_CLASS uses (UE4.20 ObjectMacros.h, Class.h, UObjectGlobals.h), and
// the generated class declarations. ABI declarations only; not recovered code.
#pragma once

#include "FortniteGameCode/UE4CodeGenRecovered.h"
#include "FortniteGameCode/UObjectRegistrationRecovered.h"
#include "FortniteGameCode/ScriptRecovered.h"

typedef unsigned long long uint64;

// ObjectMacros.h. The full flag sets are not needed: values come from the reference.
enum EClassFlags
{
	CLASS_None = 0x00000000u,
	CLASS_Deprecated = 0x02000000u,
};
enum EClassCastFlags : uint64
{
	CASTCLASS_None = 0x0000000000000000,
};

class FReferenceCollector;
class FObjectInitializer;
struct FVTableHelper;

// Class.h: InternalConstructor<T> and InternalVTableHelperCtorCaller<T> call T's constructors,
// which are not reconstructed; declared only, so their instantiations stay unresolved references.
template<class T> void InternalConstructor(const FObjectInitializer& X);
template<class T> UObject* InternalVTableHelperCtorCaller(FVTableHelper& Helper);

// Class.h: UClass's function-pointer typedefs, added to its declaration in Classes.gen.h.
#define FNGC_EXTRA_MEMBERS_UClass \
	typedef void (*ClassConstructorType)(const FObjectInitializer&); \
	typedef UObject* (*ClassVTableHelperCtorCallerType)(FVTableHelper& Helper); \
	typedef void (*ClassAddReferencedObjectsType)(UObject*, class FReferenceCollector&); \
	typedef UClass* (*StaticClassFunctionType)();

#include "UHT/Classes.gen.h"

void GetPrivateStaticClassBody(
	const TCHAR* PackageName,
	const TCHAR* Name,
	UClass*& ReturnClass,
	void(*RegisterNativeFunc)(),
	uint32 InSize,
	EClassFlags InClassFlags,
	EClassCastFlags InClassCastFlags,
	const TCHAR* InConfigName,
	UClass::ClassConstructorType InClassConstructor,
	UClass::ClassVTableHelperCtorCallerType InClassVTableHelperCtorCaller,
	UClass::ClassAddReferencedObjectsType InClassAddReferencedObjects,
	UClass::StaticClassFunctionType InSuperClassFn,
	UClass::StaticClassFunctionType InWithinClassFn,
	bool bIsDynamic = false);
