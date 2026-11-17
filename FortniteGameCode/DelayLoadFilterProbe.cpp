struct ExceptionRecordPrefix {
    unsigned long code;
};

struct ExceptionPointersPrefix {
    const ExceptionRecordPrefix* record;
};

extern "C" void* _exception_info();
using Callback = int (*)(unsigned int);

constexpr unsigned long MissingModule = 0xC06D007Eul;
constexpr unsigned long MissingProcedure = 0xC06D007Ful;

__forceinline bool HandlesMissingImport(const ExceptionPointersPrefix* pointers)
{
    // Keep the boolean in the compiler's exception frame.
    volatile bool handles =
        pointers->record->code - MissingModule <= MissingProcedure - MissingModule;
    return handles;
}

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02DAE780
// This wrapper is synthetic. Its generated DelayLoadFilterProbe$filt$0
// corresponds to the inferred delay-load exception filter.
extern "C" __declspec(noinline) int DelayLoadFilterProbe(Callback callback, unsigned int argument)
{
    __try {
        return callback(argument);
    } __except (
        HandlesMissingImport(static_cast<const ExceptionPointersPrefix*>(_exception_info()))
    ) {
        return -1;
    }
}

using WideCallback = int (*)(
    unsigned int, unsigned int, unsigned int, unsigned int, unsigned int,
    unsigned int, unsigned int, unsigned int, unsigned int, unsigned int);

// Original FortniteClient-Win64-Shipping.exe: RVA 0x02DAE750
// This synthetic wrapper makes the compiler reserve the wider argument area.
// Its generated filter still has a different exception-pointer spill offset.
extern "C" __declspec(noinline) int WideDelayLoadFilterProbe(
    WideCallback callback, unsigned int argument)
{
    __try {
        return callback(
            argument, argument, argument, argument, argument,
            argument, argument, argument, argument, argument);
    } __except (
        HandlesMissingImport(static_cast<const ExceptionPointersPrefix*>(_exception_info()))
    ) {
        return -1;
    }
}
