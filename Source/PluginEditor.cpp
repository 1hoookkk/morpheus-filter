#include "PluginProcessor.h"
#include "PluginEditor.h"

TrenchAudioProcessorEditor::TrenchAudioProcessorEditor(TrenchAudioProcessor& p)
    : AudioProcessorEditor(&p), proc(p)
{
    setSize(380, 500);

    addAndMakeVisible(display);

    morphKnob.setRange(0.0, 100.0);
    qKnob.setRange(0.0, 100.0);
    driveKnob.setRange(0.0, 100.0);
    mixKnob.setRange(0.0, 100.0);

    addAndMakeVisible(morphKnob);
    addAndMakeVisible(qKnob);
    addAndMakeVisible(driveKnob);
    addAndMakeVisible(mixKnob);
    addAndMakeVisible(bypassBtn);
    addAndMakeVisible(testBtn);

    morphAtt = std::make_unique<juce::AudioProcessorValueTreeState::SliderAttachment>(
        proc.getAPVTS(), "morph", morphKnob.getSlider());
    qAtt = std::make_unique<juce::AudioProcessorValueTreeState::SliderAttachment>(
        proc.getAPVTS(), "q", qKnob.getSlider());
    driveAtt = std::make_unique<juce::AudioProcessorValueTreeState::SliderAttachment>(
        proc.getAPVTS(), "drive", driveKnob.getSlider());
    mixAtt = std::make_unique<juce::AudioProcessorValueTreeState::SliderAttachment>(
        proc.getAPVTS(), "mix", mixKnob.getSlider());
    bypassAtt = std::make_unique<juce::AudioProcessorValueTreeState::ButtonAttachment>(
        proc.getAPVTS(), "bypass", bypassBtn.getButton());
    testAtt = std::make_unique<juce::AudioProcessorValueTreeState::ButtonAttachment>(
        proc.getAPVTS(), "test", testBtn.getButton());

    startTimerHz(24);
}

TrenchAudioProcessorEditor::~TrenchAudioProcessorEditor() { stopTimer(); }

void TrenchAudioProcessorEditor::paint(juce::Graphics& g)
{
    g.fillAll(TrenchPalette::bg());

    // Title
    g.setColour(TrenchPalette::dim());
    g.setFont(11.0f);
    g.drawText("TRENCH", getLocalBounds().removeFromTop(40), juce::Justification::centred);

    // Subtle divider line
    g.setColour(TrenchPalette::line());
    g.drawHorizontalLine(40, 40.0f, getWidth() - 40.0f);
}

void TrenchAudioProcessorEditor::resized()
{
    auto b = getLocalBounds();
    b.removeFromTop(50);  // Header space

    auto content = b.reduced(32, 0);

    // Display
    display.setBounds(content.removeFromTop(120));

    content.removeFromTop(32);

    // Knobs - single row of 4
    auto knobRow = content.removeFromTop(80);
    int knobW = knobRow.getWidth() / 4;

    morphKnob.setBounds(knobRow.removeFromLeft(knobW));
    qKnob.setBounds(knobRow.removeFromLeft(knobW));
    driveKnob.setBounds(knobRow.removeFromLeft(knobW));
    mixKnob.setBounds(knobRow);

    content.removeFromTop(32);

    // Buttons row
    auto btnRow = content.removeFromTop(24);
    int btnW = 64;
    int gap = 16;
    int totalW = btnW * 2 + gap;
    int startX = (btnRow.getWidth() - totalW) / 2;

    testBtn.setBounds(btnRow.getX() + startX, btnRow.getY(), btnW, 24);
    bypassBtn.setBounds(btnRow.getX() + startX + btnW + gap, btnRow.getY(), btnW, 24);
}

void TrenchAudioProcessorEditor::timerCallback()
{
    float m = static_cast<float>(morphKnob.getSlider().getValue() / 100.0);
    float q = static_cast<float>(qKnob.getSlider().getValue() / 100.0);
    display.setMorph(m);
    display.setQ(q);
}
