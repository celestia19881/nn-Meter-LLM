# LM-Meter Installation Guide

This guide covers the installation and setup of **LM-Meter**, an online kernel-level profiler for on-device Large Language Models (LLMs). LM-Meter extends nn-Meter to support LLM inference latency profiling on Android devices.

> **Reference**: Based on [LM-Meter](https://github.com/amai-gsu/LM-Meter) by Wang et al., "lm-Meter: Unveiling Runtime Inference Latency for On-Device Language Models," Proc. ACM/IEEE SEC, 2025.

## Prerequisites

### System Requirements

| Component       | Requirement                         |
|:---------------|:-------------------------------------|
| **OS**          | Linux (Ubuntu 20.04+) or macOS      |
| **Python**      | 3.8+                                |
| **Rust**        | 1.75.0 (for HuggingFace tokenizer cross-compilation) |
| **Java**        | JDK 17                              |
| **Android NDK** | 27.0.11718014                        |
| **CMake**       | 3.22+                               |
| **ADB**         | Latest (from Android SDK platform-tools) |

### Hardware Requirements

- A **Linux host machine** (or macOS) with internet access
- An **Android device** (e.g., Google Pixel 7/8 Pro) connected via USB with:
  - USB debugging enabled
  - Developer options turned on
  - GPU that supports OpenCL (for kernel-level profiling)

## Quick Setup (Automated)

We provide an automated setup script that installs all prerequisites:

```bash
cd scripts/lm_meter/
chmod +x setup_environment.sh
./setup_environment.sh
```

After setup completes:

```bash
source ~/.bashrc
conda activate lm-meter
pip install -e .
```

## Manual Setup

### Step 1: Install Rust 1.75.0

LM-Meter requires Rust 1.75.0 to cross-compile HuggingFace tokenizers for Android.

```bash
# Install rustup
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Install and pin Rust 1.75.0
rustup toolchain install 1.75.0
rustup default 1.75.0
rustup target add --toolchain 1.75.0 aarch64-linux-android
rustup override set 1.75.0
```

Add to `~/.bashrc`:

```bash
source "$HOME/.cargo/env"
if [ -f "$HOME/.cargo/env" ]; then
  . "$HOME/.cargo/env"
else
  export PATH="$HOME/.cargo/bin:$PATH"
fi
export RUSTUP_TOOLCHAIN=1.75.0
```

Verify:

```bash
rustc --version   # should report rustc 1.75.0
cargo --version   # should report cargo 1.75.0
```

### Step 2: Install Java 17

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y openjdk-17-jdk

# Verify
java -version   # should report 17.x
```

Add to `~/.bashrc`:

```bash
export JAVA_HOME="/usr/lib/jvm/java-17-openjdk-amd64"
export PATH="$JAVA_HOME/bin:$PATH"
```

### Step 3: Install Android SDK, NDK, and CMake

```bash
# Download Android command-line tools
mkdir -p ~/Android/Sdk/cmdline-tools
cd ~/Android/Sdk/cmdline-tools
curl -sL https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -o tools.zip
unzip tools.zip
mv cmdline-tools latest
rm tools.zip

# Install components
export PATH="$HOME/Android/Sdk/cmdline-tools/latest/bin:$PATH"
yes | sdkmanager --licenses
sdkmanager --install \
    "platform-tools" \
    "ndk;27.0.11718014" \
    "cmake;3.22.1" \
    "build-tools;34.0.0" \
    "platforms;android-34"
```

Add to `~/.bashrc`:

```bash
export ANDROID_HOME="$HOME/Android/Sdk"
export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"
export ANDROID_NDK="$ANDROID_HOME/ndk/27.0.11718014"
export TVM_NDK_CC="$ANDROID_NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang"
```

### Step 4: Set up Python Environment

```bash
# Using conda
conda create -n lm-meter python=3.11 -y
conda activate lm-meter

# Install nn-Meter with LM-Meter support
pip install -e .
```

### Step 5: Verify ADB Connection

Connect your Android device via USB, then:

```bash
adb devices
# Should show your device serial number with "device" status
```

## Install nn-Meter with LM-Meter Support

```bash
# From the project root directory
pip install -e ".[lm_meter]"
```

This installs the core nn-Meter package along with LM-Meter dependencies.

## Building MLC LLM with LM-Meter Instrumentation

To profile LLM inference on Android, you need to build a custom version of MLC LLM with LM-Meter's profiling instrumentation:

```bash
cd scripts/lm_meter/
chmod +x build_lm_meter.sh

# Build with kernel-level profiling
./build_lm_meter.sh --mode kernel

# Or build with phase-level profiling only
./build_lm_meter.sh --mode phase

# Or build with both (default)
./build_lm_meter.sh --mode both
```

> **Note**: The build process may take 20+ minutes depending on your hardware.

## Verify Installation

```python
# Test LM-Meter Python module
from lm_meter import LMProfiler, LMProfilerConfig, TraceParser, LatencyAnalyzer

config = LMProfilerConfig(profiling_mode="both")
print(f"LM-Meter configuration: {config.to_dict()}")
print("LM-Meter installed successfully!")
```

## Supported Models

LM-Meter has been tested with the following LLM models on Android:

| Model | Parameters | Quantization | Tested Devices |
|:------|:-----------|:-------------|:---------------|
| Llama-3.2-3B-Instruct | 3B | q4f16_1 | Pixel 7, Pixel 8 Pro |
| Gemma-2-2B-it | 2B | q4f16_1 | Pixel 7, Pixel 8 Pro |
| Phi-3.5-mini-instruct | 3.8B | q4f16_1 | Pixel 8 Pro |
| Qwen2.5-3B-Instruct | 3B | q4f16_1 | Pixel 8 Pro |

## Next Steps

- [Usage Guide](usage.md) — How to run profiling and collect data
- [Evaluation Guide](eval.md) — Analyzing and comparing latency results
- [Troubleshooting](common-errors.md) — Common errors and solutions
