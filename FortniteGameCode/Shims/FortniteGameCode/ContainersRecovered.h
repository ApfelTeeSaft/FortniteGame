// UE4.20 Core containers as far as exec thunks use them: HAL/UnrealMemory.h (FMemory),
// Templates/MemoryOps.h, TypeCompatibleBytes.h, UnrealTemplate.h (IfAThenAElseB),
// Containers/ContainerAllocationPolicies.h (FHeapAllocator, FDefaultAllocator,
// TInlineAllocator), Containers/Array.h (TArray) and Containers/UnrealString.h (FString).
// Member layout, construction, copy, move, destruction and ResizeForCopy follow the 4.20
// source; everything else is left out. Not recovered code.
#pragma once

#include <string.h>
#include <new>   // placement new, as Core's headers include it
#include "FortniteGameCode/UE4CodeGenRecovered.h"

typedef unsigned char uint8;
typedef long long PTRINT;   // SSIZE_T on Win64

enum { DEFAULT_ALIGNMENT = 0 };
#define MAX_int32 ((int32)0x7fffffff)

// HAL/UnrealMemory.h. On Windows INLINE_FMEMORY_OPERATION is 0: these are out of line in Core.
struct FMemory
{
	static __forceinline void* Memcpy(void* Dest, const void* Src, SIZE_T Count)
	{
		return memcpy(Dest, Src, Count);  // FGenericPlatformMemory::Memcpy
	}

