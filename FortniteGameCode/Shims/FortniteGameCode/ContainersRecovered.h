// UE4.20 Core containers as far as exec thunks use them: HAL/UnrealMemory.h (FMemory),
// Templates/MemoryOps.h, Containers/ContainerAllocationPolicies.h (FHeapAllocator,
// FDefaultAllocator), Containers/Array.h (TArray) and Containers/UnrealString.h (FString).
// Member layout, construction, copy, move, destruction and ResizeForCopy follow the 4.20
// source; everything else is left out. Not recovered code.
#pragma once

#include <string.h>
#include <new>   // placement new, as Core's headers include it
#include "FortniteGameCode/UE4CodeGenRecovered.h"

enum { DEFAULT_ALIGNMENT = 0 };
#define MAX_int32 ((int32)0x7fffffff)

// HAL/UnrealMemory.h. On Windows INLINE_FMEMORY_OPERATION is 0: these are out of line in Core.
struct FMemory
{
	static __forceinline void* Memcpy(void* Dest, const void* Src, SIZE_T Count)
	{
		return memcpy(Dest, Src, Count);  // FGenericPlatformMemory::Memcpy
	}

	static __forceinline void* Memzero(void* Dest, SIZE_T Count)
	{
		return memset(Dest, 0, Count);  // FGenericPlatformMemory::Memzero
	}

	static void* Realloc(void* Original, SIZE_T Count, uint32 Alignment = DEFAULT_ALIGNMENT);
	static void Free(void* Original);
	static SIZE_T QuantizeSize(SIZE_T Count, uint32 Alignment = DEFAULT_ALIGNMENT);
};

// Templates/EnableIf.h, IsTriviallyDestructible.h, UnrealTypeTraits.h (TIsBitwiseConstructible
// for one element type, the only form TArray's copies use here).
template <bool Predicate, typename Result = void>
class TEnableIf;

template <typename Result>
class TEnableIf<true, Result>
{
public:
	typedef Result Type;
};

template <typename Result>
class TEnableIf<false, Result>
{ };

template <typename T>
struct TIsTriviallyDestructible
{
	enum { Value = __has_trivial_destructor(T) };
};

template <typename T>
struct TIsTriviallyCopyConstructible
{
	enum { Value = __has_trivial_copy(T) };
};

template <typename T, typename Arg>
struct TIsBitwiseConstructible
{
	enum { Value = false };
};

template <typename T>
struct TIsBitwiseConstructible<T, T>
{
	// Ts can always be bitwise constructed from itself if it is trivially copyable.
	enum { Value = TIsTriviallyCopyConstructible<T>::Value };
};

// Templates/MemoryOps.h
template <typename ElementType>
__forceinline typename TEnableIf<!TIsTriviallyDestructible<ElementType>::Value>::Type DestructItems(ElementType* Element, int32 Count)
{
	while (Count)
	{
		// We need a typedef here because VC won't compile the destructor call below if ElementType itself has a member called ElementType
		typedef ElementType DestructItemsElementTypeTypedef;

		Element->DestructItemsElementTypeTypedef::~DestructItemsElementTypeTypedef();
		++Element;
		--Count;
	}
}

template <typename ElementType>
__forceinline typename TEnableIf<TIsTriviallyDestructible<ElementType>::Value>::Type DestructItems(ElementType* Elements, int32 Count)
{
}

template <typename DestinationElementType, typename SourceElementType>
__forceinline typename TEnableIf<!TIsBitwiseConstructible<DestinationElementType, SourceElementType>::Value>::Type ConstructItems(void* Dest, const SourceElementType* Source, int32 Count)
{
	while (Count)
	{
		new (Dest) DestinationElementType(*Source);
		++(DestinationElementType*&)Dest;
		++Source;
		--Count;
	}
}

