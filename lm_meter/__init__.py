# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.
"""
LM-Meter: Online Kernel-Level Profiler for On-Device Large Language Models (LLMs).

This module extends nn-Meter to support LLM inference latency profiling on
mobile and edge devices (e.g., Android phones). It provides:

  - ADB-based communication with Android devices
  - Trace data collection from MLC LLM / TVM runtime
  - Phase-level and kernel-level latency parsing and analysis
  - Latency reporting and visualization

Reference:
  Wang et al., "lm-Meter: Unveiling Runtime Inference Latency for On-Device
  Language Models," Proc. ACM/IEEE SEC, 2025.
  Original project: https://github.com/amai-gsu/LM-Meter
"""

from lm_meter.adb_utils import ADBDevice
from lm_meter.trace_parser import TraceParser
from lm_meter.latency_analyzer import LatencyAnalyzer
from lm_meter.profiler import LMProfiler
from lm_meter.config import LMProfilerConfig

__all__ = [
    "ADBDevice",
    "TraceParser",
    "LatencyAnalyzer",
    "LMProfiler",
    "LMProfilerConfig",
]
