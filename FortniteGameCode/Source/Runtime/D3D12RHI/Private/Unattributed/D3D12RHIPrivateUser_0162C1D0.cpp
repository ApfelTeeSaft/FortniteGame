// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: D3D12RHI. The original .cpp file is not established: this unit holds the copies of
// D3D12RHIPrivate.h's file-static checks that one D3D12RHI translation unit kept, with adjacent
// thread-safe statics at 0x047C91F0 and 0x047C91F8.
// Reconstruction written from image evidence; see analysis/functions.json.

#include <windows.h>

#include "FortniteGameCode/RecoveryHarness.h"
#include "../D3D12RHIPrivate.h"

// D3D12RHI_ShouldCreateWithD3DDebug
// Original FortniteClient-Win64-Shipping.exe: RVA 0x0162C1D0 (end 0x0162C27F)
// Original VA: 0x000000014162C1D0 | File offset: 0x0162B7D0
// Recovery: high-confidence inferred (UE4 name, file-static) | Matching: see analysis/functions.json
// Evidence: a thread-safe static set from FParse::Param(FCommandLine::Get(), ...) over L"d3ddebug",
//   L"d3debug" and L"dxdebug"; one of two copies (the other is 0x0164F910).
//
// D3D12RHI_ShouldForceCompatibility
// Original FortniteClient-Win64-Shipping.exe: RVA 0x0162C280 (end 0x0162C314)
// Original VA: 0x000000014162C280 | File offset: 0x0162B880
// Recovery: high-confidence inferred (UE4 name, file-static) | Matching: see analysis/functions.json
// Evidence: the same over L"d3dcompat" and L"d3d12compat", used only here in the 4.20 tree; its
//   static directly follows the copy above's.

#if FNGC_MATCHING_HARNESS
FNGC_ANCHOR_TABLE(GFngcAnchors_D3D12RHIPrivateUser_0162C1D0)
{
	(const void*)&D3D12RHI_ShouldCreateWithD3DDebug,
	(const void*)&D3D12RHI_ShouldForceCompatibility,
};
#endif
