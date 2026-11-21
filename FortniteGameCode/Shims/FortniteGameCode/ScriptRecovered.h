// ABI declarations for UHT exec thunks (UE4.20 Core/CoreUObject: Misc/OutputDevice.h,
// UObject/Stack.h, UObject/ScriptMacros.h, UObject/CoreNet.h). Not recovered code.
#pragma once

#include "FortniteGameCode/UE4CodeGenRecovered.h"

// Windows/WindowsPlatform.h: UE4.20 disables this for all code (void thunks never read
// Z_Param__Result).
#pragma warning(disable : 4100) // unreferenced formal parameter

typedef unsigned char uint8;

class UProperty;

// Misc/OutputDevice.h: the polymorphic base of FFrame (vptr, then two flags).
class FOutputDevice
{
public:
	virtual ~FOutputDevice();
protected:
	bool bSuppressEventTag;
	bool bAutoEmitLineTerminator;
};

// UObject/Stack.h. Members are declared up to the ones the thunks use, at their 4.20
// offsets (Node 0x10, Object 0x18, Code 0x20); the rest of the frame is not modelled.
struct FFrame : public FOutputDevice
{
public:
	UFunction* Node;
	UObject* Object;
	uint8* Code;
	uint8* Locals;
	UProperty* MostRecentProperty;
	uint8* MostRecentPropertyAddress;
};

// UObject/ScriptMacros.h (shipping: no script native timer).
#define P_FINISH Stack.Code += !!Stack.Code; /* increment the code ptr unless it is null */
#define P_THIS_CAST(ClassType) ((ClassType*)Context)
#define P_THIS P_THIS_CAST(ThisClass)
#define P_NATIVE_BEGIN {
#define P_NATIVE_END }

// UObject/CoreNet.h
void RPC_ValidateFailed(const TCHAR* Reason);
