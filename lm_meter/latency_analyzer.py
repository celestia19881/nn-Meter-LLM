# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.
"""Latency analyzer for LM-Meter profiling data.

Computes phase-level and kernel-level latency statistics from parsed
trace events, and optionally compares against ground-truth measurements.

Metrics:
  - alpha (α): accuracy percentage, computed as
        α = (1 - |profiled - ground_truth| / ground_truth) * 100
  - epsilon_star (ε★): normalized absolute error in µs/ms, computed as
        ε★ = |profiled - ground_truth| / ground_truth * 1000 (µs per ms)
"""

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

from lm_meter.trace_parser import TraceEvent, TraceParser

logger = logging.getLogger(__name__)


class LatencyAnalyzer:
    """Analyze latency data from LM-Meter trace events.

    Computes statistics over phase-level and kernel-level events,
    and optionally evaluates accuracy against ground-truth data.
    """

    def __init__(self, events: Optional[List[TraceEvent]] = None):
        """Initialize the analyzer with a list of trace events.

        Args:
            events: List of TraceEvent objects. Can also be loaded later
                via :meth:`load_from_parser`.
        """
        self.events: List[TraceEvent] = events or []

    def load_from_parser(self, parser: TraceParser):
        """Load events from a TraceParser instance.

        Args:
            parser: A TraceParser that has already parsed trace files.
        """
        self.events = list(parser.events)
        logger.info("Loaded %d events from parser.", len(self.events))

    def get_phase_latencies(self) -> Dict[str, Dict[str, float]]:
        """Compute latency statistics for each inference phase.

        Returns:
            Dict mapping phase name to latency stats:
              - 'total_ms': sum of all durations for that phase
              - 'count': number of occurrences
              - 'avg_ms': average duration
              - 'min_ms': minimum duration
              - 'max_ms': maximum duration
        """
        phase_durations = self._group_durations_by_name(phase_only=True)
        return self._compute_stats(phase_durations)

    def get_kernel_latencies(self) -> Dict[str, Dict[str, float]]:
        """Compute latency statistics for each kernel.

        Returns:
            Dict mapping kernel name to latency stats.
        """
        kernel_durations = self._group_durations_by_name(phase_only=False)
        return self._compute_stats(kernel_durations)

    def get_end_to_end_latency(self) -> Dict[str, float]:
        """Compute the end-to-end latency across all events.

        Calculates from the earliest to the latest timestamp among
        all events.

        Returns:
            Dict with keys 'start_us', 'end_us', 'duration_us', 'duration_ms'.
        """
        if not self.events:
            return {"start_us": 0, "end_us": 0, "duration_us": 0, "duration_ms": 0}

        timestamps = []
        for e in self.events:
            timestamps.append(e.timestamp_us)
            if e.duration_us is not None:
                timestamps.append(e.timestamp_us + e.duration_us)

        start = min(timestamps)
        end = max(timestamps)
        dur = end - start

        return {
            "start_us": start,
            "end_us": end,
            "duration_us": dur,
            "duration_ms": dur / 1000.0,
        }

    def evaluate_accuracy(
        self,
        profiled: Dict[str, float],
        ground_truth: Dict[str, float],
    ) -> Dict[str, Dict[str, float]]:
        """Evaluate profiling accuracy against ground-truth measurements.

        Args:
            profiled: Dict mapping names to profiled latencies (ms).
            ground_truth: Dict mapping names to ground-truth latencies (ms).

        Returns:
            Dict mapping name to accuracy metrics:
              - 'profiled_ms': profiled latency
              - 'ground_truth_ms': ground-truth latency
              - 'alpha_pct': accuracy percentage (α)
              - 'epsilon_star': normalized error (ε★ in µs/ms)
              - 'abs_error_ms': absolute error in ms
        """
        results = {}
        for name in profiled:
            if name not in ground_truth:
                logger.warning(
                    "No ground-truth value for '%s', skipping accuracy eval.", name
                )
                continue

            prof_val = profiled[name]
            gt_val = ground_truth[name]

            if gt_val == 0:
                logger.warning(
                    "Ground-truth for '%s' is zero, skipping accuracy eval.", name
                )
                continue

            abs_error = abs(prof_val - gt_val)
            alpha = (1.0 - abs_error / gt_val) * 100.0
            epsilon_star = (abs_error / gt_val) * 1000.0  # µs per ms

            results[name] = {
                "profiled_ms": prof_val,
                "ground_truth_ms": gt_val,
                "alpha_pct": round(alpha, 2),
                "epsilon_star": round(epsilon_star, 3),
                "abs_error_ms": round(abs_error, 4),
            }

        return results

    def summary(self) -> Dict[str, Any]:
        """Generate a complete summary of profiling results.

        Returns:
            Dict with keys:
              - 'total_events': number of events
              - 'phase_latencies': phase-level latency stats
              - 'kernel_latencies': kernel-level latency stats
              - 'end_to_end': end-to-end latency stats
        """
        return {
            "total_events": len(self.events),
            "phase_latencies": self.get_phase_latencies(),
            "kernel_latencies": self.get_kernel_latencies(),
            "end_to_end": self.get_end_to_end_latency(),
        }

    def format_report(self) -> str:
        """Format a human-readable profiling report.

        Returns:
            Multiline string with formatted latency statistics.
        """
        s = self.summary()
        lines = [
            "=" * 60,
            "LM-Meter Profiling Report",
            "=" * 60,
            f"Total events parsed: {s['total_events']}",
            "",
            f"End-to-end latency: {s['end_to_end']['duration_ms']:.4f} ms",
            "",
        ]

        if s["phase_latencies"]:
            lines.append("--- Phase-Level Latencies ---")
            lines.append(
                f"{'Phase':<30} {'Total (ms)':>12} {'Avg (ms)':>10} "
                f"{'Count':>6} {'Min (ms)':>10} {'Max (ms)':>10}"
            )
            for name, stats in sorted(s["phase_latencies"].items()):
                lines.append(
                    f"{name:<30} {stats['total_ms']:>12.4f} "
                    f"{stats['avg_ms']:>10.4f} {stats['count']:>6} "
                    f"{stats['min_ms']:>10.4f} {stats['max_ms']:>10.4f}"
                )
            lines.append("")

        if s["kernel_latencies"]:
            lines.append("--- Kernel-Level Latencies ---")
            lines.append(
                f"{'Kernel':<45} {'Total (ms)':>12} {'Avg (ms)':>10} "
                f"{'Count':>6}"
            )
            for name, stats in sorted(
                s["kernel_latencies"].items(),
                key=lambda x: x[1]["total_ms"],
                reverse=True,
            ):
                lines.append(
                    f"{name:<45} {stats['total_ms']:>12.4f} "
                    f"{stats['avg_ms']:>10.4f} {stats['count']:>6}"
                )

        lines.append("=" * 60)
        return "\n".join(lines)

    def _group_durations_by_name(
        self, phase_only: bool = False
    ) -> Dict[str, List[float]]:
        """Group event durations (ms) by event name.

        Args:
            phase_only: If True, only include phase-level events.
                If False, include only non-phase (kernel) events.

        Returns:
            Dict mapping event name to list of durations in ms.
        """
        grouped: Dict[str, List[float]] = defaultdict(list)
        for event in self.events:
            if event.duration_us is None:
                continue
            if phase_only and not event.is_phase_event:
                continue
            if not phase_only and event.is_phase_event:
                continue
            grouped[event.name].append(event.duration_us / 1000.0)
        return dict(grouped)

    @staticmethod
    def _compute_stats(
        grouped: Dict[str, List[float]],
    ) -> Dict[str, Dict[str, float]]:
        """Compute summary statistics for grouped durations.

        Args:
            grouped: Dict mapping name to list of durations (ms).

        Returns:
            Dict mapping name to stats dict.
        """
        stats = {}
        for name, durations in grouped.items():
            total = sum(durations)
            count = len(durations)
            stats[name] = {
                "total_ms": round(total, 4),
                "count": count,
                "avg_ms": round(total / count, 4) if count > 0 else 0,
                "min_ms": round(min(durations), 4) if durations else 0,
                "max_ms": round(max(durations), 4) if durations else 0,
            }
        return stats
