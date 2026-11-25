// UE4.20 Core containers for code that builds a map: Containers/ContainerAllocationPolicies.h
// (the set allocators), BitArray.h, SparseArray.h, Set.h, Map.h and Templates/Tuple.h (TPair).
// Member layout, construction, destruction and TMap::Add follow the 4.20 source. The
// reference keeps TSet::Emplace and TSparseArray::Empty out of line, so they are only declared
// here. Not recovered code.
//
// EngineStructsRecovered.h includes this in place of its empty TSet stand-in when a unit
// defines FNGC_SET_RECOVERED.
#pragma once

#include "FortniteGameCode/ContainersRecovered.h"

// Containers/ContainerAllocationPolicies.h
#define DEFAULT_NUMBER_OF_ELEMENTS_PER_HASH_BUCKET	2
#define DEFAULT_BASE_NUMBER_OF_HASH_BUCKETS			8
#define DEFAULT_MIN_NUMBER_OF_HASHED_ELEMENTS		4

class FDefaultBitArrayAllocator;

template<typename InElementAllocator = FDefaultAllocator,typename InBitArrayAllocator = FDefaultBitArrayAllocator>
class TSparseArrayAllocator
{
public:
	typedef InElementAllocator ElementAllocator;
	typedef InBitArrayAllocator BitArrayAllocator;
};

template<
	typename InSparseArrayAllocator               = TSparseArrayAllocator<>,
	typename InHashAllocator                      = TInlineAllocator<1,FDefaultAllocator>,
	uint32   AverageNumberOfElementsPerHashBucket = DEFAULT_NUMBER_OF_ELEMENTS_PER_HASH_BUCKET,
	uint32   BaseNumberOfHashBuckets              = DEFAULT_BASE_NUMBER_OF_HASH_BUCKETS,
	uint32   MinNumberOfHashedElements            = DEFAULT_MIN_NUMBER_OF_HASHED_ELEMENTS
	>
class TSetAllocator
{
public:
	typedef InSparseArrayAllocator SparseArrayAllocator;
	typedef InHashAllocator        HashAllocator;
};

class FDefaultSetAllocator         : public TSetAllocator<>         { public: typedef TSetAllocator<>         Typedef; };
class FDefaultBitArrayAllocator    : public TInlineAllocator<4>     { public: typedef TInlineAllocator<4>     Typedef; };

// Containers/BitArray.h
template<typename Allocator = FDefaultBitArrayAllocator>
class TBitArray
{
public:
	explicit TBitArray( const bool Value = false, const int32 InNumBits = 0 )
	:	NumBits(0)
	,	MaxBits(0)
	{
		Init(Value,InNumBits);
	}

	// FMath::DivideAndRoundUp and FMemory::Memset written out (not in these shims). For the
	// default TBitArray (no bits) both fold away.
	__forceinline void Init(bool Value,int32 InNumBits)
	{
		Empty(InNumBits);
		if(InNumBits)
		{
			NumBits = InNumBits;
			memset(GetData(),Value ? 0xff : 0,((NumBits + NumBitsPerDWORD - 1) / NumBitsPerDWORD) * sizeof(uint32));
		}
	}

	void Empty(int32 ExpectedNumBits = 0)
	{
		NumBits = 0;

		ExpectedNumBits = ((ExpectedNumBits + NumBitsPerDWORD - 1) / NumBitsPerDWORD) * NumBitsPerDWORD;
		// If the expected number of bits doesn't match the allocated number of bits, reallocate.
		if(MaxBits != ExpectedNumBits)
		{
			MaxBits = ExpectedNumBits;
			Realloc(0);
		}
	}

	__forceinline uint32* GetData()
	{
		return (uint32*)AllocatorInstance.GetAllocation();
	}

private:
	enum { NumBitsPerDWORD = 32 };

	__declspec(noinline) void Realloc(int32 PreviousNumBits);

	typedef typename Allocator::template ForElementType<uint32> AllocatorType;

	AllocatorType AllocatorInstance;
	int32         NumBits;
	int32         MaxBits;
};

// Containers/SparseArray.h (the anonymous struct is an MSVC extension, warning C4201, which UE
// builds disable)
#pragma warning(push)
#pragma warning(disable : 4201)
template<typename ElementType>
union TSparseArrayElementOrFreeListLink
{
	/** If the element is allocated, its value is stored here. */
	ElementType ElementData;

	struct
	{
		/** If the element isn't allocated, this is a link to the previous element in the array's free list. */
		int32 PrevFreeIndex;

		/** If the element isn't allocated, this is a link to the next element in the array's free list. */
		int32 NextFreeIndex;
	};
};
#pragma warning(pop)

template<typename InElementType,typename Allocator = TSparseArrayAllocator<> >
class TSparseArray
{
public:
	typedef InElementType ElementType;

	/** Destructor. */
	~TSparseArray()
	{
		// Destruct the elements in the array.
		Empty();
	}

	/** Removes all elements from the array, potentially leaving space allocated for an expected number of elements about to be added. */
	void Empty(int32 ExpectedNumElements = 0);   // out of line in the reference

	TSparseArray()
	:	FirstFreeIndex(-1)
	,	NumFreeIndices(0)
	{}

	__forceinline ElementType& operator[](int32 Index)
	{
		return *(ElementType*)&GetData(Index).ElementData;
	}

private:
	typedef TSparseArrayElementOrFreeListLink<
		TAlignedBytes<sizeof(ElementType),alignof(ElementType)>
		> FElementOrFreeListLink;

	__forceinline FElementOrFreeListLink& GetData(int32 Index)
	{
		return ((FElementOrFreeListLink*)Data.GetData())[Index];
	}

