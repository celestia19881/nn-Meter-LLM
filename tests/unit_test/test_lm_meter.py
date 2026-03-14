# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.
"""Unit tests for the LM-Meter module."""

import json
import os
import tempfile
import unittest

from lm_meter.config import LMProfilerConfig
from lm_meter.trace_parser import TraceParser, TraceEvent
from lm_meter.latency_analyzer import LatencyAnalyzer


class TestLMProfilerConfig(unittest.TestCase):
    """Tests for LMProfilerConfig."""

    def test_default_config(self):
        config = LMProfilerConfig()
        self.assertEqual(config.profiling_mode, "both")
        self.assertEqual(config.trace_output_dir, "./lm_meter_output")
        self.assertTrue(config.clear_logcat_before_run)
        self.assertTrue(config.pull_traces)

    def test_invalid_profiling_mode(self):
        with self.assertRaises(ValueError):
            LMProfilerConfig(profiling_mode="invalid")

    def test_valid_profiling_modes(self):
        for mode in ("phase", "kernel", "both"):
            config = LMProfilerConfig(profiling_mode=mode)
            self.assertEqual(config.profiling_mode, mode)

    def test_to_dict(self):
        config = LMProfilerConfig(profiling_mode="kernel", device_serial="ABC123")
        d = config.to_dict()
        self.assertEqual(d["profiling_mode"], "kernel")
        self.assertEqual(d["device_serial"], "ABC123")
        self.assertIn("logcat_tags", d)

    def test_from_dict(self):
        data = {"profiling_mode": "phase", "device_serial": "XYZ"}
        config = LMProfilerConfig.from_dict(data)
        self.assertEqual(config.profiling_mode, "phase")
        self.assertEqual(config.device_serial, "XYZ")

    def test_save_and_load(self):
        config = LMProfilerConfig(
            profiling_mode="kernel",
            device_serial="TEST123",
            trace_output_dir="/tmp/test_output",
        )
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            path = f.name
        try:
            config.save(path)
            loaded = LMProfilerConfig.load(path)
            self.assertEqual(loaded.profiling_mode, "kernel")
            self.assertEqual(loaded.device_serial, "TEST123")
        finally:
            os.unlink(path)


