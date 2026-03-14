#!/usr/bin/env bash
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.
#
# LM-Meter Environment Setup Script for Linux
#
# This script installs the prerequisites for building and running LM-Meter
# on a Linux host machine. It covers:
#   1. Rust toolchain (1.75.0) with Android cross-compilation target
#   2. Java 17 (OpenJDK / Temurin)
#   3. Android SDK command-line tools, NDK, and CMake
#   4. Conda environment for LM-Meter
#
# Usage:
#   chmod +x setup_environment.sh
#   ./setup_environment.sh
#
# After running this script, activate the conda environment:
#   conda activate lm-meter
#
# Reference: https://github.com/amai-gsu/LM-Meter

set -euo pipefail

echo "============================================="
echo "  LM-Meter Environment Setup (Linux)"
echo "============================================="

# -------------------------------------------
# 1. Install Rust 1.75.0
# -------------------------------------------
echo ""
echo "[Step 1/4] Installing Rust 1.75.0 ..."

if command -v rustup &> /dev/null; then
    echo "  rustup already installed, updating toolchain..."
else
    echo "  Installing rustup..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
fi

rustup toolchain install 1.75.0
rustup default 1.75.0
rustup target add --toolchain 1.75.0 aarch64-linux-android
rustup override set 1.75.0

# Ensure cargo/rustc are on PATH in .bashrc
if ! grep -q 'cargo/env' ~/.bashrc 2>/dev/null; then
    cat >> ~/.bashrc << 'RUST_EOF'

# --- LM-Meter: Rust toolchain ---
if [ -f "$HOME/.cargo/env" ]; then
  . "$HOME/.cargo/env"
else
  export PATH="$HOME/.cargo/bin:$PATH"
fi
export RUSTUP_TOOLCHAIN=1.75.0
RUST_EOF
    echo "  Added Rust PATH to ~/.bashrc"
fi

source "$HOME/.cargo/env"
echo "  Rust version: $(rustc --version)"
echo "  Cargo version: $(cargo --version)"

# -------------------------------------------
# 2. Install Java 17
# -------------------------------------------
echo ""
echo "[Step 2/4] Installing Java 17 (OpenJDK) ..."

if java -version 2>&1 | grep -q 'version "17'; then
    echo "  Java 17 is already installed."
    JAVA_HOME_PATH=$(dirname $(dirname $(readlink -f $(which java))))
else
    echo "  Installing OpenJDK 17 via apt..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq openjdk-17-jdk
    JAVA_HOME_PATH="/usr/lib/jvm/java-17-openjdk-amd64"
fi

# Set JAVA_HOME in .bashrc
if ! grep -q 'JAVA_HOME.*17' ~/.bashrc 2>/dev/null; then
    cat >> ~/.bashrc << JAVA_EOF

# --- LM-Meter: Java 17 ---
export JAVA_HOME="${JAVA_HOME_PATH}"
export PATH="\$JAVA_HOME/bin:\$PATH"
JAVA_EOF
    echo "  Added JAVA_HOME to ~/.bashrc"
fi

export JAVA_HOME="${JAVA_HOME_PATH}"
export PATH="$JAVA_HOME/bin:$PATH"
echo "  Java version: $(java -version 2>&1 | head -1)"

# -------------------------------------------
# 3. Install Android SDK, NDK, CMake
# -------------------------------------------
echo ""
echo "[Step 3/4] Setting up Android SDK tools ..."

ANDROID_HOME="${ANDROID_HOME:-$HOME/Android/Sdk}"

if [ ! -d "$ANDROID_HOME" ]; then
    echo "  Downloading Android command-line tools..."
    mkdir -p "$ANDROID_HOME/cmdline-tools"
    CMDLINE_TOOLS_URL="https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip"
    TMPZIP="/tmp/android-cmdline-tools.zip"
    curl -sL "$CMDLINE_TOOLS_URL" -o "$TMPZIP"
    unzip -q "$TMPZIP" -d "$ANDROID_HOME/cmdline-tools/"
    mv "$ANDROID_HOME/cmdline-tools/cmdline-tools" "$ANDROID_HOME/cmdline-tools/latest"
    rm "$TMPZIP"
fi

export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"

# Accept licenses and install components
echo "  Installing SDK platform-tools, NDK 27.0.11718014, and CMake..."
yes | sdkmanager --licenses > /dev/null 2>&1 || true
sdkmanager --install \
    "platform-tools" \
    "ndk;27.0.11718014" \
    "cmake;3.22.1" \
    "build-tools;34.0.0" \
    "platforms;android-34" \
    2>/dev/null || echo "  (Some components may already be installed)"

ANDROID_NDK="$ANDROID_HOME/ndk/27.0.11718014"
TVM_NDK_CC="$ANDROID_NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang"

# Add to .bashrc
if ! grep -q 'ANDROID_NDK' ~/.bashrc 2>/dev/null; then
    cat >> ~/.bashrc << ANDROID_EOF

# --- LM-Meter: Android SDK & NDK ---
export ANDROID_HOME="${ANDROID_HOME}"
export PATH="\$ANDROID_HOME/cmdline-tools/latest/bin:\$ANDROID_HOME/platform-tools:\$PATH"
export ANDROID_NDK="${ANDROID_NDK}"
export TVM_NDK_CC="${TVM_NDK_CC}"
ANDROID_EOF
    echo "  Added Android SDK/NDK to ~/.bashrc"
fi

echo "  Android SDK: $ANDROID_HOME"
echo "  Android NDK: $ANDROID_NDK"

# -------------------------------------------
# 4. Setup Conda Environment
# -------------------------------------------
echo ""
echo "[Step 4/4] Setting up Conda environment ..."

if command -v conda &> /dev/null; then
    echo "  conda found."
else
    echo "  conda not found. Installing Miniconda..."
    MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
    curl -sL "$MINICONDA_URL" -o /tmp/miniconda.sh
    bash /tmp/miniconda.sh -b -p "$HOME/miniconda3"
    rm /tmp/miniconda.sh
    eval "$($HOME/miniconda3/bin/conda shell.bash hook)"
    conda init bash
fi

conda config --add channels conda-forge 2>/dev/null || true
conda config --set channel_priority flexible

# Create lm-meter conda environment
if conda env list | grep -q 'lm-meter'; then
    echo "  conda env 'lm-meter' already exists."
else
    echo "  Creating conda env 'lm-meter' with Python 3.11..."
    conda create -n lm-meter python=3.11 -y
fi

echo ""
echo "============================================="
echo "  Setup Complete!"
echo "============================================="
echo ""
echo "Next steps:"
echo "  1. Reload your shell:  source ~/.bashrc"
echo "  2. Activate conda env: conda activate lm-meter"
echo "  3. Install LM-Meter:   pip install -e ."
echo "  4. Connect Android device via USB and verify: adb devices"
echo ""
