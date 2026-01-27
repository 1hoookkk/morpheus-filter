@echo off
REM TRENCH Quick Build Script
REM Usage: build.bat [debug|release]

setlocal
cd /d "%~dp0"

set CONFIG=%1
if "%CONFIG%"=="" set CONFIG=Release

if not exist build (
    echo First run - configuring CMake...
    mkdir build
    cd build
    cmake .. -G "Visual Studio 17 2022"
    cd ..
)

echo Building %CONFIG%...
REM Use TRENCH_All target to build both VST3 and Standalone
cmake --build build --config %CONFIG% --target TRENCH_All --parallel

if %ERRORLEVEL% EQU 0 (
    echo.
    echo BUILD SUCCESS
    echo VST3: build\TRENCH_artefacts\%CONFIG%\VST3\TRENCH.vst3
    echo Standalone: build\TRENCH_artefacts\%CONFIG%\Standalone\TRENCH.exe

    REM Auto-launch standalone for quick test
    if "%2"=="run" (
        echo Launching standalone...
        start "" "build\TRENCH_artefacts\%CONFIG%\Standalone\TRENCH.exe"
    )
) else (
    echo BUILD FAILED
)
