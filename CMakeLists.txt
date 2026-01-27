cmake_minimum_required(VERSION 3.22)
project(TRENCH VERSION 1.0.0)

# JUCE 8 - fetch or use local
include(FetchContent)
FetchContent_Declare(
    JUCE
    GIT_REPOSITORY https://github.com/juce-framework/JUCE.git
    GIT_TAG 8.0.1
    GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(JUCE)

# Plugin target
juce_add_plugin(TRENCH
    COMPANY_NAME "Trench Audio"
    BUNDLE_ID "com.trenchaudio.trench"
    PLUGIN_MANUFACTURER_CODE TrAu
    PLUGIN_CODE Trn1
    FORMATS VST3 AU Standalone
    PRODUCT_NAME "TRENCH"
    IS_SYNTH FALSE
    NEEDS_MIDI_INPUT FALSE
    NEEDS_MIDI_OUTPUT FALSE
    IS_MIDI_EFFECT FALSE
    EDITOR_WANTS_KEYBOARD_FOCUS FALSE
    COPY_PLUGIN_AFTER_BUILD TRUE
    VST3_CATEGORIES Fx Filter)

# Generate JuceHeader.h for convenience
juce_generate_juce_header(TRENCH)

# Binary resources (Z-Plane filter library)
juce_add_binary_data(TrenchData SOURCES
    Source/Data/wav_decoded.bin
    Source/Data/morpheus_zplane_library.json)

# Source files
target_sources(TRENCH
    PRIVATE
        Source/PluginProcessor.cpp
        Source/PluginEditor.cpp
        Source/DSP/WavCubeLoader.cpp)

# Link JUCE modules and binary data
target_link_libraries(TRENCH
    PRIVATE
        TrenchData
        juce::juce_audio_utils
        juce::juce_audio_processors
        juce::juce_dsp
        juce::juce_gui_basics
    PUBLIC
        juce::juce_recommended_config_flags
        juce::juce_recommended_lto_flags
        juce::juce_recommended_warning_flags)

# Compile definitions
target_compile_definitions(TRENCH
    PUBLIC
        JUCE_WEB_BROWSER=0
        JUCE_USE_CURL=0
        JUCE_VST3_CAN_REPLACE_VST2=0
        JUCE_DISPLAY_SPLASH_SCREEN=0)

# Include directories
target_include_directories(TRENCH
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/Source)
