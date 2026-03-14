# LM-Meter Evaluation Guide

This guide explains how to evaluate LM-Meter profiling results and compare them against ground-truth measurements.

## Accuracy Metrics

LM-Meter uses two primary metrics to evaluate profiling accuracy:

### α (Alpha) — Accuracy Percentage

Measures how close the profiled latency is to the ground truth:

```
α = (1 - |profiled - ground_truth| / ground_truth) × 100%
```

- **α = 100%**: Perfect accuracy
- **α ≥ 99%**: Excellent (typical for phase-level profiling)
- **α ≥ 95%**: Good (typical for kernel-level profiling)
- **α < 90%**: May need investigation

### ε★ (Epsilon Star) — Normalized Error

Normalized absolute error expressed in microseconds per millisecond:

```
ε★ = |profiled - ground_truth| / ground_truth × 1000 (µs/ms)
```

Lower is better. ε★ < 10 µs/ms indicates very high accuracy.

## Running Evaluations

### Using the Python API

```python
from lm_meter import TraceParser, LatencyAnalyzer

# Parse profiling data
parser = TraceParser()
parser.parse_directory("./lm_meter_output/session_20250314_143022/traces/")

# Create analyzer
analyzer = LatencyAnalyzer(events=parser.events)

# Get the profiling summary
summary = analyzer.summary()
print(f"Total events: {summary['total_events']}")
print(f"End-to-end latency: {summary['end_to_end']['duration_ms']:.2f} ms")

# Phase-level results
print("\n--- Phase-Level ---")
for name, stats in summary['phase_latencies'].items():
    print(f"  {name}: {stats['avg_ms']:.4f} ms (avg over {stats['count']} runs)")

# Kernel-level results
print("\n--- Kernel-Level ---")
for name, stats in summary['kernel_latencies'].items():
    print(f"  {name}: {stats['avg_ms']:.4f} ms")
```

### Comparing Against Ground Truth

If you have ground-truth measurements (e.g., from GPU instrumentation or manufacturer tools):

```python
from lm_meter import LatencyAnalyzer

analyzer = LatencyAnalyzer()

# Example: Gemma-2-2B-it on Pixel 8 Pro (from the LM-Meter paper)
profiled_kernels = {
    "dequantize1_NT_matmul5": 81.1899,
    "dequantize2_NT_matmul6": 31.3407,
    "dequantize3_NT_matmul7": 330.3757,
    "dequantize4_NT_matmul8": 367.5603,
}

ground_truth_kernels = {
    "dequantize1_NT_matmul5": 82.1329,
    "dequantize2_NT_matmul6": 31.7568,
    "dequantize3_NT_matmul7": 332.7218,
    "dequantize4_NT_matmul8": 367.0284,
}

results = analyzer.evaluate_accuracy(profiled_kernels, ground_truth_kernels)

print("Kernel-Level Accuracy (Gemma-2-2B-it, Pixel 8 Pro):")
print(f"{'Kernel':<35} {'Profiled':>10} {'GT':>10} {'α (%)':>8} {'ε★':>10}")
print("-" * 78)
for name, m in results.items():
    print(f"{name:<35} {m['profiled_ms']:>10.4f} {m['ground_truth_ms']:>10.4f} "
          f"{m['alpha_pct']:>8.2f} {m['epsilon_star']:>10.3f}")
```

## Reference Results

The following tables show reference profiling results from the LM-Meter paper.

### Phase-Level Results (Pixel 8 Pro)

| Model | Phase | LM-Meter (ms) | Ground Truth (ms) | α (%) | ε★ (µs/ms) |
|:------|:------|:---------------|:-------------------|:------|:------------|
| Llama-3.2-3B | Prefill | 3433.8628 | 3433.8142 | 99.99 | 0.014 |
| Llama-3.2-3B | Decode | 62.5669 | 62.5303 | 99.94 | 0.585 |
| Llama-3.2-3B | End-to-end | 3640.4104 | 3640.3191 | 99.99 | 0.025 |
| Gemma-2-2B | Prefill | 9301.1318 | 9301.0589 | 99.99 | 0.008 |
| Gemma-2-2B | Decode | 54.5909 | 54.5557 | 99.94 | 0.646 |
| Gemma-2-2B | End-to-end | 9859.5473 | 9859.4329 | 99.99 | 0.012 |

### Kernel-Level Results (Gemma-2-2B-it, Pixel 8 Pro)

| Kernel | Phase | LM-Meter (ms) | GT (ms) | α (%) |
|:-------|:------|:---------------|:--------|:------|
| dequantize1_NT_matmul5 | Prefill | 81.1899 | 82.1329 | 98.85 |
| dequantize2_NT_matmul6 | Prefill | 31.3407 | 31.7568 | 98.69 |
| dequantize3_NT_matmul7 | Prefill | 330.3757 | 332.7218 | 99.29 |
| dequantize4_NT_matmul8 | Prefill | 367.5603 | 367.0284 | 99.86 |

### Profiling Overhead

LM-Meter introduces minimal overhead:

| CPU Governor | Phase | No Profiling (tok/s) | LM-Meter (tok/s) | Slowdown |
|:-------------|:------|:---------------------|:------------------|:---------|
| Performance | Prefill | 0.680 | 0.680 | 0.00% |
| Performance | Decode | 8.327 | 8.319 | 0.10% |
| Powersave | Prefill | 0.658 | 0.641 | 2.58% |
| Powersave | Decode | 2.703 | 2.676 | 0.99% |

## Generating Reports

### Text Report

```python
report = analyzer.format_report()
print(report)

# Save to file
with open("profiling_report.txt", "w") as f:
    f.write(report)
```

### JSON Export

```python
import json

summary = analyzer.summary()
with open("profiling_results.json", "w") as f:
    json.dump(summary, f, indent=2)
```

## Tips for Accurate Profiling

1. **Warm up the device**: Run inference once before profiling to warm up GPU caches
2. **Set CPU governor**: Use `performance` mode for consistent results
   ```bash
   adb shell "echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
   ```
3. **Close background apps**: Minimize interference from other processes
4. **Multiple runs**: Average results over multiple inference runs
5. **Consistent prompts**: Use the same input prompt length for reproducible results

## Next Steps

- [Usage Guide](usage.md) — How to run profiling sessions
- [Installation Guide](install.md) — Setup and prerequisites
