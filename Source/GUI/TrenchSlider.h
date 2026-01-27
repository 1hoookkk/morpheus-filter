#pragma once
#include <JuceHeader.h>
#include "TrenchPalette.h"

//==============================================================================
// Minimal knob - just a ring with position indicator
//==============================================================================

class TrenchKnob : public juce::Component
{
public:
    TrenchKnob(const juce::String& name) : paramName(name)
    {
        // Don't intercept mouse - let slider child handle it
        setInterceptsMouseClicks(false, true);

        slider.setSliderStyle(juce::Slider::RotaryVerticalDrag);
        slider.setTextBoxStyle(juce::Slider::NoTextBox, false, 0, 0);
        slider.setRange(0.0, 100.0, 0.01);
        slider.setRotaryParameters(juce::MathConstants<float>::pi * 1.2f,
                                   juce::MathConstants<float>::pi * 2.8f, true);
        slider.onValueChange = [this]() { repaint(); };
        // Make slider invisible but still receive events
        slider.setColour(juce::Slider::rotarySliderFillColourId, juce::Colours::transparentBlack);
        slider.setColour(juce::Slider::rotarySliderOutlineColourId, juce::Colours::transparentBlack);
        slider.setColour(juce::Slider::thumbColourId, juce::Colours::transparentBlack);
        slider.setColour(juce::Slider::backgroundColourId, juce::Colours::transparentBlack);
        slider.setColour(juce::Slider::trackColourId, juce::Colours::transparentBlack);
        addAndMakeVisible(slider);
    }

    juce::Slider& getSlider() { return slider; }
    void setRange(double min, double max, double step = 0.01) { slider.setRange(min, max, step); }

    void paint(juce::Graphics& g) override
    {
        auto b = getLocalBounds();

        // Label
        g.setColour(TrenchPalette::dim());
        g.setFont(9.0f);
        g.drawText(paramName, b.removeFromTop(12), juce::Justification::centred);

        // Value
        g.setColour(TrenchPalette::text());
        g.setFont(10.0f);
        auto valArea = b.removeFromBottom(14);
        g.drawText(juce::String(slider.getValue(), 1), valArea, juce::Justification::centred);

        b.reduce(4, 4);
        int size = juce::jmin(b.getWidth(), b.getHeight());
        auto knobArea = b.withSizeKeepingCentre(size, size).toFloat();

        float cx = knobArea.getCentreX();
        float cy = knobArea.getCentreY();
        float r = size * 0.5f - 2.0f;

        // Track ring
        float startA = juce::MathConstants<float>::pi * 1.2f;
        float endA = juce::MathConstants<float>::pi * 2.8f;

        juce::Path track;
        track.addCentredArc(cx, cy, r, r, 0, startA, endA, true);
        g.setColour(TrenchPalette::line());
        g.strokePath(track, juce::PathStrokeType(2.0f, juce::PathStrokeType::curved, juce::PathStrokeType::rounded));

        // Value arc
        float norm = static_cast<float>((slider.getValue() - slider.getMinimum()) /
                     (slider.getMaximum() - slider.getMinimum()));
        float valA = startA + norm * (endA - startA);

        if (norm > 0.005f)
        {
            juce::Path val;
            val.addCentredArc(cx, cy, r, r, 0, startA, valA, true);
            g.setColour(TrenchPalette::accent());
            g.strokePath(val, juce::PathStrokeType(2.0f, juce::PathStrokeType::curved, juce::PathStrokeType::rounded));
        }

        // Position dot
        float dotR = 4.0f;
        float dotDist = r - 8.0f;
        float dx = cx + std::sin(valA) * dotDist;
        float dy = cy - std::cos(valA) * dotDist;
        g.setColour(TrenchPalette::bright());
        g.fillEllipse(dx - dotR, dy - dotR, dotR * 2, dotR * 2);
    }

    void resized() override { slider.setBounds(getLocalBounds()); }

private:
    juce::Slider slider;
    juce::String paramName;
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(TrenchKnob)
};

//==============================================================================
class TrenchButton : public juce::Component
{
public:
    TrenchButton(const juce::String& t) : label(t)
    {
        // Don't intercept mouse - let button child handle it
        setInterceptsMouseClicks(false, true);

        btn.setClickingTogglesState(true);
        btn.onClick = [this]() { repaint(); };
        btn.setColour(juce::TextButton::buttonColourId, juce::Colours::transparentBlack);
        btn.setColour(juce::TextButton::buttonOnColourId, juce::Colours::transparentBlack);
        btn.setColour(juce::TextButton::textColourOffId, juce::Colours::transparentBlack);
        btn.setColour(juce::TextButton::textColourOnId, juce::Colours::transparentBlack);
        addAndMakeVisible(btn);
    }

    juce::TextButton& getButton() { return btn; }

    void paint(juce::Graphics& g) override
    {
        bool on = btn.getToggleState();
        g.setColour(on ? TrenchPalette::accent() : TrenchPalette::line());
        g.fillRoundedRectangle(getLocalBounds().toFloat(), 3.0f);
        g.setColour(on ? TrenchPalette::bg() : TrenchPalette::text());
        g.setFont(9.0f);
        g.drawText(label, getLocalBounds(), juce::Justification::centred);
    }

    void resized() override { btn.setBounds(getLocalBounds()); }

private:
    juce::TextButton btn;
    juce::String label;
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(TrenchButton)
};
