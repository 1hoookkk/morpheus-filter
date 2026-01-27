#pragma once
#include <JuceHeader.h>
#include "PluginProcessor.h"
#include "GUI/TrenchPalette.h"
#include "GUI/TrenchSlider.h"
#include "GUI/TrenchOLED.h"

class TrenchAudioProcessorEditor : public juce::AudioProcessorEditor,
                                    private juce::Timer
{
public:
    explicit TrenchAudioProcessorEditor(TrenchAudioProcessor&);
    ~TrenchAudioProcessorEditor() override;

    void paint(juce::Graphics&) override;
    void resized() override;

private:
    void timerCallback() override;

    TrenchAudioProcessor& proc;

    TrenchOLED display;

    TrenchKnob morphKnob { "MORPH" };
    TrenchKnob qKnob { "Q" };
    TrenchKnob driveKnob { "DRIVE" };
    TrenchKnob mixKnob { "MIX" };

    TrenchButton bypassBtn { "BYPASS" };
    TrenchButton testBtn { "TEST" };

    std::unique_ptr<juce::AudioProcessorValueTreeState::SliderAttachment> morphAtt;
    std::unique_ptr<juce::AudioProcessorValueTreeState::SliderAttachment> qAtt;
    std::unique_ptr<juce::AudioProcessorValueTreeState::SliderAttachment> driveAtt;
    std::unique_ptr<juce::AudioProcessorValueTreeState::SliderAttachment> mixAtt;
    std::unique_ptr<juce::AudioProcessorValueTreeState::ButtonAttachment> bypassAtt;
    std::unique_ptr<juce::AudioProcessorValueTreeState::ButtonAttachment> testAtt;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(TrenchAudioProcessorEditor)
};
