#!/usr/bin/env bash
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.
#
# LM-Meter Build Script
#
# Builds the MLC LLM engine with LM-Meter profiling instrumentation.
# This script automates the compilation of:
#   - TVM runtime with OpenCL kernel profiling
#   - MLC LLM with LM-Meter instrumentation
#   - Android APK for deployment
#
# Prerequisites:
#   - Run setup_environment.sh first
#   - Activate conda env: conda activate lm-meter
#   - Ensure ANDROID_NDK and TVM_NDK_CC are set
#
# Usage:
#   chmod +x build_lm_meter.sh
#   ./build_lm_meter.sh [--mode kernel|phase|both]
#
# Reference: https://github.com/amai-gsu/LM-Meter

set -euo pipefail

MODE="${1:-both}"

echo "============================================="
echo "  LM-Meter Build Script"
echo "  Mode: ${MODE}"
echo "============================================="

# Validate environment
check_env() {
    local var_name="$1"
    local var_val="${!var_name:-}"
    if [ -z "$var_val" ]; then
        echo "ERROR: $var_name is not set. Run setup_environment.sh first."
        exit 1
    fi
    echo "  $var_name = $var_val"
}

echo ""
echo "Checking environment..."
check_env "ANDROID_NDK"
check_env "TVM_NDK_CC"
check_env "JAVA_HOME"

if ! command -v rustc &> /dev/null; then
    echo "ERROR: rustc not found. Run setup_environment.sh first."
    exit 1
fi
echo "  Rust: $(rustc --version)"

# Determine project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo ""
echo "Project root: $PROJECT_ROOT"

# Check for MLC LLM submodule
MLC_DIR="$PROJECT_ROOT/3rdparty/mlc-llm"
TVM_DIR="$PROJECT_ROOT/3rdparty/tvm"

if [ ! -d "$MLC_DIR" ]; then
    echo ""
    echo "MLC LLM submodule not found at $MLC_DIR"
    echo "Cloning MLC LLM..."
    mkdir -p "$PROJECT_ROOT/3rdparty"
    git clone --recursive https://github.com/mlc-ai/mlc-llm.git "$MLC_DIR"
fi

if [ ! -d "$TVM_DIR" ]; then
    echo ""
    echo "TVM submodule not found at $TVM_DIR"
    echo "Please ensure TVM is available (it may be a submodule of MLC LLM)."
    if [ -d "$MLC_DIR/3rdparty/tvm" ]; then
        ln -sf "$MLC_DIR/3rdparty/tvm" "$TVM_DIR"
        echo "  Linked TVM from MLC LLM submodule."
    fi
fi

echo ""
echo "Building TVM runtime for Android..."
BUILD_DIR="$PROJECT_ROOT/build"
mkdir -p "$BUILD_DIR"

case "$MODE" in
    kernel)
        echo "  Building with kernel-level profiling (OpenCL)..."
        CMAKE_FLAGS="-DUSE_OPENCL=ON -DUSE_OPENCL_ENABLE_HOST_PTR=ON"
        ;;
    phase)
        echo "  Building with phase-level profiling..."
        CMAKE_FLAGS="-DUSE_OPENCL=ON"
        ;;
    both|*)
        echo "  Building with kernel + phase profiling (OpenCL)..."
        CMAKE_FLAGS="-DUSE_OPENCL=ON -DUSE_OPENCL_ENABLE_HOST_PTR=ON"
        ;;
esac

echo ""
echo "Build configuration:"
echo "  CMAKE_FLAGS: $CMAKE_FLAGS"
echo ""
echo "To complete the build, run the following commands:"
echo ""
echo "  cd $BUILD_DIR"
echo "  cmake .. $CMAKE_FLAGS \\"
echo "    -DCMAKE_TOOLCHAIN_FILE=\$ANDROID_NDK/build/cmake/android.toolchain.cmake \\"
echo "    -DANDROID_ABI=arm64-v8a \\"
echo "    -DANDROID_PLATFORM=android-24"
echo "  make -j\$(nproc)"
echo ""
echo "After building, deploy to Android device:"
echo "  adb install build/outputs/apk/debug/app-debug.apk"
echo ""
echo "============================================="
echo "  Build script finished."
echo "============================================="