template <typename DestinationElementType, typename SourceElementType>
__forceinline typename TEnableIf<TIsBitwiseConstructible<DestinationElementType, SourceElementType>::Value>::Type ConstructItems(void* Dest, const SourceElementType* Source, int32 Count)
{
	FMemory::Memcpy(Dest, Source, sizeof(SourceElementType) * Count);
}

// Containers/ContainerAllocationPolicies.h
__forceinline int32 DefaultCalculateSlackReserve(int32 NumElements, SIZE_T BytesPerElement, bool bAllowQuantize, uint32 Alignment = DEFAULT_ALIGNMENT)
{
	int32 Retval = NumElements;
	if (bAllowQuantize)
	{
		Retval = FMemory::QuantizeSize(SIZE_T(Retval) * SIZE_T(BytesPerElement), Alignment) / BytesPerElement;
		// NumElements and MaxElements are stored in 32 bit signed integers so we must be careful not to overflow here.
		if (NumElements > Retval)
		{
			Retval = MAX_int32;
		}
	}

	return Retval;
}

struct FScriptContainerElement
{
};

class FHeapAllocator
{
public:
	enum { NeedsElementType = false };
	enum { RequireRangeCheck = true };

	class ForAnyElementType
	{
	public:
		ForAnyElementType()
			: Data(nullptr)
		{}

		__forceinline void MoveToEmpty(ForAnyElementType& Other)
		{
			if (Data)
			{
				FMemory::Free(Data);
			}

			Data       = Other.Data;
			Other.Data = nullptr;
		}

		__forceinline ~ForAnyElementType()
		{
			if(Data)
			{
				FMemory::Free(Data);
			}
		}

		__forceinline FScriptContainerElement* GetAllocation() const
		{
			return Data;
		}
		__forceinline void ResizeAllocation(int32 PreviousNumElements, int32 NumElements, SIZE_T NumBytesPerElement)
		{
			// Avoid calling FMemory::Realloc( nullptr, 0 ) as ANSI C mandates returning a valid pointer which is not what we want.
			if (Data || NumElements)
			{
				Data = (FScriptContainerElement*)FMemory::Realloc( Data, NumElements*NumBytesPerElement );
			}
		}
		__forceinline int32 CalculateSlackReserve(int32 NumElements, int32 NumBytesPerElement) const
		{
			return DefaultCalculateSlackReserve(NumElements, NumBytesPerElement, true);
		}

	private:
		ForAnyElementType(const ForAnyElementType&);
		ForAnyElementType& operator=(const ForAnyElementType&);

		FScriptContainerElement* Data;
	};
};

class FDefaultAllocator : public FHeapAllocator { public: typedef FHeapAllocator Typedef; };

// Containers/Array.h
template<typename InElementType, typename InAllocator = FDefaultAllocator>
class TArray
{
	template <typename OtherInElementType, typename OtherAllocator>
	friend class TArray;

public:
	typedef InElementType ElementType;
	typedef InAllocator   Allocator;

	__forceinline TArray()
		: ArrayNum(0)
		, ArrayMax(0)
	{}

	__forceinline TArray(const TArray& Other)
	{
		CopyToEmpty(Other.GetData(), Other.Num(), 0, 0);
	}

	TArray& operator=(const TArray& Other)
	{
		if (this != &Other)
		{
			DestructItems(GetData(), ArrayNum);
			CopyToEmpty(Other.GetData(), Other.Num(), ArrayMax, 0);
		}
		return *this;
	}

private:
	// The TCanMoveTArrayPointersBetweenArrayTypes form (same allocator and element type).
	template <typename FromArrayType, typename ToArrayType>
	static __forceinline void MoveOrCopy(ToArrayType& ToArray, FromArrayType& FromArray, int32 PrevMax)
	{
		ToArray.AllocatorInstance.MoveToEmpty(FromArray.AllocatorInstance);

		ToArray  .ArrayNum = FromArray.ArrayNum;
		ToArray  .ArrayMax = FromArray.ArrayMax;
		FromArray.ArrayNum = 0;
		FromArray.ArrayMax = 0;
	}

public:
	__forceinline TArray(TArray&& Other)
	{
		MoveOrCopy(*this, Other, 0);
	}

