# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.
"""Configuration management for LM-Meter profiler."""

import os
import yaml
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LMProfilerConfig:
    """Configuration for LM-Meter profiling sessions.

    Attributes:
        device_serial: ADB device serial number (None for auto-detect).
        trace_output_dir: Directory on the host to store collected traces.
        device_trace_dir: Directory on the Android device where traces are saved.
        logcat_tags: Logcat filter tags for MLC/TVM runtime logs.
        profiling_mode: One of 'phase', 'kernel', or 'both'.
        clear_logcat_before_run: Whether to clear logcat buffer before profiling.
        pull_traces: Whether to pull trace files from the device after profiling.
        log_filename: Name of the logcat output file.
    """

    device_serial: Optional[str] = None
    trace_output_dir: str = "./lm_meter_output"
    device_trace_dir: str = "/data/local/tmp/traces"
    logcat_tags: list = field(
        default_factory=lambda: ["TVM_RUNTIME", "MLC_Profile", "MLC_EVENT"]
    )
    profiling_mode: str = "both"
    clear_logcat_before_run: bool = True
    pull_traces: bool = True
    log_filename: str = "tvm_mlc.log"

    def __post_init__(self):
        if self.profiling_mode not in ("phase", "kernel", "both"):
            raise ValueError(
                f"profiling_mode must be 'phase', 'kernel', or 'both', "
                f"got '{self.profiling_mode}'"
            )

    def to_dict(self):
        """Serialize configuration to a dictionary."""
        return {
            "device_serial": self.device_serial,
            "trace_output_dir": self.trace_output_dir,
            "device_trace_dir": self.device_trace_dir,
            "logcat_tags": self.logcat_tags,
            "profiling_mode": self.profiling_mode,
            "clear_logcat_before_run": self.clear_logcat_before_run,
            "pull_traces": self.pull_traces,
            "log_filename": self.log_filename,
        }

    @classmethod
    def from_dict(cls, data):
        """Create configuration from a dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def save(self, path):
        """Save configuration to a YAML file."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)

    @classmethod
    def load(cls, path):
        """Load configuration from a YAML file."""
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)