	static __forceinline void* Memmove(void* Dest, const void* Src, SIZE_T Count)
	{
		return memmove(Dest, Src, Count);  // FGenericPlatformMemory::Memmove
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

template <typename A, typename B>
struct TAreTypesEqual
{
	enum { Value = false };
};

template <typename A>
struct TAreTypesEqual<A, A>
{
	enum { Value = true };
};

// Templates/ChooseClass.h
template<bool Predicate,typename TrueClass,typename FalseClass>
class TChooseClass;

template<typename TrueClass,typename FalseClass>
class TChooseClass<true,TrueClass,FalseClass>
{
public:
	typedef TrueClass Result;
};

template<typename TrueClass,typename FalseClass>
class TChooseClass<false,TrueClass,FalseClass>
{
public:
	typedef FalseClass Result;
};

// Templates/UnrealTemplate.h
template<typename ReferencedType>
__forceinline ReferencedType* IfAThenAElseB(ReferencedType* A,ReferencedType* B)
{
	const PTRINT IntA = reinterpret_cast<PTRINT>(A);
	const PTRINT IntB = reinterpret_cast<PTRINT>(B);

	// Compute a mask which has all bits set if IntA is zero, and no bits set if it's non-zero.
	const PTRINT MaskB = -(!IntA);

	return reinterpret_cast<ReferencedType*>(IntA | (MaskB & IntB));
}

// Templates/RemoveReference.h and UnrealTemplate.h (MoveTemp)
template <typename T> struct TRemoveReference      { typedef T Type; };
template <typename T> struct TRemoveReference<T& > { typedef T Type; };
template <typename T> struct TRemoveReference<T&&> { typedef T Type; };

#if FNGC_CORE_MATH_EXTRAS   // MathDecls.h
// Templates/UnrealTemplate.h
template <typename T>
__forceinline T&& Forward(typename TRemoveReference<T>::Type& Obj)
{
	return (T&&)Obj;
}

template <typename T>
__forceinline T&& Forward(typename TRemoveReference<T>::Type&& Obj)
{
	return (T&&)Obj;
}
#endif

template <typename T>
__forceinline typename TRemoveReference<T>::Type&& MoveTemp(T&& Obj)
{
	typedef typename TRemoveReference<T>::Type CastType;
	return (CastType&&)Obj;
}

// Templates/TypeCompatibleBytes.h
template<int32 Size,uint32 Alignment>
struct TAlignedBytes; // this intentionally won't compile, we don't support the requested alignment

/** Unaligned storage. */
template<int32 Size>
struct TAlignedBytes<Size,1>
{
	uint8 Pad[Size];
};

/** A macro that implements TAlignedBytes for a specific alignment. */
#define IMPLEMENT_ALIGNED_STORAGE(Align) \
	template<int32 Size>        \
	struct TAlignedBytes<Size,Align> \
	{ \
		struct __declspec(align(Align)) TPadding \
		{ \
			uint8 Pad[Size]; \
		}; \
		TPadding Padding; \
	};

// Implement TAlignedBytes for these alignments.
IMPLEMENT_ALIGNED_STORAGE(16);
IMPLEMENT_ALIGNED_STORAGE(8);
IMPLEMENT_ALIGNED_STORAGE(4);
IMPLEMENT_ALIGNED_STORAGE(2);

#undef IMPLEMENT_ALIGNED_STORAGE

/** An untyped array of data with compile-time alignment and size derived from another type. */
template<typename ElementType>
struct TTypeCompatibleBytes :
	public TAlignedBytes<
		sizeof(ElementType),
		alignof(ElementType)
		>
{};

// Templates/UnrealTemplate.h: Swap for class types (TUseBitwiseSwap; the register-type form
// is not modelled).
template <typename T>
inline void Swap(T& A, T& B)
{
	static_assert(!__is_enum(T), "only class types are swapped here (TUseBitwiseSwap)");
	if ((&A != &B))   // LIKELY() is empty on MSVC
	{
		TTypeCompatibleBytes<T> Temp;
		FMemory::Memcpy(&Temp, &A, sizeof(T));
		FMemory::Memcpy(&A, &B, sizeof(T));
		FMemory::Memcpy(&B, &Temp, sizeof(T));
	}
}

// The register-type form (!TUseBitwiseSwap: arithmetic, pointer and enum types), for float.
inline void Swap(float& A, float& B)
{
	float Temp = MoveTemp(A);
	A = MoveTemp(B);
	B = MoveTemp(Temp);
}

// Templates/MemoryOps.h
namespace UE4MemoryOps_Private
{
	template <typename DestinationElementType, typename SourceElementType>
	struct TCanBitwiseRelocate
	{
		enum
		{
			Value =
				TAreTypesEqual<DestinationElementType, SourceElementType>::Value ||
				(TIsBitwiseConstructible<DestinationElementType, SourceElementType>::Value &&
				 TIsTriviallyDestructible<SourceElementType>::Value)
		};
	};
}

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

template <typename DestinationElementType, typename SourceElementType>
__forceinline typename TEnableIf<!UE4MemoryOps_Private::TCanBitwiseRelocate<DestinationElementType, SourceElementType>::Value>::Type RelocateConstructItems(void* Dest, const SourceElementType* Source, int32 Count)
{
	while (Count)
	{
		// We need a typedef here because VC won't compile the destructor call below if SourceElementType itself has a member called SourceElementType
		typedef SourceElementType RelocateConstructItemsElementTypeTypedef;

		new (Dest) DestinationElementType(*Source);
		++(DestinationElementType*&)Dest;
		(Source++)->RelocateConstructItemsElementTypeTypedef::~RelocateConstructItemsElementTypeTypedef();
		--Count;
	}
}

template <typename DestinationElementType, typename SourceElementType>
__forceinline typename TEnableIf<UE4MemoryOps_Private::TCanBitwiseRelocate<DestinationElementType, SourceElementType>::Value>::Type RelocateConstructItems(void* Dest, const SourceElementType* Source, int32 Count)
{
	FMemory::Memmove(Dest, Source, sizeof(SourceElementType) * Count);
}

// Containers/ContainerAllocationPolicies.h
#if FNGC_CORE_MATH_EXTRAS   // MathDecls.h
__forceinline int32 DefaultCalculateSlackGrow(int32 NumElements, int32 NumAllocatedElements, SIZE_T BytesPerElement, bool bAllowQuantize, uint32 Alignment = DEFAULT_ALIGNMENT)
{
	int32 Retval;
	// checkSlow(NumElements > NumAllocatedElements && NumElements > 0) is compiled out.

	SIZE_T Grow = 4; // this is the amount for the first alloc
	if (NumAllocatedElements || SIZE_T(NumElements) > Grow)
	{
		// Allocate slack for the array proportional to its size.
		Grow = SIZE_T(NumElements) + 3 * SIZE_T(NumElements) / 8 + 16;
	}
	if (bAllowQuantize)
	{
		Retval = FMemory::QuantizeSize(Grow * BytesPerElement, Alignment) / BytesPerElement;
	}
	else
	{
		Retval = Grow;
	}
	// NumElements and MaxElements are stored in 32 bit signed integers so we must be careful not to overflow here.
	if (NumElements > Retval)
	{
		Retval = MAX_int32;
	}

	return Retval;
}
#endif

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
#if FNGC_CORE_MATH_EXTRAS   // MathDecls.h
		__forceinline int32 CalculateSlackGrow(int32 NumElements, int32 NumAllocatedElements, int32 NumBytesPerElement) const
		{
			return DefaultCalculateSlackGrow(NumElements, NumAllocatedElements, NumBytesPerElement, true);
		}
#endif

	private:
		ForAnyElementType(const ForAnyElementType&);
		ForAnyElementType& operator=(const ForAnyElementType&);

		FScriptContainerElement* Data;
	};

