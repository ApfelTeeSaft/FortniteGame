// UE4.20 structs exec thunks pass by value, by reference or as returns, with their members,
// default constructors and copies as the 4.20 headers declare them (FTransform: TransformRecovered.h):
// UObject/WeakObjectPtr.h and
// WeakObjectPtrTemplates.h, Math/Color.h (FColor), SlateCore's Layout/Margin.h,
// Engine/NetSerialization.h (FVector_NetQuantize*), Engine/EngineTypes.h (FHitResult),
// Camera/PlayerCameraManager.h (FViewTargetTransitionParams) and
// GameplayAbilities' GameplayPrediction.h (FPredictionKey), GameplayAbilitySpec.h
// (FGameplayAbilityActivationInfo), Abilities/GameplayAbilityTargetTypes.h and
// GameplayAbilityTypes.h (FGameplayAbilityTargetDataHandle, FGameplayEventData) and
// GameplayEffectTypes.h
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

// CoreUObject: UObject/SoftObjectPath.h, PersistentObjectPtr.h and SoftObjectPtr.h, the members
// and special members the thunks use. Deviation from public 4.20: the reference's assignment
// takes a const reference and copies (docs/ENGINE_DIFFERENCES.md #6); 4.20 takes the path by
// value and moves its string.
struct FSoftObjectPath
{
	FSoftObjectPath() {}

	/** Construct from another soft object path */
	FSoftObjectPath(const FSoftObjectPath& Other)
		: AssetPathName(Other.AssetPathName)
		, SubPathString(Other.SubPathString)
	{
	}

	~FSoftObjectPath() {}

	FSoftObjectPath& operator=(const FSoftObjectPath& Other);

	/** Resets reference to point to null */
	void Reset()
	{
		AssetPathName = NAME_None;
		SubPathString.Reset();
	}

private:
	/** Asset path, patch to a top level object in a package */
	FName AssetPathName;

	/** Optional FString for subobject within an asset */
	FString SubPathString;
};

template<class TObjectID>
struct TPersistentObjectPtr
{
public:
	/** Default constructor, will be null */
	__forceinline TPersistentObjectPtr()
	{
		Reset();
	}

	/** Reset the lazy pointer back to the null state */
	__forceinline void Reset()
	{
		WeakPtr.Reset();
		ObjectID.Reset();
		TagAtLastTest = 0;
	}

	/** Copy a TPersistentObjectPtr */
	__forceinline TPersistentObjectPtr(const TPersistentObjectPtr& Other)
	{
		(*this)=Other;
	}

	/** Copy from another TPersistentObjectPtr */
	__forceinline void operator=(const TPersistentObjectPtr<TObjectID>& Other)
	{
		WeakPtr = Other.WeakPtr;
		TagAtLastTest = Other.TagAtLastTest;
		ObjectID = Other.ObjectID;
	}

private:
	/** Once the object has been noticed to be loaded, this is set to the object weak pointer **/
	mutable FWeakObjectPtr	WeakPtr;
	/** Compared to CurrentAnnotationTag and if they are not equal, a guid search will be performed **/
	mutable int32			TagAtLastTest;
	/** Guid for the object this pointer points to or will point to. **/
	TObjectID				ObjectID;
};

struct FSoftObjectPtr : public TPersistentObjectPtr<FSoftObjectPath>
{
public:
	/** Default constructor, will be null */
	__forceinline FSoftObjectPtr()
	{
	}

	/** Construct from another soft pointer */
	__forceinline FSoftObjectPtr(const FSoftObjectPtr& Other)
	{
		(*this)=Other;
	}

	using TPersistentObjectPtr<FSoftObjectPath>::operator=;
};

template<class T=UObject>
struct TSoftObjectPtr
{
	template <class U>
	friend struct TSoftObjectPtr;

public:
	/** Default constructor, will be null */
	__forceinline TSoftObjectPtr()
	{
	}

private:
	FSoftObjectPtr SoftObjectPtr;
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
		: GameplayTags(MoveTemp(Other.GameplayTags))
		, ParentTags(MoveTemp(Other.ParentTags))
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

// Engine: Camera/PlayerCameraManager.h. The enumerators and their values agree with the
// reference's FEnumParams for EViewTargetBlendFunction.
enum EViewTargetBlendFunction
{
	/** Camera does a simple linear interpolation. */
	VTBlend_Linear,
	/** Camera has a slight ease in and ease out, but amount of ease cannot be tweaked. */
	VTBlend_Cubic,
	/** Camera immediately accelerates, but smoothly decelerates into the target.  Ease amount controlled by BlendExp. */
	VTBlend_EaseIn,
	/** Camera smoothly accelerates, but does not decelerate into the target.  Ease amount controlled by BlendExp. */
	VTBlend_EaseOut,
	/** Camera smoothly accelerates and decelerates.  Ease amount controlled by BlendExp. */
	VTBlend_EaseInOut,
	VTBlend_MAX,
};

struct FViewTargetTransitionParams
{
	static class UScriptStruct* StaticStruct();  // GENERATED_USTRUCT_BODY
public:

