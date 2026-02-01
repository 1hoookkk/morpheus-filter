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
        Source/DSP/WavCubeLoader.cpp
        Source/DSP/ZPlaneFilter.cpp)

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

# -----------------------------------------------------------------------------
# Offline DSP runner (no audio device needed)
# Writes tools/output_*.wav for comparison against validation/*.wav
# -----------------------------------------------------------------------------
add_executable(dsp_runner
    tools/dsp_runner.cpp
    Source/DSP/ZPlaneFilter.cpp)

target_include_directories(dsp_runner
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/Source)

target_link_libraries(dsp_runner
    PRIVATE
        juce::juce_audio_basics
        juce::juce_core
        juce::juce_recommended_config_flags
        juce::juce_recommended_lto_flags
        juce::juce_recommended_warning_flags)

# -----------------------------------------------------------------------------
# Morph sweep renderer (for X3 comparison)
# Renders smooth morph from M0 to M100 over 10 seconds
# -----------------------------------------------------------------------------
add_executable(morph_sweep
    tools/render_morph_sweep.cpp
    Source/DSP/ZPlaneFilter.cpp)

target_include_directories(morph_sweep
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/Source)

target_link_libraries(morph_sweep
    PRIVATE
        juce::juce_audio_basics
        juce::juce_core
        juce::juce_recommended_config_flags
        juce::juce_recommended_lto_flags
        juce::juce_recommended_warning_flags)

# -----------------------------------------------------------------------------
# DSP Engine Functional Test (Phase 2)
# Validates 5-stage cascade with pink noise input
# -----------------------------------------------------------------------------
add_executable(test_dsp_engine
    tools/test_dsp_engine.cpp
    Source/DSP/ZPlaneFilter.cpp)

target_include_directories(test_dsp_engine
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/Source)

target_link_libraries(test_dsp_engine
    PRIVATE
        juce::juce_audio_basics
        juce::juce_core
        juce::juce_recommended_config_flags
        juce::juce_recommended_lto_flags
        juce::juce_recommended_warning_flags)
