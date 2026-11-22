// UE4.20 structs exec thunks pass by value, by reference or as returns, with their members,
// default constructors and copies as the 4.20 headers declare them (FTransform: TransformRecovered.h):
// UObject/WeakObjectPtr.h and
// WeakObjectPtrTemplates.h, Math/Color.h (FColor), SlateCore's Layout/Margin.h,
// Engine/NetSerialization.h (FVector_NetQuantize*), Engine/EngineTypes.h (FHitResult) and
// GameplayAbilities' GameplayPrediction.h (FPredictionKey) and GameplayEffectTypes.h
// (FGameplayEffectContextHandle, FGameplayCueParameters), GameplayTags' GameplayTagContainer.h
// (FGameplayTagContainer), InputCore's InputCoreTypes.h (FKey), CoreUObject's
// UObject/CoreOnline.h and Engine's GameFramework/OnlineReplStructs.h (FUniqueNetIdRepl).
// Virtual functions the thunks never call are declared without their bodies; only the vtables'
// addresses are referenced. Other members are not modelled.
// The member offsets agree with each struct's reflected properties in the reference
// (FStructParams). Not recovered code.
#pragma once

#include "FortniteGameCode/ContainersRecovered.h"
#include "FortniteGameCode/TextRecovered.h"

enum { INDEX_NONE = -1 };

class UObject;
class UPackageMap;
class UPhysicalMaterial;
class AActor;
class UPrimitiveComponent;
class USceneComponent;

// UObject/WeakObjectPtr.h
struct FWeakObjectPtr
{
public:
	__forceinline FWeakObjectPtr()
	{
		Reset();
	}

	__forceinline FWeakObjectPtr(const FWeakObjectPtr &Other)
	{
		(*this)=Other;
	}

	__forceinline void Reset()
	{
		ObjectIndex = INDEX_NONE;
		ObjectSerialNumber = 0;
	}

	__forceinline void operator=(const FWeakObjectPtr &Other)
	{
		ObjectIndex = Other.ObjectIndex;
		ObjectSerialNumber = Other.ObjectSerialNumber;
	}

private:
	int32		ObjectIndex;
	int32		ObjectSerialNumber;
};

// UObject/WeakObjectPtrTemplates.h
template<class T, class TWeakObjectPtrBase = FWeakObjectPtr>
struct TWeakObjectPtr : private TWeakObjectPtrBase
{
public:
	TWeakObjectPtr() = default;
	TWeakObjectPtr(const TWeakObjectPtr&) = default;
	TWeakObjectPtr& operator=(const TWeakObjectPtr&) = default;
	~TWeakObjectPtr() = default;
};

// Math/Color.h (PLATFORM_LITTLE_ENDIAN, _MSC_VER)
struct FColor
{
public:
#pragma warning(push)
#pragma warning(disable : 4201) // nameless struct/union (UE4.20 disables it)
	union { struct{ uint8 B,G,R,A; }; uint32 AlignmentDummy; };
#pragma warning(pop)

	__forceinline FColor() {}
};

// Layout/Margin.h
struct FMargin
{
	static class UScriptStruct* StaticStruct();  // GENERATED_USTRUCT_BODY

	float Left;
	float Top;
	float Right;
	float Bottom;

public:
	FMargin( )
		: Left(0.0f)
		, Top(0.0f)
		, Right(0.0f)
		, Bottom(0.0f)
	{ }
};

// Core: Math/TransformVectorized.h. Defined in TransformRecovered.h, which each unity unit
// includes after its own GlobalVectorConstants (tools/codegen/unity.py): its default
// constructor reads them. Declarations here need only the incomplete type.
struct FTransform;

// Engine/NetSerialization.h
struct FVector_NetQuantize : public FVector
{
	static class UScriptStruct* StaticStruct();  // GENERATED_USTRUCT_BODY
	__forceinline FVector_NetQuantize()
	{}
};

struct FVector_NetQuantize10 : public FVector
{
	static class UScriptStruct* StaticStruct();
	__forceinline FVector_NetQuantize10()
	{}

	explicit __forceinline FVector_NetQuantize10(EForceInit E)
	: FVector(E)
	{}
};

struct FVector_NetQuantize100 : public FVector
{
	static class UScriptStruct* StaticStruct();
	__forceinline FVector_NetQuantize100()
	{}
};

struct FVector_NetQuantizeNormal : public FVector
{
	static class UScriptStruct* StaticStruct();
	__forceinline FVector_NetQuantizeNormal()
	{}

	explicit __forceinline FVector_NetQuantizeNormal(EForceInit E)
	: FVector(E)
	{}
};

// Engine/EngineTypes.h
struct FHitResult
{
	static class UScriptStruct* StaticStruct();  // GENERATED_USTRUCT_BODY

	uint8 bBlockingHit:1;
	uint8 bStartPenetrating:1;
	int32 FaceIndex;
	float Time;
	float Distance;
	FVector_NetQuantize Location;
	FVector_NetQuantize ImpactPoint;
	FVector_NetQuantizeNormal Normal;
	FVector_NetQuantizeNormal ImpactNormal;
	FVector_NetQuantize TraceStart;
	FVector_NetQuantize TraceEnd;
	float PenetrationDepth;
	int32 Item;
	TWeakObjectPtr<class UPhysicalMaterial> PhysMaterial;
	TWeakObjectPtr<class AActor> Actor;
	TWeakObjectPtr<class UPrimitiveComponent> Component;
	FName BoneName;
	FName MyBoneName;

	FHitResult()
	{
		Init();
	}

	/** Initialize empty hit result with given time. */
	__forceinline void Init()
	{
		FMemory::Memzero(this, sizeof(FHitResult));
		Time = 1.f;
	}
};

