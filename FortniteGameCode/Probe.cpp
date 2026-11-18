// Synthetic inputs for the comparison tool. These exports are not Fortnite functions.
// The standalone v140 DLL has no CRT. Supply its floating-point usage marker.
extern "C" {
    int _fltused = 0;
}

extern "C" __declspec(dllexport) __declspec(noinline)
unsigned int ProbeScale(unsigned int value)
{
    return value * 5u + 3u;
}

extern "C" __declspec(dllexport) __declspec(noinline)
unsigned int ProbeScaleVariant(unsigned int value)
{
    return value * 5u + 4u;
}

extern "C" __declspec(dllexport) __declspec(noinline)
unsigned int ProbeBranch(unsigned int value)
{
    if ((value & 1u) != 0u) {
        return ProbeScale(value) + 3u;
    }
    return ProbeScaleVariant(value) + 5u;
}

extern "C" __declspec(dllexport) __declspec(noinline)
unsigned int ProbeBranchVariant(unsigned int value)
{
    if ((value & 1u) != 0u) {
        return ProbeScale(value) + 4u;
    }
    return ProbeScaleVariant(value) + 5u;
}

// These synthetic probes need flagless unwind records and no CRT dependencies.
extern "C" __declspec(dllexport) __declspec(noinline) __declspec(safebuffers)
unsigned int ProbeFrame(unsigned int value, void* pointer)
{
    void* volatile slots[32];
    const unsigned int index = value & 31u;
    slots[index] = pointer;
    const unsigned int scaled = ProbeScale(value);
    return scaled + value + (slots[index] != nullptr ? 7u : 0u);
}

extern "C" __declspec(dllexport) __declspec(noinline) __declspec(safebuffers)
unsigned int ProbeFrameVariant(unsigned int value, void* pointer)
{
    void* volatile slots[32];
    const unsigned int index = value & 31u;
    slots[index] = pointer;
    const unsigned int scaled = ProbeScale(value);
    return scaled + value + (slots[index] != nullptr ? 8u : 0u);
}

extern "C" __declspec(dllexport) __declspec(noinline)
double ProbeSimd(unsigned int value, double scale)
{
    const unsigned int scaled = ProbeScale(value);
    return scale + static_cast<double>(scaled) + 3.0;
}

extern "C" __declspec(dllexport) __declspec(noinline)
double ProbeSimdVariant(unsigned int value, double scale)
{
    const unsigned int scaled = ProbeScale(value);
    return scale + static_cast<double>(scaled) + 4.0;
}
