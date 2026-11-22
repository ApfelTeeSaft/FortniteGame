# Engine differences: reference build vs. supplied UE4.20.0

The reference identifies itself as `4.20.0-3889387+++Fortnite+Release-2.5`, linked
2018-02-14. The supplied tree is public `++UE4+Release-4.20` 4.20.0 (Changelist 0).
The reference is an internal development snapshot that predates the public release,
so source-level differences are expected. Each entry below is backed by evidence from
the reference image.

| # | Location (public 4.20.0) | Reference build | Evidence |
| --- | --- | --- | --- |
| 1 | `D3D11RHI/Private/Windows/WindowsD3D11Device.cpp` `SafeCreateDXGIFactory` parses `-quad_buffer_stereo` and may call `CreateDXGIFactory2` | Only `CreateDXGIFactory1` inside the `__try` | Parent `0x016138D0` is 0x1A bytes, with a 17-byte guarded range `[+0x04,+0x15)`. A one-call reconstruction reproduces size, unwind and scope exactly |
| 2 | Same file, `SafeTestD3D11CreateDevice` requests `{11_1, 11_0, 10_0}` | Requests `{11_0, 10_0}` | With three levels the array is a `/GS` buffer, so v140 adds a cookie, `__GSHandlerCheck_SEH` and a 0x90 frame. With two levels it reproduces size 0x13E, the 0x70 frame, all unwind codes, `__C_specific_handler` and scope `[+0xBD,+0x126)` |
| 3 | `D3D12RHI/Private/Windows/WindowsD3D12Device.cpp` `SafeCreateDXGIFactory` assigns `bIsQuadBufferStereoEnabled` | If `0x0165FEB0` is this function, only the factory call is guarded | Same shape as #1. Owner not confirmed (low confidence) |
| 4 | 20 BlueprintCallable functions declared `virtual` in public 4.20.0, for example 10 in `UAbilitySystemComponent` (`TargetConfirm`, `MakeEffectContext`, ...), `UWidget::IsHovered`, `UUserWidget::GetOwningLocalPlayer`, `UCheatManager::InvertMouse`, `ADefaultPawn::LookUpAtRate` | Their exec thunks call or tail-jump to them directly, not through the vtable: not virtual, or `final`, in this build | `analysis/native-implementations.json`. MSVC v140 calls a non-final virtual through the vtable. All 20 targets pass the Context-in-rcx and module-range checks. Plausible for a February 2018 branch of a July 2018 release, but unconfirmed (medium confidence). Full list: `docs/REVERSE_ENGINEERING.md`, "Native implementations" |
| 5 | `SlateCore/Public/Styling/SlateBrush.h` `FSlateBrush`: 136 bytes, with `mutable FSlateResourceHandle ResourceHandle` (a `TSharedPtr`, 16 bytes) after `ImageType` and the two bitfields after it | 120 bytes, alignment 8 | The reference's `FStructParams` for `FSlateBrush` give SizeOf 120. Its reflected members sit where 4.20 puts them, up to `ImageType` at 111 (`ImageSize` 8, `Margin` 16, `TintColor` 32, `ResourceObject` 72, `ResourceName` 80, `UVRegion` 88, the enums 108-111). 16 bytes fewer fits `ResourceHandle` being absent or elsewhere. Not modelled (medium confidence) |
| 6 | `CoreUObject/Public/UObject/SoftObjectPath.h` `FSoftObjectPath& operator=(FSoftObjectPath Other)`: by value; `SoftObjectPath.cpp` moves the copy's `SubPathString` | Takes the path by reference and copies it | Callers pass the source path's address, with no copy first: e.g. the exec thunk `UFortItem::execGetSmallPreviewImage` (`0x01009900`), `lea rdx, [rax+0x10]; call 0x01389AA0`. The callee copies `AssetPathName`, then calls `FString`'s copy assignment (`0x0056A0A0`: `this != &Other`, `ResizeForCopy`, `memcpy`). Modelled as `operator=(const FSoftObjectPath&)`, out of line (high confidence for the shape; whether `const&` or a defaulted copy assignment is not visible) |

No engine patches have been made. Stage 3 will record compatibility patches here.
