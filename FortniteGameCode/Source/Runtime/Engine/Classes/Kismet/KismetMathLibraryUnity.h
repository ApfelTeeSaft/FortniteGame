// Opens the generated unity unit that holds UKismetMathLibrary's UHT code (Engine.18), before its
// constants and fragments, for KismetMathLibrary.inl, which tools/codegen/unity.py (UNIT_SOURCES)
// compiles at the unit's end. Declarations and flags only: nothing here emits code.
#pragma once

// FTransform's matrix and composition members (TransformRecovered.h, QuatRecovered.h).
#define FNGC_CORE_MATH_EXTRAS 1

// The unit's constants (analysis/unity-order.json) lack SmallLengthThreshold and VectorSinCos's.
#define FNGC_QUAT_WITHOUT_SINCOS 1

// The natives KismetMathLibrary.inl defines, declared in the generated class body
// (tools/codegen/uht_classes.py, EXTRA_MEMBERS).
#define FNGC_EXTRA_MEMBERS_UKismetMathLibrary \
	static FTransform ComposeTransforms(const FTransform& A, const FTransform& B); \
	static FVector GetDirectionUnitVector(FVector From, FVector To); \
	static FTransform InvertTransform(const FTransform& T); \
	static FVector RandomPointInBoundingBox(const FVector& Origin, const FVector& BoxExtent);
