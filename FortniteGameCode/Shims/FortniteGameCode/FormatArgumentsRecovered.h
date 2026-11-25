// UE4.20 Core's named format arguments: Misc/Optional.h (TOptional), Internationalization/Text.h
// (EFormatArgumentType, FFormatArgumentValue, FFormatNamedArguments) and LocKeyFuncs.h
// (FLocKeyMapFuncs, only named). Member layout, the float constructor and destruction follow
// the 4.20 source. Not recovered code.
//
// Needs the real TSet (SetRecovered.h): a unit including this defines FNGC_SET_RECOVERED before
// the shim headers.
#pragma once

#include "FortniteGameCode/TextRecovered.h"
#include "FortniteGameCode/SetRecovered.h"

// Misc/Optional.h: construction and destruction.
template<typename OptionalType>
struct TOptional
{
public:
	/** Construct an OptionaType with no value; i.e. unset */
	TOptional()
		: bIsSet(false)
	{
	}

	~TOptional()
	{
		Reset();
	}

	void Reset()
	{
		if (bIsSet)
		{
			bIsSet = false;

			// We need a typedef here because VC won't compile the destructor call below if OptionalType itself has a member called OptionalType
			typedef OptionalType OptionalDestructOptionalType;
			((OptionalType*)&Value)->OptionalDestructOptionalType::~OptionalDestructOptionalType();
		}
	}

private:
	TTypeCompatibleBytes<OptionalType> Value;
	bool bIsSet;
};

// Internationalization/Text.h
namespace EFormatArgumentType
{
	enum Type
	{
		Int,
		UInt,
		Float,
		Double,
		Text,
		Gender,
		// Add new enum types at the end only! They are serialized by index.
	};
}

class FFormatArgumentValue
{
public:
	FFormatArgumentValue(const float Value)
		: Type(EFormatArgumentType::Float)
	{
		FloatValue = Value;
	}

private:
	EFormatArgumentType::Type Type;
	union
	{
		int64 IntValue;
		uint64 UIntValue;
		float FloatValue;
		double DoubleValue;
	};
	TOptional<FText> TextValue;
};

// Internationalization/LocKeyFuncs.h: case sensitive hashing for the map's FString keys.
template <typename ValueType>
struct FLocKeyMapFuncs;

typedef TMap<FString, FFormatArgumentValue, FDefaultSetAllocator, FLocKeyMapFuncs<FFormatArgumentValue>> FFormatNamedArguments;
