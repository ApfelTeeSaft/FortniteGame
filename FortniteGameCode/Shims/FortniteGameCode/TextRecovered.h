// UE4.20 types exec thunks pass besides containers: Templates/SharedPointerInternals.h and
// SharedPointer.h (TSharedRef's members and its thread-safe release),
// Windows/WindowsPlatformAtomics.h, Internationalization/Text.h (FText) and
// Templates/SubclassOf.h (TSubclassOf). Member layout and the members thunks use follow the
// 4.20 source; everything else is left out. Not recovered code.
#pragma once

#include "FortniteGameCode/UE4CodeGenRecovered.h"
#include "FortniteGameCode/ContainersRecovered.h"   // MoveTemp, Swap

// The one intrinsic used, declared as MSVC documents instead of including <intrin.h>:
// including that header changed the order in which MSVC emitted other functions' static
// locals (StaticEnum singletons) in every unit, breaking layout predictions that hold without it.
extern "C" long _InterlockedDecrement(long volatile* Addend);
#pragma intrinsic(_InterlockedDecrement)

class UClass;

// Windows/WindowsPlatformAtomics.h
struct FWindowsPlatformAtomics
{
	static __forceinline int32 InterlockedDecrement(volatile int32* Value)
	{
		return (int32)::_InterlockedDecrement((long*)Value);
	}
};
typedef FWindowsPlatformAtomics FPlatformAtomics;

// Templates/SharedPointerInternals.h
enum class ESPMode
{
	NotThreadSafe = 0,
	Fast = 0,          // FORCE_THREADSAFE_SHAREDPTRS is 0 on Windows
	ThreadSafe = 1
};

namespace SharedPointerInternals
{
	struct FNullTag {};

	class FReferenceControllerBase
	{
	public:
		__forceinline explicit FReferenceControllerBase()
			: SharedReferenceCount(1)
			, WeakReferenceCount(1)
		{
		}

		int32 SharedReferenceCount;
		int32 WeakReferenceCount;

		virtual void DestroyObject() = 0;

		virtual ~FReferenceControllerBase()
		{
		}

	private:
		FReferenceControllerBase( FReferenceControllerBase const& );
		FReferenceControllerBase& operator=( FReferenceControllerBase const& );
	};

	template <ESPMode Mode>
	struct FReferenceControllerOps;

	template <>
	struct FReferenceControllerOps<ESPMode::NotThreadSafe>
	{
		static __forceinline void AddSharedReference(FReferenceControllerBase* ReferenceController)
		{
			++ReferenceController->SharedReferenceCount;
		}

		static __forceinline void ReleaseSharedReference(FReferenceControllerBase* ReferenceController)
		{
			if( --ReferenceController->SharedReferenceCount == 0 )
			{
				// Last shared reference was released!  Destroy the referenced object.
				ReferenceController->DestroyObject();

				// No more shared referencers, so decrement the weak reference count by one.  When the weak
				// reference count reaches zero, this object will be deleted.
				ReleaseWeakReference(ReferenceController);
			}
		}

		static void ReleaseWeakReference(FReferenceControllerBase* ReferenceController)
		{
			if( --ReferenceController->WeakReferenceCount == 0 )
			{
				// No more references to this reference count.  Destroy it!
				delete ReferenceController;
			}
		}
	};

	template <>
	struct FReferenceControllerOps<ESPMode::ThreadSafe>
	{
		static __forceinline void ReleaseSharedReference(FReferenceControllerBase* ReferenceController)
		{
			if( FPlatformAtomics::InterlockedDecrement( &ReferenceController->SharedReferenceCount ) == 0 )
			{
				// Last shared reference was released!  Destroy the referenced object.
				ReferenceController->DestroyObject();

				// No more shared referencers, so decrement the weak reference count by one.  When the weak
				// reference count reaches zero, this object will be deleted.
				ReleaseWeakReference(ReferenceController);
			}
		}

		static void ReleaseWeakReference(FReferenceControllerBase* ReferenceController)
		{
			if( FPlatformAtomics::InterlockedDecrement( &ReferenceController->WeakReferenceCount ) == 0 )
			{
				// No more references to this reference count.  Destroy it!
				delete ReferenceController;
			}
		}
	};

	template< ESPMode Mode >
	class FSharedReferencer
	{
		typedef FReferenceControllerOps<Mode> TOps;

	public:
		/** Constructor for an empty shared referencer object */
		__forceinline FSharedReferencer()
			: ReferenceController( nullptr )
		{ }

		/** Copy constructor creates a new reference to the existing object */
		__forceinline FSharedReferencer( FSharedReferencer const& InSharedReference )
			: ReferenceController( InSharedReference.ReferenceController )
		{
			// If the incoming reference had an object associated with it, then go ahead and increment the
			// shared reference count
			if( ReferenceController != nullptr )
			{
				TOps::AddSharedReference(ReferenceController);
			}
		}

		/** Move constructor creates no new references */
		__forceinline FSharedReferencer( FSharedReferencer&& InSharedReference )
			: ReferenceController( InSharedReference.ReferenceController )
		{
			InSharedReference.ReferenceController = nullptr;
		}

		__forceinline ~FSharedReferencer()
		{
			if( ReferenceController != nullptr )
			{
				// Tell the reference counter object that we're no longer referencing the object with
				// this shared pointer
				TOps::ReleaseSharedReference(ReferenceController);
			}
		}