	template<typename ElementType>
	class ForElementType : public ForAnyElementType
	{
	public:

		/** Default constructor. */
		ForElementType()
		{}

		__forceinline ElementType* GetAllocation() const
		{
			return (ElementType*)ForAnyElementType::GetAllocation();
		}
	};
};

class FDefaultAllocator : public FHeapAllocator { public: typedef FHeapAllocator Typedef; };

template <uint32 NumInlineElements, typename SecondaryAllocator = FDefaultAllocator>
class TInlineAllocator
{
public:

	enum { NeedsElementType = true };
	enum { RequireRangeCheck = true };

	template<typename ElementType>
	class ForElementType
	{
	public:

		/** Default constructor. */
		ForElementType()
		{
		}

		__forceinline void MoveToEmpty(ForElementType& Other)
		{
			if (!Other.SecondaryData.GetAllocation())
			{
				// Relocate objects from other inline storage only if it was stored inline in Other
				RelocateConstructItems<ElementType>((void*)InlineData, Other.GetInlineElements(), NumInlineElements);
			}

			// Move secondary storage in any case.
			// This will move secondary storage if it exists but will also handle the case where secondary storage is used in Other but not in *this.
			SecondaryData.MoveToEmpty(Other.SecondaryData);
		}

		__forceinline ElementType* GetAllocation() const
		{
			return IfAThenAElseB<ElementType>(SecondaryData.GetAllocation(),GetInlineElements());
		}

		void ResizeAllocation(int32 PreviousNumElements,int32 NumElements,SIZE_T NumBytesPerElement)
		{
			// Check if the new allocation will fit in the inline data area.
			if(NumElements <= NumInlineElements)
			{
				// If the old allocation wasn't in the inline data area, relocate it into the inline data area.
				if(SecondaryData.GetAllocation())
				{
					RelocateConstructItems<ElementType>((void*)InlineData, (ElementType*)SecondaryData.GetAllocation(), PreviousNumElements);

					// Free the old indirect allocation.
					SecondaryData.ResizeAllocation(0,0,NumBytesPerElement);
				}
			}
			else
			{
				if(!SecondaryData.GetAllocation())
				{
					// Allocate new indirect memory for the data.
					SecondaryData.ResizeAllocation(0,NumElements,NumBytesPerElement);

					// Move the data out of the inline data area into the new allocation.
					RelocateConstructItems<ElementType>((void*)SecondaryData.GetAllocation(), GetInlineElements(), PreviousNumElements);
				}
				else
				{
					// Reallocate the indirect data for the new size.
					SecondaryData.ResizeAllocation(PreviousNumElements, NumElements, NumBytesPerElement);
				}
			}
		}

		__forceinline int32 CalculateSlackReserve(int32 NumElements, SIZE_T NumBytesPerElement) const
		{
			// If the elements use less space than the inline allocation, only use the inline allocation as slack.
			return NumElements <= NumInlineElements ?
				NumInlineElements :
				SecondaryData.CalculateSlackReserve(NumElements, NumBytesPerElement);
		}

	private:
		ForElementType(const ForElementType&);
		ForElementType& operator=(const ForElementType&);

		/** The data is stored in this array if less than NumInlineElements is needed. */
		TTypeCompatibleBytes<ElementType> InlineData[NumInlineElements];

		/** The data is allocated through the indirect allocation policy if more than NumInlineElements is needed. */
		typename SecondaryAllocator::template ForElementType<ElementType> SecondaryData;

		/** @return the base of the aligned inline element data */
		ElementType* GetInlineElements() const
		{
			return (ElementType*)InlineData;
		}
	};