	float BlendTime;

	TEnumAsByte<enum EViewTargetBlendFunction> BlendFunction;

	float BlendExp;

	uint32 bLockOutgoing:1;

	FViewTargetTransitionParams()
		: BlendTime(0.f)
		, BlendFunction(VTBlend_Cubic)
		, BlendExp(2.f)
		, bLockOutgoing(false)
	{}
};

// GameplayAbilities: GameplayAbilitySpec.h. The enumerators and their values agree with the
// reference's FEnumParams for EGameplayAbilityActivationMode.
namespace EGameplayAbilityActivationMode
{
	enum Type
	{
		/** We are the authority activating this ability */
		Authority,

		/** We are not the authority but aren't predicting yet. This is a mostly invalid state to be in */
		NonAuthority,

		/** We are predicting the activation of this ability */
		Predicting,

		/** We are not the authority, but the authority has confirmed this activation */
		Confirmed,

		/** We tried to activate it, and server told us we couldn't (even though we thought we could) */
		Rejected,
	};
}

struct FGameplayAbilityActivationInfo
{
	static class UScriptStruct* StaticStruct();  // GENERATED_USTRUCT_BODY

	FGameplayAbilityActivationInfo()
		: ActivationMode(EGameplayAbilityActivationMode::Authority)
		, bCanBeEndedByOtherInstance(false)
	{
	}

	/** Activation status of this ability */
	mutable TEnumAsByte<EGameplayAbilityActivationMode::Type>	ActivationMode;

	/** An ability that runs on multiple game instances can be canceled by a remote instance, but only if that remote instance has already confirmed starting it. */
	uint8 bCanBeEndedByOtherInstance:1;

private:

	/** This was the prediction key used to activate this ability. It does not get updated if a new prediction key is generated over the course of the ability. */
	FPredictionKey PredictionKeyWhenActivated;
};

// GameplayAbilities: Abilities/GameplayAbilityTargetTypes.h. Copies and the destructor are
// implicit, as there.
struct FGameplayAbilityTargetData;

struct FGameplayAbilityTargetDataHandle
{
	static class UScriptStruct* StaticStruct();  // GENERATED_USTRUCT_BODY

	FGameplayAbilityTargetDataHandle() { }

	/** Raw storage of target data, do not modify this directly */
	TArray<TSharedPtr<FGameplayAbilityTargetData>, TInlineAllocator<1> >	Data;
};

// GameplayAbilities: Abilities/GameplayAbilityTypes.h. Copies and the destructor are implicit.
struct FGameplayEventData
{
	static class UScriptStruct* StaticStruct();  // GENERATED_USTRUCT_BODY

	FGameplayEventData()
		: Instigator(nullptr)
		, Target(nullptr)
		, OptionalObject(nullptr)
		, OptionalObject2(nullptr)
		, EventMagnitude(0.f)
	{
	}

	/** Tag of the event that triggered this */
	FGameplayTag EventTag;

	/** The instigator of the event */
	const AActor* Instigator;

	/** The target of the event */
	const AActor* Target;

	/** An optional ability-specific object to be passed though the event */
	const UObject* OptionalObject;

	/** A second optional ability-specific object to be passed though the event */
	const UObject* OptionalObject2;

	/** Polymorphic context information */
	FGameplayEffectContextHandle ContextHandle;

	/** Tags that the instigator has */
	FGameplayTagContainer InstigatorTags;

	/** Tags that the target has */
	FGameplayTagContainer TargetTags;

	/** The magnitude of the triggering event */
	float EventMagnitude;

	/** The polymorphic target information for the event */
	FGameplayAbilityTargetDataHandle TargetData;
};

// OnlineSubsystemUtils: PartyBeaconState.h. The reference's FPlayerReservation is older than
// 4.20's: no Platform or bAllowCrossplay; ElapsedTime directly follows ValidationStr (its
// FStructParams: SizeOf 64, members at 0/40/56; docs/ENGINE_DIFFERENCES.md #7). Its default
// constructor is 4.20's without the crossplay flag. Copies and destructors are implicit.
struct FPlayerReservation
{
	static class UScriptStruct* StaticStruct();  // GENERATED_USTRUCT_BODY

	FPlayerReservation()
		: ElapsedTime(0.0f)
	{}

