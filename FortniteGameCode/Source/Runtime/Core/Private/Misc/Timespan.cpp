// Recovered from FortniteClient-Win64-Shipping.exe (++Fortnite+Release-2.5-CL-3889387).
// Module: Core. Reference for names and intent: the supplied UE4.20.0 tree,
// Engine/Source/Runtime/Core/Private/Misc/Timespan.cpp.
// Reconstruction written from image evidence; see analysis/functions.json.

#define FNGC_CORE_MATH_EXTRAS 1   // FDateTime, FColor, FVector4, ... (MathDecls.h)
#include "FortniteGameCode/MathDecls.h"

/* FTimespan implementation
 *****************************************************************************/

// check((TotalTicks >= ETimespan::MinTicks) && (TotalTicks <= ETimespan::MaxTicks)) is compiled out.
// Original FortniteClient-Win64-Shipping.exe: RVA 0x011D5640 (end 0x011D5695), no .pdata (leaf)
// Original VA: 0x00000001411D5640 | File offset: 0x011D4C40
// Recovery: high-confidence inferred (UE4 name) | Matching: see analysis/functions.json
// Evidence: called by FTimespan's constructor, inlined in UKismetMathLibrary::MakeTimespan (0x0208A5B0) and
//   MakeTimespan2 (0x0208A580); v140 folds the sum into (((Days * 24 + Hours) * 60 + Minutes) * 60
//   + Seconds) * TicksPerSecond.
void FTimespan::Assign(int32 Days, int32 Hours, int32 Minutes, int32 Seconds, int32 FractionNano)
{
	int64 TotalTicks = 0;

	TotalTicks += Days * ETimespan::TicksPerDay;
	TotalTicks += Hours * ETimespan::TicksPerHour;
	TotalTicks += Minutes * ETimespan::TicksPerMinute;
	TotalTicks += Seconds * ETimespan::TicksPerSecond;
	TotalTicks += FractionNano / ETimespan::NanosecondsPerTick;

	Ticks = TotalTicks;
}
