#pragma once
#include <JuceHeader.h>
#include "TrenchPalette.h"

//==============================================================================
// Minimal display - morph visualization
//==============================================================================

class TrenchOLED : public juce::Component
{
public:
    TrenchOLED() { setOpaque(true); }

    void setMorph(float m) { morph = juce::jlimit(0.0f, 1.0f, m); repaint(); }
    void setQ(float newQ) { q = juce::jlimit(0.0f, 1.0f, newQ); repaint(); }

    void paint(juce::Graphics& g) override
    {
        g.fillAll(juce::Colour(0xFF080808));

        auto b = getLocalBounds().reduced(1);
        g.setColour(TrenchPalette::line());
        g.drawRect(b.toFloat(), 1.0f);

        auto inner = b.reduced(20);
        float cx = static_cast<float>(inner.getCentreX());
        float cy = static_cast<float>(inner.getCentreY());
        float maxR = juce::jmin(inner.getWidth(), inner.getHeight()) * 0.35f;

        // Shape morphs from circle to line
        float w = maxR * (0.6f + morph * 1.0f);
        float h = maxR * (1.0f - morph * 0.9f);
        h = juce::jmax(h, 2.0f);

        float alpha = 0.4f + q * 0.6f;

        juce::Path shape;
        shape.addEllipse(cx - w, cy - h, w * 2, h * 2);

        g.setColour(TrenchPalette::accent().withAlpha(alpha * 0.15f));
        g.fillPath(shape);

        g.setColour(TrenchPalette::accent().withAlpha(alpha));
        g.strokePath(shape, juce::PathStrokeType(1.5f));
    }

private:
    float morph = 0.0f;
    float q = 0.5f;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(TrenchOLED)
};
