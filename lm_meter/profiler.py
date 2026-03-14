# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.
"""Main LM-Meter profiler orchestrator.

Coordinates ADB device interaction, logcat streaming, trace collection,
and latency analysis for on-device LLM inference profiling.
"""

import logging
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from lm_meter.adb_utils import ADBDevice
from lm_meter.config import LMProfilerConfig
from lm_meter.latency_analyzer import LatencyAnalyzer
from lm_meter.trace_parser import TraceParser

logger = logging.getLogger(__name__)


class LMProfiler:
    """High-level profiler for on-device LLM inference latency.

    Manages the full profiling lifecycle:
      1. Connect to an Android device via ADB
      2. Clean old traces and logcat buffers
      3. Stream logcat and collect trace data during inference
      4. Pull trace files from the device
      5. Parse and analyze latency data

    Args:
        config: LMProfilerConfig instance with profiling settings.

    Example usage::

        from lm_meter import LMProfiler, LMProfilerConfig

        config = LMProfilerConfig(
            profiling_mode="both",
            trace_output_dir="./my_experiment",
        )
        profiler = LMProfiler(config)
        profiler.setup()

        # Start profiling (then launch the LLM app on the phone)
        profiler.start()

        # ... wait for inference to complete ...

        # Stop and collect data
        profiler.stop()
        report = profiler.analyze()
        print(report)
    """

    def __init__(self, config: Optional[LMProfilerConfig] = None):
        self.config = config or LMProfilerConfig()
        self.device: Optional[ADBDevice] = None
        self.parser = TraceParser()
        self.analyzer = LatencyAnalyzer()
        self._logcat_thread: Optional[threading.Thread] = None
        self._logcat_running = False
        self._session_dir: Optional[str] = None

    def setup(self):
        """Initialize connection to the Android device and prepare the session.

        Creates a timestamped output directory and connects to the device.
        """
        # Create timestamped session directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._session_dir = os.path.join(
            self.config.trace_output_dir, f"session_{timestamp}"
        )
        os.makedirs(self._session_dir, exist_ok=True)
        os.makedirs(os.path.join(self._session_dir, "traces"), exist_ok=True)

        # Save config
        self.config.save(os.path.join(self._session_dir, "config.yaml"))

        # Connect to device
        self.device = ADBDevice(serial=self.config.device_serial)

        # Log device info
        try:
            model = self.device.get_device_model()
            android_ver = self.device.get_android_version()
            logger.info(
                "Connected to device: %s (Android %s)", model, android_ver
            )
        except Exception as e:
            logger.warning("Could not retrieve device info: %s", e)

    def start(self):
        """Begin the profiling session.

        Clears old traces, resets logcat, and starts streaming logs.
        The user should then launch the LLM inference app on the device.
        """
        if self.device is None:
            raise RuntimeError("Call setup() before start().")

        # Clean old traces on device
        trace_pattern = os.path.join(self.config.device_trace_dir, "trace_*.json")
        self.device.remove_device_files(trace_pattern)
        logger.info("Cleaned old traces on device.")

        # Clear logcat buffer
        if self.config.clear_logcat_before_run:
            self.device.clear_logcat()

        # Start logcat streaming in background thread
        self._logcat_running = True
        log_path = os.path.join(self._session_dir, self.config.log_filename)

        self._logcat_thread = threading.Thread(
            target=self._stream_logcat_worker,
            args=(log_path,),
            daemon=True,
        )
        self._logcat_thread.start()
        logger.info(
            "Profiling started. Launch the LLM app on the device and "
            "begin inference."
        )

    def stop(self):
        """Stop the profiling session and collect trace data.

        Terminates logcat streaming and pulls trace files from the device.
        """
        # Stop logcat streaming
        self._logcat_running = False
        if self._logcat_thread and self._logcat_thread.is_alive():
            self._logcat_thread.join(timeout=5)
        logger.info("Logcat streaming stopped.")

        # Pull traces from device
        if self.config.pull_traces and self.device:
            self._pull_traces()

    def analyze(self) -> str:
        """Parse collected traces and generate a latency report.

        Returns:
            Formatted string report of profiling results.
        """
        if self._session_dir is None:
            raise RuntimeError("No session directory. Call setup() first.")

        traces_dir = os.path.join(self._session_dir, "traces")

        # Parse all trace files
        self.parser.clear()
        events = self.parser.parse_directory(traces_dir)

        if not events:
            return "No trace events found. Ensure the LLM app was run during profiling."

        # Analyze
        self.analyzer.events = list(self.parser.events)
        report = self.analyzer.format_report()

        # Save report
        report_path = os.path.join(self._session_dir, "report.txt")
        with open(report_path, "w") as f:
            f.write(report)
        logger.info("Report saved to %s", report_path)

        return report

    def get_summary(self) -> Dict[str, Any]:
        """Get structured summary data after analysis.

        Returns:
            Dictionary with phase and kernel latency statistics.
        """
        return self.analyzer.summary()

    def get_session_dir(self) -> Optional[str]:
        """Get the path to the current session output directory."""
        return self._session_dir

    def collect_and_analyze(self, wait_seconds: int = 60) -> str:
        """Convenience method: setup, start, wait, stop, and analyze.

        Args:
            wait_seconds: How long to wait (seconds) for inference to complete.

        Returns:
            Formatted profiling report string.
        """
        self.setup()
        self.start()

        logger.info("Waiting %d seconds for inference...", wait_seconds)
        try:
            time.sleep(wait_seconds)
        except KeyboardInterrupt:
            logger.info("Interrupted by user.")

        self.stop()
        return self.analyze()

    def analyze_existing_traces(self, traces_dir: str) -> str:
        """Analyze previously collected trace files without running profiling.

        Args:
            traces_dir: Path to directory containing trace_*.json files.

        Returns:
            Formatted profiling report string.
        """
        self.parser.clear()
        events = self.parser.parse_directory(traces_dir)

        if not events:
            return "No trace events found in the specified directory."

        self.analyzer.events = list(self.parser.events)
        return self.analyzer.format_report()

    def _stream_logcat_worker(self, log_path: str):
        """Background worker for streaming logcat."""
        import subprocess

        tag_filters = [f"{t}:V" for t in self.config.logcat_tags] + ["*:S"]
        cmd = ["adb"]
        if self.config.device_serial:
            cmd.extend(["-s", self.config.device_serial])
        cmd.extend(["logcat"] + tag_filters)

        try:
            with open(log_path, "w") as f:
                proc = subprocess.Popen(
                    cmd, stdout=f, stderr=subprocess.PIPE, text=True
                )
                while self._logcat_running:
                    time.sleep(0.5)
                proc.terminate()
                proc.wait(timeout=5)
        except Exception as e:
            logger.error("Logcat streaming error: %s", e)

    def _pull_traces(self):
        """Pull trace files from the device to the session directory."""
        traces_local = os.path.join(self._session_dir, "traces")
        device_files = self.device.list_device_files(self.config.device_trace_dir)

        trace_files = [f for f in device_files if f.startswith("trace_") and f.endswith(".json")]
        if not trace_files:
            logger.warning("No trace files found on device in %s", self.config.device_trace_dir)
            return

        for fname in trace_files:
            remote = os.path.join(self.config.device_trace_dir, fname)
            local = os.path.join(traces_local, fname)
            try:
                self.device.pull(remote, local)
                logger.info("Pulled: %s -> %s", remote, local)
            except RuntimeError as e:
                logger.error("Failed to pull %s: %s", fname, e)

        logger.info("Pulled %d trace files from device.", len(trace_files))