class TestTraceParser(unittest.TestCase):
    """Tests for TraceParser."""

    def _create_trace_file(self, events):
        """Create a temporary trace JSON file with the given events."""
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", prefix="trace_", delete=False
        )
        json.dump(events, f)
        f.close()
        return f.name

    def test_parse_complete_events(self):
        raw_events = [
            {"name": "prefill", "ph": "X", "ts": 1000000, "dur": 500000, "pid": 1, "tid": 1},
            {"name": "decode", "ph": "X", "ts": 1500000, "dur": 200000, "pid": 1, "tid": 1},
            {"name": "dequantize1_NT_matmul5", "ph": "X", "ts": 1000100, "dur": 80000, "pid": 1, "tid": 2},
        ]
        filepath = self._create_trace_file(raw_events)
        try:
            parser = TraceParser()
            events = parser.parse_file(filepath)
            self.assertEqual(len(events), 3)
            self.assertEqual(events[0].name, "prefill")
            self.assertEqual(events[0].duration_us, 500000)
            self.assertAlmostEqual(events[0].duration_ms, 500.0)
        finally:
            os.unlink(filepath)

    def test_parse_begin_end_events(self):
        raw_events = [
            {"name": "prefill", "ph": "B", "ts": 1000000, "pid": 1, "tid": 1},
            {"name": "prefill", "ph": "E", "ts": 1500000, "pid": 1, "tid": 1},
        ]
        filepath = self._create_trace_file(raw_events)
        try:
            parser = TraceParser()
            parser.parse_file(filepath)
            pairs = parser.get_begin_end_pairs()
            self.assertEqual(len(pairs), 1)
            self.assertEqual(pairs[0]["name"], "prefill")
            self.assertEqual(pairs[0]["duration_us"], 500000)
            self.assertAlmostEqual(pairs[0]["duration_ms"], 500.0)
        finally:
            os.unlink(filepath)

    def test_parse_object_format(self):
        raw_data = {
            "traceEvents": [
                {"name": "decode", "ph": "X", "ts": 2000000, "dur": 100000, "pid": 1, "tid": 1},
            ]
        }
        filepath = self._create_trace_file(raw_data)
        try:
            parser = TraceParser()
            events = parser.parse_file(filepath)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].name, "decode")
        finally:
            os.unlink(filepath)

    def test_get_phase_events(self):
        raw_events = [
            {"name": "prefill", "ph": "X", "ts": 1000000, "dur": 500000, "pid": 1, "tid": 1},
            {"name": "decode", "ph": "X", "ts": 1500000, "dur": 200000, "pid": 1, "tid": 1},
            {"name": "dequantize_matmul", "ph": "X", "ts": 1000100, "dur": 80000, "pid": 1, "tid": 2},
        ]
        filepath = self._create_trace_file(raw_events)
        try:
            parser = TraceParser()
            parser.parse_file(filepath)
            phase_events = parser.get_phase_events()
            self.assertEqual(len(phase_events), 2)
            self.assertTrue(all(e.is_phase_event for e in phase_events))
        finally:
            os.unlink(filepath)

    def test_get_kernel_events(self):
        raw_events = [
            {"name": "prefill", "ph": "X", "ts": 1000000, "dur": 500000, "pid": 1, "tid": 1},
            {"name": "dequantize_matmul", "ph": "X", "ts": 1000100, "dur": 80000, "pid": 1, "tid": 2},
            {"name": "softmax_kernel", "ph": "X", "ts": 1080100, "dur": 5000, "pid": 1, "tid": 2},
        ]
        filepath = self._create_trace_file(raw_events)
        try:
            parser = TraceParser()
            parser.parse_file(filepath)
            kernel_events = parser.get_kernel_events()
            self.assertEqual(len(kernel_events), 2)
            self.assertFalse(any(e.is_phase_event for e in kernel_events))
        finally:
            os.unlink(filepath)

    def test_parse_directory(self):
        tmpdir = tempfile.mkdtemp()
        try:
            # Create two trace files
            for i in range(2):
                events = [
                    {"name": f"kernel_{i}", "ph": "X", "ts": 1000000 + i * 100000, "dur": 50000, "pid": 1, "tid": 1},
                ]
                path = os.path.join(tmpdir, f"trace_{i:03d}.json")
                with open(path, "w") as f:
                    json.dump(events, f)

            parser = TraceParser()
            events = parser.parse_directory(tmpdir)
            self.assertEqual(len(events), 2)
        finally:
            import shutil
            shutil.rmtree(tmpdir)

    def test_parse_file_not_found(self):
        parser = TraceParser()
        with self.assertRaises(FileNotFoundError):
            parser.parse_file("/nonexistent/trace.json")

    def test_clear(self):
        parser = TraceParser()
        parser.events = [TraceEvent("test", "X", 0, 100)]
        parser.clear()
        self.assertEqual(len(parser.events), 0)


class TestTraceEvent(unittest.TestCase):
    """Tests for TraceEvent."""

    def test_phase_event_detection(self):
        for name in ["prefill", "decode", "softmax", "embedding", "sampling"]:
            event = TraceEvent(name=name, phase="X", timestamp_us=0, duration_us=100)
            self.assertTrue(event.is_phase_event, f"{name} should be a phase event")

    def test_non_phase_event(self):
        event = TraceEvent(name="dequantize_matmul", phase="X", timestamp_us=0, duration_us=100)
        self.assertFalse(event.is_phase_event)

    def test_duration_ms(self):
        event = TraceEvent(name="test", phase="X", timestamp_us=0, duration_us=1500)
        self.assertAlmostEqual(event.duration_ms, 1.5)

    def test_no_duration(self):
        event = TraceEvent(name="test", phase="i", timestamp_us=0)
        self.assertIsNone(event.duration_ms)


