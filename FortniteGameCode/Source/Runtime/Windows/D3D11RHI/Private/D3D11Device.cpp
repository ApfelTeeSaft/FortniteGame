// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: D3D11RHI. Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/Windows/D3D11RHI/Private/D3D11Device.cpp.
// Compiled through ../Module.D3D11RHI.cpp.

#include "D3D11RHIRecoveredPrivate.h"

// Original FortniteClient-Win64-Shipping.exe: RVA not located (standalone copy unidentified)
// Recovery: high-confidence inferred (UE4 name, extern) | Matching: unknown
// Evidence: SafeTestD3D11CreateDevice (RVA 0x016138F0) only reproduces its size, unwind codes
//   and scope offsets when this body is inlined into it. The standalone compiled copy is 0x58
//   bytes with a generic sub rsp,0x28 unwind record. 636 reference functions share that size,
//   so its RVA cannot be fixed from metadata alone while bodies are encrypted.
bool D3D11RHI_ShouldCreateWithD3DDebug()
{
	return
		FParse::Param(FCommandLine::Get(), TEXT("d3ddebug")) ||
		FParse::Param(FCommandLine::Get(), TEXT("d3debug")) ||
		FParse::Param(FCommandLine::Get(), TEXT("dxdebug"));
}
