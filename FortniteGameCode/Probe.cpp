// Synthetic inputs for the comparison tool. These exports are not Fortnite functions.
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