// GameplayAbilities: GameplayPrediction.h
struct FPredictionKey
{
	static class UScriptStruct* StaticStruct();  // GENERATED_USTRUCT_BODY

	typedef int16 KeyType;

	FPredictionKey()
	: Current(0), Base(0), PredictiveConnection(nullptr), bIsStale(false), bIsServerInitiated(false)
	{

	}

	int16	Current;
	int16	Base;
	UPackageMap*	PredictiveConnection;
	bool bIsStale;
	bool bIsServerInitiated;
};

// InputCore: InputCoreTypes.h
struct FKeyDetails;

struct FKey
{
	static class UScriptStruct* StaticStruct();  // GENERATED_USTRUCT_BODY

	FKey()
	{
	}

private:
	FName KeyName;
	mutable class TSharedPtr<struct FKeyDetails> KeyDetails;
};

// CoreUObject: UObject/CoreOnline.h
class FUniqueNetId;

struct FUniqueNetIdWrapper
{
public:

	FUniqueNetIdWrapper()
		: UniqueNetId()
	{
	}

	FUniqueNetIdWrapper(const TSharedPtr<const FUniqueNetId>& InUniqueNetId)
		: UniqueNetId(InUniqueNetId)
	{
	}

	FUniqueNetIdWrapper(const FUniqueNetIdWrapper& InUniqueNetId)
		: UniqueNetId(InUniqueNetId.UniqueNetId)
	{
	}

	virtual ~FUniqueNetIdWrapper()
	{
	}

	virtual void SetUniqueNetId(const TSharedPtr<const FUniqueNetId>& InUniqueNetId);

protected:

	// Actual unique id
	TSharedPtr<const FUniqueNetId> UniqueNetId;
};

// Engine: GameFramework/OnlineReplStructs.h
struct FUniqueNetIdRepl : public FUniqueNetIdWrapper
{
	static class UScriptStruct* StaticStruct();  // GENERATED_USTRUCT_BODY

	FUniqueNetIdRepl()
	{
	}

	FUniqueNetIdRepl(const FUniqueNetIdRepl& InWrapper)
		: FUniqueNetIdWrapper(InWrapper.UniqueNetId)
	{
	}

	virtual ~FUniqueNetIdRepl() {}

	virtual void SetUniqueNetId(const TSharedPtr<const FUniqueNetId>& InUniqueNetId) override;

protected:
	TArray<uint8> ReplicationBytes;
};

// GameplayAbilities: GameplayEffectTypes.h
struct FGameplayEffectContext;
class UAbilitySystemComponent;

struct FGameplayEffectContextHandle
{
	static class UScriptStruct* StaticStruct();  // GENERATED_USTRUCT_BODY

	FGameplayEffectContextHandle()
	{
	}

	virtual ~FGameplayEffectContextHandle()
	{
	}

	virtual AActor* GetInstigator() const;
	virtual UAbilitySystemComponent* GetInstigatorAbilitySystemComponent() const;
	virtual AActor* GetEffectCauser() const;
	virtual const FVector& GetOrigin() const;
	virtual bool HasOrigin() const;

private:
	TSharedPtr<FGameplayEffectContext> Data;
};

// GameplayTags: GameplayTagContainer.h. operator= is defined out of line, in
// GameplayTagContainer.cpp; the copy constructor calls it.
struct FGameplayTagContainer
{
	static class UScriptStruct* StaticStruct();  // GENERATED_USTRUCT_BODY

	FGameplayTagContainer()
	{
	}

	FGameplayTagContainer(FGameplayTagContainer const& Other)
	{
		*this = Other;
	}

	FGameplayTagContainer(FGameplayTagContainer&& Other)
		: GameplayTags(static_cast<TArray<FGameplayTag>&&>(Other.GameplayTags))   // MoveTemp
		, ParentTags(static_cast<TArray<FGameplayTag>&&>(Other.ParentTags))
	{

	}

	~FGameplayTagContainer()
	{
	}

	FGameplayTagContainer& operator=(FGameplayTagContainer const& Other);
	FGameplayTagContainer& operator=(FGameplayTagContainer&& Other);

protected:
	TArray<FGameplayTag> GameplayTags;
	TArray<FGameplayTag> ParentTags;
};

// GameplayAbilities: GameplayEffectTypes.h. Copies and the destructor are implicit, as there.
struct FGameplayCueParameters
{
	static class UScriptStruct* StaticStruct();  // GENERATED_USTRUCT_BODY

	FGameplayCueParameters()
	: NormalizedMagnitude(0.0f)
	, RawMagnitude(0.0f)
	, Location(ForceInitToZero)
	, Normal(ForceInitToZero)
	, GameplayEffectLevel(1)
	, AbilityLevel(1)
	{}

	float NormalizedMagnitude;
	float RawMagnitude;
	FGameplayEffectContextHandle EffectContext;
	FGameplayTag MatchedTagName;
	FGameplayTag OriginalTag;
	FGameplayTagContainer AggregatedSourceTags;
	FGameplayTagContainer AggregatedTargetTags;
	FVector_NetQuantize10 Location;
	FVector_NetQuantizeNormal Normal;
	TWeakObjectPtr<AActor> Instigator;
	TWeakObjectPtr<AActor> EffectCauser;
	TWeakObjectPtr<const UObject> SourceObject;
	TWeakObjectPtr<const UPhysicalMaterial> PhysicalMaterial;
	int32 GameplayEffectLevel;
	int32 AbilityLevel;
	TWeakObjectPtr<USceneComponent> TargetAttachComponent;
};
