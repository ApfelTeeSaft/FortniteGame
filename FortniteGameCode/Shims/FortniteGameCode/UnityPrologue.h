// Stand-in for the engine headers at the top of every unity translation unit. Not recovered code.
//
// Each of the original unity files first includes engine headers that define namespace-scope
// objects with dynamic initializers (their initializers open every unit in .CRT$XCU, see
// tools/analysis/unity_order.py). The first such object creates the unit's plain (non-COMDAT)
// .bss section, so every later zero-initialized namespace-scope object (registration objects,
// FName globals) joins that section ahead of the COMDAT function-local statics, which stay
// contiguous in source order. This object plays that role here. It only fixes the section's
// place in the object file; its storage and initializer are not part of the reconstruction.
//
// Of those header objects, the GlobalVectorConstants are reconstructed: tools/codegen/unity.py
// defines each unit's own, from its .CRT$XCU initializers, just before this prologue.
#pragma once

static struct FNGCUnityPrologue
{
	FNGCUnityPrologue();
} GNGCUnityPrologue;
