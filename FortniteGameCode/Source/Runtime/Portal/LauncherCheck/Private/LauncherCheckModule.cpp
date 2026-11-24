// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: LauncherCheck. Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/Portal/LauncherCheck/Private/LauncherCheckModule.cpp.
// Reconstruction written from image evidence; see analysis/functions.json.

#include "FortniteGameCode/EngineDecls.h"

// Only the members the recovered function uses. The original derives from
// ILauncherCheckModule; this TU defines no constructor, so no vtable is emitted here.
class FLauncherCheckModule
{
public:
	bool IsEnabled() const
	{
		return FParse::Param(FCommandLine::Get(), TEXT("NoEpicPortal")) == false && FParse::Param(FCommandLine::Get(), TEXT("q")) == false;
	}

	virtual bool WasRanFromLauncher() const;
};

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02517390 (end 0x025173E8)
// Original VA: 0x0000000142517390 | File offset: 0x02516990
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: FParse::Param(FCommandLine::Get(), ...) for L"NoEpicPortal", L"q" and L"EpicPortal",
//   true as soon as one is set: IsEnabled() inlined into WasRanFromLauncher(). The same 0x58-byte
//   shape as D3D11RHI_ShouldCreateWithD3DDebug (0x015FEDD0), which is exact.
bool FLauncherCheckModule::WasRanFromLauncher() const
{
	return !IsEnabled() || FParse::Param(FCommandLine::Get(), TEXT("EpicPortal"));
}
