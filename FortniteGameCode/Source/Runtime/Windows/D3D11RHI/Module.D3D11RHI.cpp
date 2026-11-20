// Unity translation unit for the recovered D3D11RHI sources (UnrealBuildTool style).
// Evidence only fixes the relative order D3D11Device.cpp -> Windows/WindowsD3D11Device.cpp:
// the latter inlines D3D11RHI_ShouldCreateWithD3DDebug from the former. The original unity
// grouping of the other D3D11RHI files is unknown.
#include "Private/D3D11Device.cpp"
#include "Private/Windows/WindowsD3D11Device.cpp"
