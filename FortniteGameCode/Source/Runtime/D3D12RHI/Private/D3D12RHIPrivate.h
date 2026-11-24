// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: D3D12RHI. Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/D3D12RHI/Private/D3D12RHIPrivate.h.
// Reconstruction written from image evidence; see analysis/functions.json.
//
// File-static command-line checks the header defines in every D3D12RHI translation unit. A unit
// emits only those it uses, so each recovered unit lists the ones the reference holds in its
// anchor table. Their thread-safe statics follow this order within a unit.
#pragma once

#include "FortniteGameCode/EngineDecls.h"

// A unit keeps only the checks it uses; the rest are removed unreferenced.
#pragma warning(disable: 4505)

static bool D3D12RHI_ShouldCreateWithD3DDebug()
{
	// Use a debug device if specified on the command line.
	static bool bCreateWithD3DDebug =
		FParse::Param(FCommandLine::Get(), TEXT("d3ddebug")) ||
		FParse::Param(FCommandLine::Get(), TEXT("d3debug")) ||
		FParse::Param(FCommandLine::Get(), TEXT("dxdebug"));
	return bCreateWithD3DDebug;
}

static bool D3D12RHI_ShouldCreateWithWarp()
{
	// Use the warp adapter if specified on the command line.
	static bool bCreateWithWarp = FParse::Param(FCommandLine::Get(), TEXT("warp"));
	return bCreateWithWarp;
}

static bool D3D12RHI_ShouldForceCompatibility()
{
	// Suppress the use of newer D3D12 features.
	static bool bForceCompatibility =
		FParse::Param(FCommandLine::Get(), TEXT("d3dcompat")) ||
		FParse::Param(FCommandLine::Get(), TEXT("d3d12compat"));
	return bForceCompatibility;
}
