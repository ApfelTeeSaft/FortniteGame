// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: D3D11RHI (Windows). Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/Windows/D3D11RHI/Private/Windows/WindowsD3D11Device.cpp.
// The functions below are reconstructions written against evidence from the
// reference image (unwind records, SEH scope tables, filter funclet bytes). They
// are not a copy of the engine file. See analysis/functions.json for status.
// Compiled through ../../Module.D3D11RHI.cpp, as UnrealBuildTool's unity build did.

#include "D3D11RHIRecoveredPrivate.h"

extern bool D3D11RHI_ShouldCreateWithD3DDebug();

// SEH filter used by the delay-load guarded calls below. It is always inlined
// into the compiler-generated filter funclets; there is no standalone copy.
// The bool return type is original: the funclets materialize it with SETBE.
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

// Original FortniteClient-Win64-Shipping.exe: RVA 0x016138D0 (end 0x016138EA)
// Original VA: 0x00000001416138D0 | File offset: 0x01612ED0
// Recovery: high-confidence inferred (UE4 name) | Matching: unknown, body encrypted on disk
// Evidence: unwind ALLOC_SMALL 0x38; one C scope [+0x04,+0x15) -> filter 0x02DAE780.
//   A 17-byte guarded range fits only the single factory call. Public 4.20.0 also parses
//   -quad_buffer_stereo here; that code cannot fit, so the CL 3889387 fork predates it.
static void SafeCreateDXGIFactory(IDXGIFactory1** DXGIFactory1)
{
	__try
	{
		CreateDXGIFactory1(__uuidof(IDXGIFactory1), (void**)DXGIFactory1);
	}
	__except (IsDelayLoadException(GetExceptionInformation()))
	{
	}
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x016138F0 (end 0x01613A2E)
// Original VA: 0x00000001416138F0 | File offset: 0x01612EF0
// Recovery: high-confidence inferred (UE4 name) | Matching: unknown, body encrypted on disk
// Evidence: unwind saves rbx/rsi, pushes rdi/r14/r15, ALLOC_SMALL 0x70; one C scope
//   [+0xBD,+0x126) -> filter funclet 0x02DAE750 (frame slots +0x68/+0x50). This
//   reconstruction reproduces the 0x13E size, every unwind code, the handler kind and the
//   scope offsets under the global /GS switch only when (a) D3D11RHI_ShouldCreateWithD3DDebug
//   is inlined (unity build) and (b) the request list has two levels. Public 4.20.0 lists
//   11_1 first; three elements make the array a /GS buffer and change all four facts.
static bool SafeTestD3D11CreateDevice(IDXGIAdapter* Adapter, D3D_FEATURE_LEVEL MaxFeatureLevel, D3D_FEATURE_LEVEL* OutFeatureLevel)
{
	ID3D11Device* D3DDevice = NULL;
	ID3D11DeviceContext* D3DDeviceContext = NULL;
	unsigned int DeviceFlags = D3D11_CREATE_DEVICE_SINGLETHREADED;

	if (D3D11RHI_ShouldCreateWithD3DDebug())
	{
		DeviceFlags |= D3D11_CREATE_DEVICE_DEBUG;
	}

	D3D_FEATURE_LEVEL RequestedFeatureLevels[] =
	{
		D3D_FEATURE_LEVEL_11_0,
		D3D_FEATURE_LEVEL_10_0
	};

	int FirstAllowedFeatureLevel = 0;
	int NumAllowedFeatureLevels = sizeof(RequestedFeatureLevels) / sizeof(RequestedFeatureLevels[0]);
	while (FirstAllowedFeatureLevel < NumAllowedFeatureLevels)
	{
		if (RequestedFeatureLevels[FirstAllowedFeatureLevel] == MaxFeatureLevel)
		{
			break;
		}
		FirstAllowedFeatureLevel++;
	}
	NumAllowedFeatureLevels -= FirstAllowedFeatureLevel;

	if (NumAllowedFeatureLevels == 0)
	{
		return false;
	}

	__try
	{
		if (SUCCEEDED(D3D11CreateDevice(Adapter, D3D_DRIVER_TYPE_UNKNOWN, NULL, DeviceFlags,
			&RequestedFeatureLevels[FirstAllowedFeatureLevel], NumAllowedFeatureLevels,
			D3D11_SDK_VERSION, &D3DDevice, OutFeatureLevel, &D3DDeviceContext)))
		{
			D3DDevice->Release();
			D3DDeviceContext->Release();
			return true;
		}
	}
	__except (IsDelayLoadException(GetExceptionInformation()))
	{
	}

	return false;
}

// Compiler-generated SEH filter funclets of the two functions above:
//   0x02DAE780 (end 0x02DAE7AA): filter of SafeCreateDXGIFactory. /OPT:ICF also folded the
//     identical filter of a second parent at RVA 0x0165FEB0 into this copy.
//   0x02DAE750 (end 0x02DAE77A): filter of SafeTestD3D11CreateDevice.
// compare.py checks them against the funclets the compiler emits for the code above.

#if FNGC_MATCHING_HARNESS
FNGC_ANCHOR_TABLE(GFngcAnchors_WindowsD3D11Device)
{
	(const void*)&SafeCreateDXGIFactory,
	(const void*)&SafeTestD3D11CreateDevice,
};
#endif
