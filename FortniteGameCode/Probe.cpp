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