	typedef void ForAnyElementType;
};

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

	// RangeCheck is checkSlow, compiled out in shipping.
	__forceinline ElementType& operator[](int32 Index)
	{
		return GetData()[Index];
	}

	__forceinline const ElementType& operator[](int32 Index) const
	{
		return GetData()[Index];
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

#if FNGC_CORE_MATH_EXTRAS   // MathDecls.h
	__forceinline int32 AddUninitialized(int32 Count = 1)
	{
		const int32 OldNum = ArrayNum;
		if ((ArrayNum += Count) > ArrayMax)
		{
			ResizeGrow(OldNum);
		}
		return OldNum;
	}

	template <typename... ArgsType>
	__forceinline int32 Emplace(ArgsType&&... Args)
	{
		const int32 Index = AddUninitialized(1);
		new(GetData() + Index) ElementType(Forward<ArgsType>(Args)...);
		return Index;
	}

	__forceinline int32 Add(ElementType&& Item) { return Emplace(MoveTemp(Item)); }
	__forceinline int32 Add(const ElementType& Item) { return Emplace(Item); }
#endif

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

#if FNGC_CORE_MATH_EXTRAS   // MathDecls.h
	__declspec(noinline) void ResizeGrow(int32 OldNum)
	{
		ArrayMax = AllocatorInstance.CalculateSlackGrow(ArrayNum, ArrayMax, sizeof(ElementType));
		AllocatorInstance.ResizeAllocation(OldNum, ArrayMax, sizeof(ElementType));
	}
#endif

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
	typedef typename TChooseClass<
		Allocator::NeedsElementType,
		typename Allocator::template ForElementType<ElementType>,
		typename Allocator::ForAnyElementType
		>::Result ElementAllocatorType;

	ElementAllocatorType AllocatorInstance;
	int32	  ArrayNum;
	int32	  ArrayMax;
};

#if FNGC_CORE_MATH_EXTRAS   // MathDecls.h
// GenericPlatform/GenericPlatformString.h: the TCHAR to TCHAR conversion, a copy. Memcpy is out
// of line in Core (GenericPlatformString.cpp), private to the class.
struct FGenericPlatformString
{
	template <typename DestEncoding, typename SourceEncoding>
	static __forceinline int32 ConvertedLength(const SourceEncoding* Src, int32 SrcSize)
	{
		return SrcSize;
	}

	template <typename SourceEncoding, typename DestEncoding>
	static __forceinline DestEncoding* Convert(DestEncoding* Dest, int32 DestSize, const SourceEncoding* Src, int32 SrcSize, DestEncoding BogusChar = (DestEncoding)'?')
	{
		if (DestSize < SrcSize)
		{
			return nullptr;
		}

		return (DestEncoding*)Memcpy(Dest, Src, SrcSize * sizeof(SourceEncoding)) + SrcSize;
	}

private:
	/**
	 * Forwarding function because we can't call FMemory::Memcpy directly due to #include ordering issues.
	 *
	 * @param Dest  The destination buffer.
	 * @param Src   The source buffer.
	 * @param Count The number of bytes to copy.
	 *
	 * @return Dest
	 */
	static void* Memcpy(void* Dest, const void* Src, SIZE_T Count);
};

// Microsoft/MicrosoftPlatformString.h (Strlen), Windows/WindowsPlatformString.h
struct FWindowsPlatformString : public FGenericPlatformString
{
	static __forceinline int32 Strlen( const TCHAR* String )
	{
		return (int32)wcslen( String );
	}
};
typedef FWindowsPlatformString FPlatformString;
#endif

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

#if FNGC_CORE_MATH_EXTRAS   // MathDecls.h
	// The 4.20 template for any character type, for TCHAR: TCString<TCHAR>::Strlen is wcslen.
	__forceinline FString(const TCHAR* Src)
	{
		if (Src && *Src)
		{
			int32 SrcLen  = FPlatformString::Strlen(Src) + 1;
			int32 DestLen = FPlatformString::ConvertedLength<TCHAR>(Src, SrcLen);
			Data.AddUninitialized(DestLen);

			FPlatformString::Convert(Data.GetData(), DestLen, Src, SrcLen);
		}
	}
#endif

	__forceinline const TCHAR* operator*() const
	{
		return Data.Num() ? Data.GetData() : TEXT("");
	}

	template <typename FmtType, typename... Types>
	static FString Printf(const FmtType& Fmt, Types... Args)
	{
		return PrintfImpl(Fmt, Args...);
	}

private:
	static FString __cdecl PrintfImpl(const TCHAR* Fmt, ...);   // CORE_API, Containers/String.cpp

public:

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
