#pragma once
#include <JuceHeader.h>

namespace TrenchPalette
{
    inline juce::Colour bg()       { return juce::Colour(0xFF0C0C0C); }
    inline juce::Colour surface()  { return juce::Colour(0xFF141414); }
    inline juce::Colour line()     { return juce::Colour(0xFF2A2A2A); }
    inline juce::Colour dim()      { return juce::Colour(0xFF4A4A4A); }
    inline juce::Colour text()     { return juce::Colour(0xFF8A8A8A); }
    inline juce::Colour bright()   { return juce::Colour(0xFFD0D0D0); }
    inline juce::Colour accent()   { return juce::Colour(0xFF00B894); }
}