class TestLatencyAnalyzer(unittest.TestCase):
    """Tests for LatencyAnalyzer."""

    def _make_events(self):
        """Create sample events for testing."""
        return [
            TraceEvent("prefill", "X", 1000000, duration_us=500000),
            TraceEvent("prefill", "X", 2000000, duration_us=510000),
            TraceEvent("decode", "X", 3000000, duration_us=20000),
            TraceEvent("dequantize_matmul", "X", 1000100, duration_us=80000),
            TraceEvent("attention_kernel", "X", 1080100, duration_us=5000),
        ]

    def test_phase_latencies(self):
        analyzer = LatencyAnalyzer(events=self._make_events())
        phases = analyzer.get_phase_latencies()
        self.assertIn("prefill", phases)
        self.assertIn("decode", phases)
        self.assertEqual(phases["prefill"]["count"], 2)
        self.assertAlmostEqual(phases["prefill"]["total_ms"], 1010.0)

    def test_kernel_latencies(self):
        analyzer = LatencyAnalyzer(events=self._make_events())
        kernels = analyzer.get_kernel_latencies()
        self.assertIn("dequantize_matmul", kernels)
        self.assertIn("attention_kernel", kernels)
        self.assertNotIn("prefill", kernels)

    def test_end_to_end_latency(self):
        analyzer = LatencyAnalyzer(events=self._make_events())
        e2e = analyzer.get_end_to_end_latency()
        self.assertGreater(e2e["duration_us"], 0)
        self.assertGreater(e2e["duration_ms"], 0)

    def test_empty_events(self):
        analyzer = LatencyAnalyzer(events=[])
        e2e = analyzer.get_end_to_end_latency()
        self.assertEqual(e2e["duration_us"], 0)

    def test_evaluate_accuracy(self):
        analyzer = LatencyAnalyzer()
        profiled = {"prefill": 81.1899, "decode": 0.3643}
        ground_truth = {"prefill": 82.1329, "decode": 0.3737}

        results = analyzer.evaluate_accuracy(profiled, ground_truth)
        self.assertIn("prefill", results)
        self.assertIn("decode", results)

        # Check prefill accuracy
        self.assertGreater(results["prefill"]["alpha_pct"], 98.0)
        self.assertLess(results["prefill"]["epsilon_star"], 15.0)

        # Check that all fields are present
        for name in results:
            self.assertIn("profiled_ms", results[name])
            self.assertIn("ground_truth_ms", results[name])
            self.assertIn("alpha_pct", results[name])
            self.assertIn("epsilon_star", results[name])
            self.assertIn("abs_error_ms", results[name])

    def test_evaluate_accuracy_missing_ground_truth(self):
        analyzer = LatencyAnalyzer()
        profiled = {"prefill": 100.0, "unknown_phase": 50.0}
        ground_truth = {"prefill": 100.0}

        results = analyzer.evaluate_accuracy(profiled, ground_truth)
        self.assertIn("prefill", results)
        self.assertNotIn("unknown_phase", results)

    def test_format_report(self):
        analyzer = LatencyAnalyzer(events=self._make_events())
        report = analyzer.format_report()
        self.assertIn("LM-Meter Profiling Report", report)
        self.assertIn("prefill", report)
        self.assertIn("decode", report)

    def test_summary(self):
        analyzer = LatencyAnalyzer(events=self._make_events())
        summary = analyzer.summary()
        self.assertIn("total_events", summary)
        self.assertIn("phase_latencies", summary)
        self.assertIn("kernel_latencies", summary)
        self.assertIn("end_to_end", summary)
        self.assertEqual(summary["total_events"], 5)


if __name__ == "__main__":
    unittest.main()
