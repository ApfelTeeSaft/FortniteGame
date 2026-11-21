// ABI declarations for UHT exec thunks (UE4.20 Core/CoreUObject: Misc/OutputDevice.h,
// UObject/Stack.h, UObject/ScriptMacros.h, UObject/UnrealType.h, UObject/CoreNet.h).
// Not recovered code.
#pragma once

#include "FortniteGameCode/UE4CodeGenRecovered.h"
#include "FortniteGameCode/UObjectRegistrationRecovered.h"

// Windows/WindowsPlatform.h: UE4.20 disables this for all code (void thunks never read
// Z_Param__Result).
#pragma warning(disable : 4100) // unreferenced formal parameter

typedef unsigned char uint8;
typedef signed char int8;
typedef signed short int16;
typedef long long int64;
typedef unsigned long long uint64;

class UField;
class UProperty;
struct FOutParmRec;

// Misc/OutputDevice.h: the polymorphic base of FFrame (vptr, then two flags).
class FOutputDevice
{
public:
	virtual ~FOutputDevice();
protected:
	bool bSuppressEventTag;
	bool bAutoEmitLineTerminator;
};

// UObject/Stack.h, at the reference's offsets: Code 0x20 and PropertyChainForCompiledIn 0x80
// (the thunks read both). FlowStack, a TArray<CodeSkipSizeType, TInlineAllocator<8>>, is not
// modelled; its 0x30 bytes keep the members after it in place.
struct FFrame : public FOutputDevice
{
public:
	UFunction* Node;
	UObject* Object;
	uint8* Code;
	uint8* Locals;
	UProperty* MostRecentProperty;
	uint8* MostRecentPropertyAddress;
	unsigned char FlowStack[0x30];
	FFrame* PreviousFrame;
	FOutParmRec* OutParms;
	UField* PropertyChainForCompiledIn;
	UFunction* CurrentNativeFunction;
	bool bArrayContextFailed;

	void Step(UObject* Context, void* const Z_Param__Result);
	void StepExplicitProperty(void* const Result, UProperty* Property);

	// FORCEINLINE_DEBUGGABLE is FORCEINLINE in shipping builds.
	template<class TProperty>
	__forceinline void StepCompiledIn(void* const Result)
	{
		if (Code)
		{
			Step(Object, Result);
		}
		else
		{
			TProperty* Property = (TProperty*)PropertyChainForCompiledIn;
			PropertyChainForCompiledIn = Property->Next;
			StepExplicitProperty(Result, Property);
		}
	}

	template<class TProperty, typename TNativeType>
	__forceinline TNativeType& StepCompiledInRef(void* const TemporaryBuffer)
	{
		MostRecentPropertyAddress = nullptr;

		if (Code)
		{
			Step(Object, TemporaryBuffer);
		}
		else
		{
			TProperty* Property = (TProperty*)PropertyChainForCompiledIn;
			PropertyChainForCompiledIn = Property->Next;
			StepExplicitProperty(TemporaryBuffer, Property);
		}

		return (MostRecentPropertyAddress != nullptr) ? *(TNativeType*)(MostRecentPropertyAddress) : *(TNativeType*)TemporaryBuffer;
	}
};

// UObject/ScriptMacros.h (shipping: no script native timer).
#define PARAM_PASSED_BY_VAL(ParamName, PropertyType, ParamType) \
	ParamType ParamName; \
	Stack.StepCompiledIn<PropertyType>(&ParamName);
#define PARAM_PASSED_BY_VAL_ZEROED(ParamName, PropertyType, ParamType) \
	ParamType ParamName = (ParamType)0; \
	Stack.StepCompiledIn<PropertyType>(&ParamName);