	/** Unique id for this reservation */
	FUniqueNetIdRepl UniqueId;

	/** Info needed to validate user credentials when joining a server */
	FString ValidationStr;

	/** Elapsed time since player made reservation and was last seen */
	float ElapsedTime;
};

struct FPartyReservation
{
	static class UScriptStruct* StaticStruct();  // GENERATED_USTRUCT_BODY

	FPartyReservation()
		: TeamNum(INDEX_NONE)
	{}

	/** Team assigned to this reservation */
	int32 TeamNum;

	/** Player initiating the request for the entire party */
	FUniqueNetIdRepl PartyLeader;

	/** All party members (including party leader) in the reservation */
	TArray<FPlayerReservation> PartyMembers;
};

// FortniteGame (no source): FAthenaQuickChatActiveEntry. Members, types and offsets are the
// reference's reflected properties (FStructParams: SizeOf 24; Bank's ClassFunc is
// UAthenaQuickChatBank::StaticClass). The default constructor is inferred from its inlined
// code in the reference's thunks, which zero every member and leave the padding. Copies are
// implicit (the thunks copy 24 bytes).
class UAthenaQuickChatBank;

struct FAthenaQuickChatActiveEntry
{
	static class UScriptStruct* StaticStruct();  // GENERATED_USTRUCT_BODY

	FAthenaQuickChatActiveEntry()
		: Bank(nullptr)
		, ContextObject(nullptr)
		, ContextValue(0)
		, Index(0)
	{}

	UAthenaQuickChatBank* Bank;
	UObject* ContextObject;
	int16 ContextValue;
	int8 Index;
};

// AssetRegistry: AssetDataTagMap.h and AssetData.h. Copies, moves and destructors are implicit,
// as there; FAssetData's default constructor leaves PackageFlags uninitialised, as there.
class FAssetDataTagMap;

class FAssetDataTagMapSharedView
{

public:
	/** Default constructor - empty map */
	FAssetDataTagMapSharedView()
	{
	}

private:
	/** Pointer to map being wrapped, it is created on demand */
	TSharedPtr<FAssetDataTagMap> Map;
};

struct FAssetData
{
	static class UScriptStruct* StaticStruct();  // GENERATED_USTRUCT_BODY

public:
	/** The object path for the asset in the form PackageName.AssetName. Only top level objects in a package can have AssetData */
	FName ObjectPath;
	/** The name of the package in which the asset is found, this is the full long package name such as /Game/Path/Package */
	FName PackageName;
	/** The path to the package in which the asset is found, this is /Game/Path with the Package stripped off */
	FName PackagePath;
	/** The name of the asset without the package */
	FName AssetName;
	/** The name of the asset's class */
	FName AssetClass;
	/** The map of values for properties that were marked AssetRegistrySearchable or added by GetAssetRegistryTags */
	FAssetDataTagMapSharedView TagsAndValues;
	/** The IDs of the pakchunks this asset is located in for streaming install.  Empty if not assigned to a chunk */
	TArray<int32> ChunkIDs;
	/** Asset package flags */
	uint32 PackageFlags;

public:
	/** Default constructor */
	FAssetData()
	{}
};

// GameplayAbilities: AttributeSet.h (FGameplayAttribute) and GameplayEffect.h. Copies and
// destructors are implicit; FGameplayEffectSpecForRPC's default constructor is out of line, in
// GameplayEffect.cpp, as the reference's thunks call it.
class UProperty;
class UStruct;
class UGameplayEffect;

struct FGameplayAttribute
{
	static class UScriptStruct* StaticStruct();  // GENERATED_USTRUCT_BODY

	FGameplayAttribute()
		: Attribute(nullptr)
		, AttributeOwner(nullptr)
	{
	}

	/** Name of the attribute, usually the same as property name */
	FString AttributeName;

private:
	UProperty*	Attribute;
	UStruct* AttributeOwner;
};

struct FGameplayEffectModifiedAttribute
{
	static class UScriptStruct* StaticStruct();  // GENERATED_USTRUCT_BODY

	/** The attribute that has been modified */
	FGameplayAttribute Attribute;

	/** Total magnitude applied to that attribute */
	float TotalMagnitude;

	FGameplayEffectModifiedAttribute() : TotalMagnitude(0.0f) {}
};

struct FGameplayEffectSpecForRPC
{
	static class UScriptStruct* StaticStruct();  // GENERATED_USTRUCT_BODY

	FGameplayEffectSpecForRPC();

	/** GameplayEfect definition. The static data that this spec points to. */
	const UGameplayEffect* Def;

	TArray<FGameplayEffectModifiedAttribute> ModifiedAttributes;

