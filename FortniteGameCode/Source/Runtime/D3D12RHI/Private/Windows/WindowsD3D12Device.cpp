// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: D3D12RHI (Windows). Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/D3D12RHI/Private/Windows/WindowsD3D12Device.cpp.
// Reconstruction written from image evidence; see analysis/functions.json.

#include <windows.h>
#include <delayimp.h>
#include <dxgi1_4.h>

#include "FortniteGameCode/RecoveryHarness.h"

static bool IsDelayLoadException(PEXCEPTION_POINTERS ExceptionPointers)
{
	switch (ExceptionPointers->ExceptionRecord->ExceptionCode)
	{
	case VcppException(ERROR_SEVERITY_ERROR, ERROR_MOD_NOT_FOUND):
	case VcppException(ERROR_SEVERITY_ERROR, ERROR_PROC_NOT_FOUND):
		return EXCEPTION_EXECUTE_HANDLER;
	default:
		return EXCEPTION_CONTINUE_SEARCH;
	}
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x0165FEB0 (end 0x0165FECA)
// Original VA: 0x000000014165FEB0 | File offset: 0x0165F4B0
// Recovery: low-confidence inferred (owner not confirmed) | Matching: unknown, body encrypted on disk
// Evidence: unwind and scope layout are identical to SafeCreateDXGIFactory at 0x016138D0, and
//   its filter was ICF-folded into 0x02DAE780. Public 4.20.0 also sets
//   bIsQuadBufferStereoEnabled here, which would not fit in the 17-byte guarded range.
//   The D3D12 assignment is unconfirmed; nothing ties this parent to D3D12RHI yet.
static void SafeCreateDXGIFactory(IDXGIFactory4** DXGIFactory)
{
	__try
	{
		CreateDXGIFactory(__uuidof(IDXGIFactory4), (void**)DXGIFactory);
	}
	__except (IsDelayLoadException(GetExceptionInformation()))
	{
	}
}

#if FNGC_MATCHING_HARNESS
FNGC_ANCHOR_TABLE(GFngcAnchors_WindowsD3D12Device)
{
	(const void*)&SafeCreateDXGIFactory,
};
#endif