		/** Assignment operator adds a reference to the assigned object.  If this counter was previously
		    referencing an object, that reference will be released. */
		inline FSharedReferencer& operator=( FSharedReferencer const& InSharedReference )
		{
			// Make sure we're not be reassigned to ourself!
			auto NewReferenceController = InSharedReference.ReferenceController;
			if( NewReferenceController != ReferenceController )
			{
				// First, add a shared reference to the new object
				if( NewReferenceController != nullptr )
				{
					TOps::AddSharedReference(NewReferenceController);
				}

				// Release shared reference to the old object
				if( ReferenceController != nullptr )
				{
					TOps::ReleaseSharedReference(ReferenceController);
				}

				// Assume ownership of the assigned reference counter
				ReferenceController = NewReferenceController;
			}

			return *this;
		}

		/** Move assignment operator adds no references to the assigned object.  If this counter was previously
		    referencing an object, that reference will be released. */
		inline FSharedReferencer& operator=( FSharedReferencer&& InSharedReference )
		{
			// Make sure we're not be reassigned to ourself!
			auto NewReferenceController = InSharedReference.ReferenceController;
			auto OldReferenceController = ReferenceController;
			if( NewReferenceController != OldReferenceController )
			{
				// Assume ownership of the assigned reference counter
				InSharedReference.ReferenceController = nullptr;
				ReferenceController                   = NewReferenceController;

				// Release shared reference to the old object
				if( OldReferenceController != nullptr )
				{
					TOps::ReleaseSharedReference(OldReferenceController);
				}
			}

			return *this;
		}

	private:
		FReferenceControllerBase* ReferenceController;
	};
}

// Templates/SharedPointer.h: TSharedRef's members only (FText's copies are out of line).
template< class ObjectType, ESPMode Mode = ESPMode::Fast >
class TSharedRef
{
private:
	ObjectType* Object;
	SharedPointerInternals::FSharedReferencer< Mode > SharedReferenceCount;
};

// Templates/SharedPointer.h: empty construction, copy, move, assignment and destruction.
template< class ObjectType, ESPMode Mode = ESPMode::Fast >
class TSharedPtr
{
public:
	__forceinline TSharedPtr( SharedPointerInternals::FNullTag* = nullptr )
		: Object( nullptr )
		, SharedReferenceCount()
	{ }

	__forceinline TSharedPtr( TSharedPtr const& InSharedPtr )
		: Object( InSharedPtr.Object )
		, SharedReferenceCount( InSharedPtr.SharedReferenceCount )
	{ }

	__forceinline TSharedPtr( TSharedPtr&& InSharedPtr )
		: Object( InSharedPtr.Object )
		, SharedReferenceCount( MoveTemp(InSharedPtr.SharedReferenceCount) )
	{
		InSharedPtr.Object = nullptr;
	}

	/**
	 * Assignment operator replaces this shared pointer with the specified shared pointer.  The object
	 * currently referenced by this shared pointer will no longer be referenced and will be deleted if
	 * there are no other referencers.
	 */
	__forceinline TSharedPtr& operator=( TSharedPtr const& InSharedPtr )
	{
		TSharedPtr Temp = InSharedPtr;
		Swap(Temp, *this);
		return *this;
	}

	__forceinline TSharedPtr& operator=( TSharedPtr&& InSharedPtr )
	{
		if (this != &InSharedPtr)
		{
			Object = InSharedPtr.Object;
			InSharedPtr.Object = nullptr;
			SharedReferenceCount = MoveTemp(InSharedPtr.SharedReferenceCount);
		}
		return *this;
	}

private:
	ObjectType* Object;
	SharedPointerInternals::FSharedReferencer< Mode > SharedReferenceCount;
};

// Internationalization/Text.h: construction, copy and move are out of line in Core.
class ITextData;

class FText
{
public:
	FText();
	FText( const FText& Source );
	FText(FText&& Source);
	FText& operator=(const FText& Source);
	FText& operator=(FText&& Source);

private:
	TSharedRef<ITextData, ESPMode::ThreadSafe> TextData;
	uint32 Flags;
};

// UObject/Class.h: UStruct::IsChildOf (USTRUCT_FAST_ISCHILDOF_IMPL is USTRUCT_ISCHILDOF_OUTERWALK)
// walks UStruct::SuperStruct, at 0x30 after UField. The generated class bodies are opaque, so
// the walk reads the member at that offset.
template <typename TStruct>
__forceinline bool FngcStructIsChildOf(const TStruct* This, const TStruct* SomeBase)
{
	for (const TStruct* Struct = This; Struct; Struct = *(const TStruct* const*)((const char*)Struct + 0x30))
	{
		if (Struct == SomeBase)
			return true;
	}

	return false;
}

// Templates/SubclassOf.h: construction and the checked dereference.
template<class TClass>
class TSubclassOf
{
	template <class TClassA>
	friend class TSubclassOf;

public:
	/** Default Constructor, defaults to null */
	__forceinline TSubclassOf() :
		Class(nullptr)
	{
	}

	/** Constructor that takes a UClass and does a runtime check to make sure this is a compatible class */
	__forceinline TSubclassOf(UClass* From) :
		Class(From)
	{
	}

	/** Dereference back into a UClass*, does runtime type checking. */
	__forceinline UClass* operator*() const
	{
		if (!Class || !FngcStructIsChildOf(Class, TClass::StaticClass()))
		{
			return nullptr;
		}
		return Class;
	}

private:
	UClass* Class;
};