	TArray& operator=(TArray&& Other)
	{
		if (this != &Other)
		{
			DestructItems(GetData(), ArrayNum);
			MoveOrCopy(*this, Other, ArrayMax);
		}
		return *this;
	}

	~TArray()
	{
		DestructItems(GetData(), ArrayNum);

		// ensure that DebugGet gets instantiated (MSVC).
		volatile const ElementType* Dummy = &DebugGet(0);
	}

	__forceinline ElementType* GetData()
	{
		return (ElementType*)AllocatorInstance.GetAllocation();
	}

	__forceinline const ElementType* GetData() const
	{
		return (const ElementType*)AllocatorInstance.GetAllocation();
	}

	__forceinline int32 Num() const
	{
		return ArrayNum;
	}

	void Reset(int32 NewSize = 0)
	{
		// If we have space to hold the excepted size, then don't reallocate
		if (NewSize <= ArrayMax)
		{
			DestructItems(GetData(), ArrayNum);
			ArrayNum = 0;
		}
		else
		{
			Empty(NewSize);
		}
	}

	void Empty(int32 Slack = 0)
	{
		DestructItems(GetData(), ArrayNum);

		ArrayNum = 0;

		if (ArrayMax != Slack)
		{
			ResizeTo(Slack);
		}
	}

private:
	__declspec(noinline) const ElementType& DebugGet(int32 Index) const
	{
		return GetData()[Index];
	}

	__declspec(noinline) void ResizeTo(int32 NewMax)
	{
		if (NewMax)
		{
			NewMax = AllocatorInstance.CalculateSlackReserve(NewMax, sizeof(ElementType));
		}
		if (NewMax != ArrayMax)
		{
			ArrayMax = NewMax;
			AllocatorInstance.ResizeAllocation(ArrayNum, ArrayMax, sizeof(ElementType));
		}
	}

	__declspec(noinline) void ResizeForCopy(int32 NewMax, int32 PrevMax)
	{
		if (NewMax)
		{
			NewMax = AllocatorInstance.CalculateSlackReserve(NewMax, sizeof(ElementType));
		}
		if (NewMax != PrevMax)
		{
			AllocatorInstance.ResizeAllocation(0, NewMax, sizeof(ElementType));
		}
		ArrayMax = NewMax;
	}

	template <typename OtherElementType>
	void CopyToEmpty(const OtherElementType* OtherData, int32 OtherNum, int32 PrevMax, int32 ExtraSlack)
	{
		ArrayNum = OtherNum;
		if (OtherNum || ExtraSlack || PrevMax)
		{
			ResizeForCopy(OtherNum + ExtraSlack, PrevMax);
			ConstructItems<ElementType>(GetData(), OtherData, OtherNum);
		}
		else
		{
			ArrayMax = 0;
		}
	}

protected:
	typedef typename Allocator::ForAnyElementType ElementAllocatorType;  // FHeapAllocator: NeedsElementType is false

	ElementAllocatorType AllocatorInstance;
	int32	  ArrayNum;
	int32	  ArrayMax;
};

// Containers/UnrealString.h
class FString
{
private:
	/** Array holding the character data */
	typedef TArray<TCHAR> DataType;
	DataType Data;

public:
	FString() = default;
	FString(FString&&) = default;
	FString(const FString&) = default;
	FString& operator=(FString&&) = default;
	FString& operator=(const FString&) = default;

	__forceinline void Reset(int32 NewReservedSize = 0)
	{
		const int32 NewSizeIncludingTerminator = (NewReservedSize > 0) ? (NewReservedSize + 1) : 0;
		Data.Reset(NewSizeIncludingTerminator);
		if (TCHAR* DataPtr = Data.GetData())
		{
			*DataPtr = TEXT('\0');
		}
	}
};