	typedef TArray<FElementOrFreeListLink,typename Allocator::ElementAllocator> DataType;
	DataType Data;

	typedef TBitArray<typename Allocator::BitArrayAllocator> AllocationBitArrayType;
	AllocationBitArrayType AllocationFlags;

	/** The index of an unallocated element in the array that currently contains the head of the linked list of free elements. */
	int32 FirstFreeIndex;

	/** The number of elements in the free list. */
	int32 NumFreeIndices;
};

// Containers/Set.h
template<typename ElementType, bool bInAllowDuplicateKeys = false> struct DefaultKeyFuncs;

class FSetElementId
{
public:
	template<typename,typename,typename> friend class TSet;

	/** Default constructor. */
	__forceinline FSetElementId():
		Index(INDEX_NONE)
	{}

	/** Converts the ID to an integer. */
	__forceinline int32 AsInteger() const
	{
		return Index;
	}

private:
	/** The index of the element in the set's element array. */
	int32 Index;

	/** Initialization constructor. */
	__forceinline FSetElementId(int32 InIndex):
		Index(InIndex)
	{}
};

template<typename InElementType>
class TSetElement
{
public:
	typedef InElementType ElementType;

	/** The element's value. */
	ElementType Value;

	/** The id of the next element in the same hash bucket. */
	mutable FSetElementId HashNextId;

	/** The hash bucket that the element is currently linked to. */
	mutable int32 HashIndex;
};

template<typename InElementType, typename KeyFuncs = DefaultKeyFuncs<InElementType>, typename Allocator = FDefaultSetAllocator>
class TSet
{
public:
	typedef InElementType ElementType;

	/** Initialization constructor. */
	__forceinline TSet()
	:	HashSize(0)
	{}

	/** Destructor. */
	__forceinline ~TSet()
	{
		HashSize = 0;
	}

	/**
	 * Adds an element to the set by constructing the ElementType in-place with a set of arguments.
	 * Out of line in the reference: only declared.
	 */
	template <typename ArgsType>
	FSetElementId Emplace(ArgsType&& Args, bool* bIsAlreadyInSetPtr = nullptr);

	__forceinline ElementType& operator[](FSetElementId Id)
	{
		return Elements[Id.AsInteger()].Value;
	}

private:
	typedef TSetElement<InElementType> SetElementType;

	typedef TSparseArray<SetElementType,typename Allocator::SparseArrayAllocator>     ElementArrayType;
	typedef typename Allocator::HashAllocator::template ForElementType<FSetElementId> HashType;

	ElementArrayType Elements;

	mutable HashType Hash;
	mutable int32	 HashSize;
};

// Templates/Tuple.h: the two-element TTuple TPair names (Key, Value).
template <typename... Types>
struct TTuple;

template <typename KeyType, typename ValueType>
struct TTuple<KeyType, ValueType>
{
	KeyType   Key;
	ValueType Value;
};

template <typename KeyType, typename ValueType>
using TPair = TTuple<KeyType, ValueType>;

// Containers/Map.h
template <typename T> struct TRValueToLValueReference      { typedef T  Type; };
template <typename T> struct TRValueToLValueReference<T&&> { typedef T& Type; };

template <typename KeyInitType, typename ValueInitType>
class TPairInitializer
{
public:
	typename TRValueToLValueReference<KeyInitType  >::Type Key;
	typename TRValueToLValueReference<ValueInitType>::Type Value;

	/** Initialization constructor. */
	__forceinline TPairInitializer(KeyInitType InKey,ValueInitType InValue)
		: Key  (InKey  )
		, Value(InValue)
	{
	}
};

template<typename KeyType, typename ValueType, bool bInAllowDuplicateKeys> struct TDefaultMapHashableKeyFuncs;

template <typename KeyType, typename ValueType, typename SetAllocator, typename KeyFuncs>
class TMapBase
{
protected:
	typedef TPair<KeyType, ValueType> ElementType;

	TMapBase() = default;

public:
	/**
	 * Set the value associated with a key.
	 *
	 * @param InKey The key to associate the value with.
	 * @param InValue The value to associate with the key.
	 * @return A reference to the value as stored in the map. The reference is only valid until the next change to any key in the map.
	 */
	__forceinline ValueType& Add(      KeyType&& InKey,       ValueType&& InValue) { return Emplace(MoveTemp(InKey), MoveTemp(InValue)); }

	/**
	 * Sets the value associated with a key.
	 *
	 * @param InKey The key to associate the value with.
	 * @param InValue The value to associate with the key.
	 * @return A reference to the value as stored in the map. The reference is only valid until the next change to any key in the map.
	 */
	template <typename InitKeyType, typename InitValueType>
	ValueType& Emplace(InitKeyType&& InKey, InitValueType&& InValue)
	{
		const FSetElementId PairId = Pairs.Emplace(TPairInitializer<InitKeyType&&, InitValueType&&>(Forward<InitKeyType>(InKey), Forward<InitValueType>(InValue)));

		return Pairs[PairId].Value;
	}

protected:
	typedef TSet<ElementType, KeyFuncs, SetAllocator> ElementSetType;

	/** A set of the key-value pairs in the map. */
	ElementSetType Pairs;
};

template <typename KeyType, typename ValueType, typename SetAllocator, typename KeyFuncs>
class TSortableMapBase : public TMapBase<KeyType, ValueType, SetAllocator, KeyFuncs>
{
};

template<typename InKeyType, typename InValueType, typename SetAllocator = FDefaultSetAllocator, typename KeyFuncs = TDefaultMapHashableKeyFuncs<InKeyType,InValueType,false> >
class TMap : public TSortableMapBase<InKeyType, InValueType, SetAllocator, KeyFuncs>
{
};