	FGameplayEffectContextHandle EffectContext; // This tells us how we got here (who / what applied us)

	FGameplayTagContainer AggregatedSourceTags;

	FGameplayTagContainer AggregatedTargetTags;

	float Level;

	float AbilityLevel;
};

// Engine: Engine/NetSerialization.h
struct FFastArraySerializerItem
{
	static class UScriptStruct* StaticStruct();  // GENERATED_USTRUCT_BODY

	FFastArraySerializerItem()
		: ReplicationID(INDEX_NONE), ReplicationKey(INDEX_NONE), MostRecentArrayReplicationKey(INDEX_NONE)
	{

	}

	FFastArraySerializerItem(const FFastArraySerializerItem &InItem)
		: ReplicationID(INDEX_NONE), ReplicationKey(INDEX_NONE), MostRecentArrayReplicationKey(INDEX_NONE)
	{

	}

	FFastArraySerializerItem& operator=(const FFastArraySerializerItem& In)
	{
		if (&In != this)
		{
			ReplicationID = INDEX_NONE;
			ReplicationKey = INDEX_NONE;
			MostRecentArrayReplicationKey = INDEX_NONE;
		}
		return *this;
	}

	int32 ReplicationID;

	int32 ReplicationKey;

	int32 MostRecentArrayReplicationKey;
};

// FortniteGame (no source): the item entry and the structs it holds. Members, types and offsets
// are the reference's reflected properties (FStructParams), class types from their ClassFunc.
// Their constructors are out of line in the reference (the thunks call them), and so is
// FFortItemEntry's destructor. Their code agrees with the offsets:
// - FFortItemEntry::FFortItemEntry (0x00C3DB80) sets the base's three INDEX_NONE, Count 1,
//   Durability 1.0f, and the three bools as bytes at 0x60-0x62;
// - FFortItemEntryStateValue's (0x00C3DC40) zeroes IntValue and NameValue and stores its
//   argument, which the thunks pass as 0, in StateType.
// The bools' order is the declaration order of their properties.
namespace EFortItemEntryState
{
	// The reference's enumerators and values (FEnumParams).
	enum Type
	{
		NoneState = 0,
		NewItemCount = 1,
		ShouldShowItemToast = 2,
		DurabilityInitialized = 3,
		DoNotShowSpawnParticles = 4,
		FromRecoveredBackpack = 5,
		FromGift = 6,
		PendingUpgradeCriteriaProgress = 7,
		OwnerBuildingHandle = 8,
		FromDroppedPickup = 9,
		JustCrafted = 10,
		CraftAndSlotTarget = 11,
	};
}

struct FFortItemEntryStateValue
{
	static class UScriptStruct* StaticStruct();  // GENERATED_USTRUCT_BODY

	FFortItemEntryStateValue(EFortItemEntryState::Type InStateType = EFortItemEntryState::NoneState);

	int32 IntValue;
	FName NameValue;
	TEnumAsByte<EFortItemEntryState::Type> StateType;
};

class UFortHeroType;
class UFortItemDefinition;
class AFortInventory;
class UFortAlterationItemDefinition;

// 24-40 has no reflected property. FFortItemEntry's destructor (0x0098E350) releases it as a
// non-thread-safe TSharedPtr (the controller at +0x88 of the entry: shared count, DestroyObject,
// weak count, delete); the pointee's type is not recovered.
struct FNGCUnrecoveredGiftingData;

struct FFortGiftingInfo
{
	static class UScriptStruct* StaticStruct();  // GENERATED_USTRUCT_BODY

	FString PlayerName;
	UFortHeroType* HeroType;

private:
	TSharedPtr<FNGCUnrecoveredGiftingData> Unreflected;
};

struct FFortItemEntry : public FFastArraySerializerItem
{
	static class UScriptStruct* StaticStruct();  // GENERATED_USTRUCT_BODY

	FFortItemEntry();
	~FFortItemEntry();

	int32 Count;
	int32 PreviousCount;
	UFortItemDefinition* ItemDefinition;
	float Durability;
	int32 Level;
	int32 LoadedAmmo;
	TArray<FString> AlterationDefinitions;
	FString ItemSource;
	FGuid ItemGuid;
	bool inventory_overflow_date;
	bool bIsReplicatedCopy;
	bool bIsDirty;
	FFortGiftingInfo GiftingInfo;
	TArray<FFortItemEntryStateValue> StateValues;
	TWeakObjectPtr<AFortInventory> ParentInventory;
	FGameplayAbilitySpecHandle GameplayAbilitySpecHandle;
	TArray<UFortAlterationItemDefinition*> AlterationInstances;
};
