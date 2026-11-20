// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: D3D11RHI. Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/Windows/D3D11RHI/Private/D3D11Device.cpp.
// Compiled through ../Module.D3D11RHI.cpp.

#include "D3D11RHIRecoveredPrivate.h"

// Original FortniteClient-Win64-Shipping.exe: RVA 0x015FEDD0 (end 0x015FEE28)
// Original VA: 0x00000001415FEDD0 | File offset: 0x015FE3D0
// Recovery: high-confidence inferred (UE4 name, extern) | Matching: relocation-equivalent (vs decrypted image; literals ambiguous, callees not yet matched)
// Evidence: SafeTestD3D11CreateDevice (RVA 0x016138F0) only reproduces its structure with this
//   body inlined. In the decrypted image two 0x58-byte functions match every non-relocation
//   byte; only this one references the literals d3ddebug/d3debug/dxdebug, and they are the
//   same copies (0x0353EF98/0x0353F2E8/0x0353F368) as the inlined use. The other function,
//   0x02517390, tests NoEpicPortal/q/EpicPortal.
bool D3D11RHI_ShouldCreateWithD3DDebug()
{
	return
		FParse::Param(FCommandLine::Get(), TEXT("d3ddebug")) ||
		FParse::Param(FCommandLine::Get(), TEXT("d3debug")) ||
		FParse::Param(FCommandLine::Get(), TEXT("dxdebug"));
}
