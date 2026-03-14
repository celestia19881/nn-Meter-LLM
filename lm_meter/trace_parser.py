# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.
"""Trace parser for LM-Meter profiling data.

Parses Chrome Trace Event / Perfetto JSON trace files collected from
on-device LLM inference via MLC LLM / TVM runtime.

Trace events follow the Chrome Trace Event Format:
  https://docs.google.com/document/d/1CvAClvFfyA5R-PhYUmn5OOQtYMH4h6I0nSsKchNAySU

Supported event types:
  - "B" (Begin): marks the start of a duration event
  - "E" (End): marks the end of a duration event
  - "X" (Complete): a self-contained event with "dur" field
  - "i" (Instant): a point-in-time event
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Well-known phase names in LM-Meter traces
KNOWN_PHASES = {
    "prefill",
    "decode",
    "softmax",
    "embedding",
    "sampling",
    "copyProbsToCPU",
    "CopyProbsToCPU",
}


class TraceEvent:
    """Represents a single trace event from the profiling data.

    Attributes:
        name: Event name (e.g., 'prefill', 'decode_kernel', kernel name).
        phase: Event type character ('B', 'E', 'X', 'i').
        timestamp_us: Timestamp in microseconds.
        duration_us: Duration in microseconds (only for 'X' events).
        pid: Process ID on the device.
        tid: Thread ID (may be numeric or a string identifier).
        args: Additional event arguments (e.g., tokens count, latency_ms).
    """

    def __init__(
        self,
        name: str,
        phase: str,
        timestamp_us: float,
        duration_us: Optional[float] = None,
        pid: Optional[int] = None,
        tid: Optional[Any] = None,
        args: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.phase = phase
        self.timestamp_us = timestamp_us
        self.duration_us = duration_us
        self.pid = pid
        self.tid = tid
        self.args = args or {}

    @property
    def duration_ms(self) -> Optional[float]:
        """Duration in milliseconds, or None if not a complete event."""
        if self.duration_us is not None:
            return self.duration_us / 1000.0
        return None

    @property
    def is_phase_event(self) -> bool:
        """Check if this event corresponds to a known LLM inference phase."""
        return self.name.lower() in {p.lower() for p in KNOWN_PHASES}

    def __repr__(self):
        dur_str = f", dur={self.duration_us}us" if self.duration_us else ""
        return (
            f"TraceEvent(name='{self.name}', ph='{self.phase}', "
            f"ts={self.timestamp_us}{dur_str})"
        )


class TraceParser:
    """Parser for Chrome Trace Event JSON files from LM-Meter.

    Parses one or more trace JSON files and extracts structured events
    for downstream latency analysis.
    """

    def __init__(self):
        self.events: List[TraceEvent] = []
        self._raw_data: List[Dict[str, Any]] = []

    def parse_file(self, filepath: str) -> List[TraceEvent]:
        """Parse a single trace JSON file.

        Args:
            filepath: Path to a trace_*.json file.

        Returns:
            List of TraceEvent objects parsed from the file.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Trace file not found: {filepath}")

        logger.info("Parsing trace file: %s", filepath)
        with open(filepath, "r") as f:
            data = json.load(f)

        # Handle both array format and object format with 'traceEvents' key
        if isinstance(data, dict) and "traceEvents" in data:
            raw_events = data["traceEvents"]
        elif isinstance(data, list):
            raw_events = data
        else:
            raise ValueError(
                f"Unexpected trace format in {filepath}. "
                "Expected a JSON array or object with 'traceEvents' key."
            )

        parsed = []
        for raw in raw_events:
            event = self._parse_event(raw)
            if event:
                parsed.append(event)

        self.events.extend(parsed)
        self._raw_data.extend(raw_events)

        logger.info("Parsed %d events from %s", len(parsed), filepath)
        return parsed

    def parse_directory(self, dirpath: str, pattern: str = "trace_*.json") -> List[TraceEvent]:
        """Parse all trace files in a directory matching the given pattern.

        Args:
            dirpath: Directory containing trace JSON files.
            pattern: Glob pattern for trace files.

        Returns:
            List of all TraceEvent objects parsed.
        """
        import glob

        files = sorted(glob.glob(os.path.join(dirpath, pattern)))
        if not files:
            logger.warning("No trace files matching '%s' found in %s", pattern, dirpath)
            return []

        all_events = []
        for filepath in files:
            events = self.parse_file(filepath)
            all_events.extend(events)

        return all_events

    def get_phase_events(self) -> List[TraceEvent]:
        """Get only phase-level events (prefill, decode, softmax, etc.)."""
        return [e for e in self.events if e.is_phase_event]

    def get_kernel_events(self) -> List[TraceEvent]:
        """Get only kernel-level events (non-phase events with duration)."""
        return [
            e
            for e in self.events
            if not e.is_phase_event and e.duration_us is not None
        ]

    def get_complete_events(self) -> List[TraceEvent]:
        """Get all complete events (phase='X') that have duration info."""
        return [e for e in self.events if e.phase == "X"]

    def get_begin_end_pairs(self) -> List[Dict[str, Any]]:
        """Match Begin ('B') and End ('E') events into duration pairs.

        Returns:
            List of dicts with keys: 'name', 'begin_ts', 'end_ts',
            'duration_us', 'duration_ms', 'tid', 'pid'.
        """
        # Stack-based matching per (tid, pid) to handle nesting
        stacks: Dict[tuple, List[TraceEvent]] = {}
        pairs = []

        sorted_events = sorted(self.events, key=lambda e: e.timestamp_us)
        for event in sorted_events:
            key = (event.tid, event.pid)
            if event.phase == "B":
                stacks.setdefault(key, []).append(event)
            elif event.phase == "E" and key in stacks and stacks[key]:
                begin = stacks[key].pop()
                dur_us = event.timestamp_us - begin.timestamp_us
                pairs.append(
                    {
                        "name": begin.name,
                        "begin_ts": begin.timestamp_us,
                        "end_ts": event.timestamp_us,
                        "duration_us": dur_us,
                        "duration_ms": dur_us / 1000.0,
                        "tid": event.tid,
                        "pid": event.pid,
                    }
                )
        return pairs

    def clear(self):
        """Clear all parsed events."""
        self.events.clear()
        self._raw_data.clear()

    @staticmethod
    def _parse_event(raw: Dict[str, Any]) -> Optional[TraceEvent]:
        """Parse a single raw JSON event dict into a TraceEvent."""
        name = raw.get("name")
        phase = raw.get("ph")
        ts = raw.get("ts")

        if not name or not phase or ts is None:
            return None

        return TraceEvent(
            name=str(name),
            phase=str(phase),
            timestamp_us=float(ts),
            duration_us=float(raw["dur"]) if "dur" in raw else None,
            pid=raw.get("pid"),
            tid=raw.get("tid"),
            args=raw.get("args"),
        )
