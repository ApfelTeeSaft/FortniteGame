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
class UObject;
struct FVTableHelper;

// UObjectGlobals.h: FObjectInitializer's first member is the object under construction.
class FObjectInitializer
{
	UObject* Obj;
public:
	UObject* GetObj() const { return Obj; }
};

// ObjectMacros.h: DECLARE_CLASS's placement allocation (a class member there).
enum EInternal { EC_InternalUseOnlyConstructor };
inline void* operator new(const size_t InSize, EInternal* InMem) { return (void*)InMem; }

// Class.h. InternalConstructor<T> calls T's __DefaultConstructor, which Classes.gen.h declares
// with the constructor form the reference uses; the constructors themselves are not
// reconstructed. Without WITH_HOT_RELOAD, InternalVTableHelperCtorCaller<T> returns nullptr.
// Classes.gen.h declares the instances that differ as explicit specializations.
template<class T> void InternalConstructor(const FObjectInitializer& X) { T::__DefaultConstructor(X); }
template<class T> UObject* InternalVTableHelperCtorCaller(FVTableHelper& Helper) { return nullptr; }

// Class.h: UClass's function-pointer typedefs, added to its declaration in Classes.gen.h.
#define FNGC_EXTRA_MEMBERS_UClass \
	typedef void (*ClassConstructorType)(const FObjectInitializer&); \
	typedef UObject* (*ClassVTableHelperCtorCallerType)(FVTableHelper& Helper); \
	typedef void (*ClassAddReferencedObjectsType)(UObject*, class FReferenceCollector&); \
	typedef UClass* (*StaticClassFunctionType)();

// UObject/UnrealType.h: declared only; the reference's instances are out of line.
template<typename T> T* FindFieldChecked(const UStruct* Owner, FName FieldName);

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