#define PARAM_PASSED_BY_REF(ParamName, PropertyType, ParamType) \
	ParamType ParamName##Temp; \
	ParamType& ParamName = Stack.StepCompiledInRef<PropertyType, ParamType>(&ParamName##Temp);
#define PARAM_PASSED_BY_REF_ZEROED(ParamName, PropertyType, ParamType) \
	ParamType ParamName##Temp = (ParamType)0; \
	ParamType& ParamName = Stack.StepCompiledInRef<PropertyType, ParamType>(&ParamName##Temp);
#define P_GET_PROPERTY(PropertyType, ParamName) \
	PropertyType::TCppType ParamName = PropertyType::GetDefaultPropertyValue(); \
	Stack.StepCompiledIn<PropertyType>(&ParamName);
#define P_GET_PROPERTY_REF(PropertyType, ParamName) \
	PropertyType::TCppType ParamName##Temp = PropertyType::GetDefaultPropertyValue(); \
	PropertyType::TCppType& ParamName = Stack.StepCompiledInRef<PropertyType, PropertyType::TCppType>(&ParamName##Temp);
#define P_GET_UBOOL(ParamName) uint32 ParamName##32 = 0; bool ParamName=false; Stack.StepCompiledIn<UBoolProperty>(&ParamName##32); ParamName = !!ParamName##32;
#define P_GET_UBOOL_REF(ParamName) PARAM_PASSED_BY_REF_ZEROED(ParamName, UBoolProperty, bool)
#define P_GET_OBJECT(ObjectType,ParamName) PARAM_PASSED_BY_VAL_ZEROED(ParamName, UObjectPropertyBase, ObjectType*)
#define P_GET_OBJECT_REF(ObjectType,ParamName) PARAM_PASSED_BY_REF_ZEROED(ParamName, UObjectPropertyBase, ObjectType*)
#define P_GET_STRUCT(StructType,ParamName) PARAM_PASSED_BY_VAL(ParamName, UStructProperty, StructType)
#define P_GET_STRUCT_REF(StructType,ParamName) PARAM_PASSED_BY_REF(ParamName, UStructProperty, StructType)
#define P_GET_ENUM(EnumType,ParamName) EnumType ParamName = (EnumType)0; Stack.StepCompiledIn<UEnumProperty>(&ParamName);
#define P_GET_ENUM_REF(EnumType,ParamName) PARAM_PASSED_BY_REF_ZEROED(ParamName, UEnumProperty, EnumType)

// Containers/EnumAsByte.h (the enum-class check and GetTypeHash omitted).
template<class TEnum>
class TEnumAsByte
{
public:
	typedef TEnum EnumType;

	__forceinline TEnumAsByte() { }
	__forceinline TEnumAsByte(const TEnumAsByte& InValue) : Value(InValue.Value) { }
	__forceinline TEnumAsByte(TEnum InValue) : Value(static_cast<uint8>(InValue)) { }
	explicit __forceinline TEnumAsByte(int32 InValue) : Value(static_cast<uint8>(InValue)) { }
	explicit __forceinline TEnumAsByte(uint8 InValue) : Value(InValue) { }

	__forceinline TEnumAsByte& operator=(TEnumAsByte InValue) { Value = InValue.Value; return *this; }
	__forceinline TEnumAsByte& operator=(TEnum InValue) { Value = static_cast<uint8>(InValue); return *this; }
	bool operator==(TEnum InValue) const { return static_cast<TEnum>(Value) == InValue; }
	bool operator==(TEnumAsByte InValue) const { return Value == InValue.Value; }
	operator TEnum() const { return (TEnum)Value; }

	TEnum GetValue() const { return (TEnum)Value; }

private:
	uint8 Value;
};

#define P_FINISH Stack.Code += !!Stack.Code; /* increment the code ptr unless it is null */
#define P_THIS_CAST(ClassType) ((ClassType*)Context)
#define P_THIS P_THIS_CAST(ThisClass)
#define P_NATIVE_BEGIN {
#define P_NATIVE_END }

// UObject/UnrealType.h: TPropertyTypeFundamentals<T>::TCppType and GetDefaultPropertyValue(),
// added to the generated property class declarations (Classes.gen.h).
#define FNGC_PROPERTY_FUNDAMENTALS(T) \
	typedef T TCppType; \
	static __forceinline TCppType GetDefaultPropertyValue() { return TCppType(); }
#define FNGC_EXTRA_MEMBERS_UByteProperty FNGC_PROPERTY_FUNDAMENTALS(uint8)
#define FNGC_EXTRA_MEMBERS_UInt8Property FNGC_PROPERTY_FUNDAMENTALS(int8)
#define FNGC_EXTRA_MEMBERS_UInt16Property FNGC_PROPERTY_FUNDAMENTALS(int16)
#define FNGC_EXTRA_MEMBERS_UIntProperty FNGC_PROPERTY_FUNDAMENTALS(int32)
#define FNGC_EXTRA_MEMBERS_UInt64Property FNGC_PROPERTY_FUNDAMENTALS(int64)
#define FNGC_EXTRA_MEMBERS_UUInt16Property FNGC_PROPERTY_FUNDAMENTALS(uint16)
#define FNGC_EXTRA_MEMBERS_UUInt32Property FNGC_PROPERTY_FUNDAMENTALS(uint32)
#define FNGC_EXTRA_MEMBERS_UUInt64Property FNGC_PROPERTY_FUNDAMENTALS(uint64)
#define FNGC_EXTRA_MEMBERS_UFloatProperty FNGC_PROPERTY_FUNDAMENTALS(float)
#define FNGC_EXTRA_MEMBERS_UDoubleProperty FNGC_PROPERTY_FUNDAMENTALS(double)
#define FNGC_EXTRA_MEMBERS_UNameProperty FNGC_PROPERTY_FUNDAMENTALS(FName)

// UObject/CoreNet.h
void RPC_ValidateFailed(const TCHAR* Reason);

// Structs passed to and from exec thunks, with their UE4.20 members and default constructors
// (Math/Vector.h, Rotator.h, Vector2D.h, Color.h; Misc/Guid.h; GameplayTags'
// GameplayTagContainer.h; GameplayAbilities' GameplayAbilitySpec.h). Copies are implicit, as
// there. Other members and methods are not modelled. tools/codegen/uht_props.py uses them
// only where the reference's FStructParams give the same SizeOf and AlignOf.
struct FVector
{
	float X;
	float Y;
	float Z;
	__forceinline FVector() {}
};

struct FRotator
{
	float Pitch;
	float Yaw;
	float Roll;
	__forceinline FRotator() { }
};

struct FVector2D
{
	float X;
	float Y;
	__forceinline FVector2D() { }
};

struct FLinearColor
{
	float R, G, B, A;
	__forceinline FLinearColor() {}
};

struct FGuid
{
	FGuid() : A(0), B(0), C(0), D(0) { }
private:
	uint32 A;
	uint32 B;
	uint32 C;
	uint32 D;
};

struct FGameplayTag
{
	static class UScriptStruct* StaticStruct();  // GENERATED_USTRUCT_BODY
	FGameplayTag() { }
private:
	FName TagName;
};

struct FGameplayAbilitySpecHandle
{
	static class UScriptStruct* StaticStruct();  // GENERATED_USTRUCT_BODY
	FGameplayAbilitySpecHandle() : Handle(-1) { }  // INDEX_NONE
private:
	int32 Handle;
};
