# LM-Meter Usage Guide

This guide explains how to use LM-Meter to profile LLM inference latency on Android devices.

## Overview

LM-Meter supports two levels of profiling:

- **Phase-level profiling**: Measures latency for each inference phase (embedding, prefill, decode, softmax, sampling, etc.)
- **Kernel-level profiling**: Measures latency for individual GPU kernels within each phase (e.g., dequantize, matmul, attention kernels)

> When running with kernel-level profiling, LM-Meter automatically captures both phase-level and kernel-level data.

## Method 1: Using the Data Collection Script

The simplest way to collect profiling data is via the provided shell script:

```bash
cd scripts/lm_meter/
chmod +x collect_data.sh

# Basic usage (120 seconds profiling window)
./collect_data.sh

# Custom duration and output directory
./collect_data.sh --duration 180 --output-dir ./my_experiment

# Specify a device serial
./collect_data.sh -s <device-serial> --duration 120
```

### Workflow

1. Run `collect_data.sh` on your **host machine**
2. The script will wait for you to launch the LLM app on the Android device
3. Start inference on the device (e.g., send a prompt to the LLM)
4. The script automatically collects logs and traces
5. After the specified duration, data is pulled from the device

### Output Structure

```
lm_meter_output/
└── session_20250314_143022/
    ├── tvm_mlc.log          # Runtime logs from MLC LLM/TVM
    ├── metadata.json         # Session info (device, duration, etc.)
    └── traces/
        ├── trace_001.json    # Trace events (Chrome/Perfetto format)
        ├── trace_002.json
        └── ...
```

## Method 2: Using the Python API

For programmatic control, use the LM-Meter Python API:

### Basic Profiling Session

```python
from lm_meter import LMProfiler, LMProfilerConfig

# Configure the profiling session
config = LMProfilerConfig(
    profiling_mode="both",           # 'phase', 'kernel', or 'both'
    trace_output_dir="./experiment", # Where to save output
    device_serial=None,              # Auto-detect device
)

# Create and set up the profiler
profiler = LMProfiler(config)
profiler.setup()

# Start profiling
profiler.start()

# >>> Now launch the LLM app on your Android device <<<
# >>> and start inference <<<

import time
time.sleep(120)  # Wait for inference to complete

# Stop and collect data
profiler.stop()

# Analyze results
report = profiler.analyze()
print(report)
```

### Quick One-Shot Profiling

```python
from lm_meter import LMProfiler, LMProfilerConfig

config = LMProfilerConfig(profiling_mode="both")
profiler = LMProfiler(config)

# Setup, start, wait, stop, and analyze in one call
report = profiler.collect_and_analyze(wait_seconds=120)
print(report)
```

### Analyzing Existing Trace Files

If you already have collected trace files, you can analyze them directly:

```python
from lm_meter import TraceParser, LatencyAnalyzer

# Parse trace files
parser = TraceParser()
events = parser.parse_directory("./experiment/session_20250314_143022/traces/")

# Get phase and kernel events separately
phase_events = parser.get_phase_events()
kernel_events = parser.get_kernel_events()

print(f"Total events: {len(events)}")
print(f"Phase events: {len(phase_events)}")
print(f"Kernel events: {len(kernel_events)}")

# Analyze latencies
analyzer = LatencyAnalyzer(events=parser.events)

# Phase-level latencies
phases = analyzer.get_phase_latencies()
for name, stats in phases.items():
    print(f"  {name}: {stats['avg_ms']:.4f} ms (avg), "
          f"{stats['total_ms']:.4f} ms (total), "
          f"count={stats['count']}")

# Kernel-level latencies
kernels = analyzer.get_kernel_latencies()
for name, stats in sorted(kernels.items(), key=lambda x: x[1]['total_ms'], reverse=True):
    print(f"  {name}: {stats['avg_ms']:.4f} ms (avg)")

# Full report
report = analyzer.format_report()
print(report)
```

### Comparing Against Ground Truth

```python
from lm_meter import LatencyAnalyzer

analyzer = LatencyAnalyzer()

# Profiled latencies (from LM-Meter)
profiled = {
    "prefill": 810.4666,
    "decode": 21.4957,
    "softmax": 0.5094,
    "embedding": 0.1034,
}

# Ground truth latencies (from device instrumentation / AGI)
ground_truth = {
    "prefill": 813.6399,
    "decode": 21.4191,
    "softmax": 0.5231,
    "embedding": 0.1097,
}

# Evaluate accuracy
results = analyzer.evaluate_accuracy(profiled, ground_truth)
for name, metrics in results.items():
    print(f"{name}:")
    print(f"  Profiled:     {metrics['profiled_ms']:.4f} ms")
    print(f"  Ground Truth: {metrics['ground_truth_ms']:.4f} ms")
    print(f"  Accuracy (α): {metrics['alpha_pct']:.2f}%")
    print(f"  Error (ε★):   {metrics['epsilon_star']:.3f} µs/ms")
```

## Trace Event Format

LM-Meter trace files follow the [Chrome Trace Event Format](https://docs.google.com/document/d/1CvAClvFfyA5R-PhYUmn5OOQtYMH4h6I0nSsKchNAySU). Each JSON file contains a list of events:

```json
[
  {
    "name": "prefill",
    "ph": "X",
    "ts": 1750274382114019,
    "dur": 810466.6,
    "pid": 1,
    "tid": 12
  },
  {
    "name": "dequantize1_NT_matmul5",
    "ph": "X",
    "ts": 1750274382124019,
    "dur": 81189.9,
    "pid": 1,
    "tid": 12,
    "args": {
      "tokens": 128,
      "latency_ms": 81.19
    }
  }
]
```

### Event Types

| `ph` | Type     | Description |
|:-----|:---------|:------------|
| `B`  | Begin    | Start of a duration event |
| `E`  | End      | End of a duration event |
| `X`  | Complete | Self-contained event with `dur` field |
| `i`  | Instant  | Point-in-time event |

### Standard Fields

| Field  | Description |
|:-------|:------------|
| `name` | Event name (phase name or kernel name) |
| `ph`   | Event type (see table above) |
| `ts`   | Timestamp in microseconds |
| `dur`  | Duration in microseconds (only for `X` events) |
| `pid`  | Process ID |
| `tid`  | Thread ID |
| `args` | Additional metadata (kernel duration, token count, etc.) |

## LLM Inference Phases

LM-Meter identifies the following inference phases:

| Phase | Description |
|:------|:------------|
| **Embedding** | Token embedding lookup and dequantization |
| **Prefill** | Processing all input tokens in parallel |
| **Decode** | Generating output tokens one at a time |
| **Softmax** | Computing attention weights and probability distribution |
| **CopyProbsToCPU** | Transferring probability data from GPU to CPU |
| **Sampling** | Token sampling from the probability distribution |

## Next Steps

- [Evaluation Guide](eval.md) — Detailed analysis and accuracy evaluation
- [Installation Guide](install.md) — Setup prerequisites and build instructions
