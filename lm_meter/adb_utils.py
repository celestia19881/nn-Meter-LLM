# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.
"""ADB communication utilities for LM-Meter.

Provides a wrapper around the Android Debug Bridge (adb) command-line tool
for interacting with Android devices during LLM profiling sessions.
"""

import logging
import os
import subprocess
import time
from typing import List, Optional

logger = logging.getLogger(__name__)


class ADBDevice:
    """Wrapper for ADB operations on a connected Android device.

    Args:
        serial: Device serial number. If None, the first connected device
            is used automatically.
    """

    def __init__(self, serial: Optional[str] = None):
        self.serial = serial
        self._verify_adb()

    def _verify_adb(self):
        """Check that adb is available on the host."""
        try:
            self._run_host_cmd(["adb", "version"])
        except FileNotFoundError:
            raise EnvironmentError(
                "adb not found in PATH. Please install Android SDK "
                "platform-tools and ensure 'adb' is accessible."
            )

    def _build_adb_cmd(self, args: List[str]) -> List[str]:
        """Build an adb command list with optional serial flag."""
        cmd = ["adb"]
        if self.serial:
            cmd.extend(["-s", self.serial])
        cmd.extend(args)
        return cmd

    @staticmethod
    def _run_host_cmd(cmd: List[str], timeout: int = 60) -> str:
        """Run a command on the host and return stdout."""
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            logger.error("Command failed: %s\nstderr: %s", cmd, result.stderr)
            raise RuntimeError(
                f"Command {' '.join(cmd)} failed with code {result.returncode}: "
                f"{result.stderr.strip()}"
            )
        return result.stdout.strip()

    def shell(self, command: str, timeout: int = 60) -> str:
        """Run a shell command on the device via adb shell.

        Args:
            command: Shell command string to execute on the device.
            timeout: Maximum seconds to wait for the command.

        Returns:
            Standard output from the device command.
        """
        cmd = self._build_adb_cmd(["shell", command])
        return self._run_host_cmd(cmd, timeout=timeout)

    def pull(self, remote_path: str, local_path: str, timeout: int = 120) -> str:
        """Pull a file or directory from the device.

        Args:
            remote_path: Path on the Android device.
            local_path: Destination path on the host.
            timeout: Maximum seconds to wait.

        Returns:
            adb pull output.
        """
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        cmd = self._build_adb_cmd(["pull", remote_path, local_path])
        return self._run_host_cmd(cmd, timeout=timeout)

    def push(self, local_path: str, remote_path: str, timeout: int = 120) -> str:
        """Push a file or directory to the device.

        Args:
            local_path: Path on the host.
            remote_path: Destination path on the Android device.
            timeout: Maximum seconds to wait.

        Returns:
            adb push output.
        """
        cmd = self._build_adb_cmd(["push", local_path, remote_path])
        return self._run_host_cmd(cmd, timeout=timeout)

    def clear_logcat(self):
        """Clear the logcat buffer on the device."""
        cmd = self._build_adb_cmd(["logcat", "-c"])
        self._run_host_cmd(cmd)
        logger.info("Logcat buffer cleared.")

    def stream_logcat(
        self,
        tags: List[str],
        output_file: str,
        duration: Optional[int] = None,
    ):
        """Stream logcat output filtered by tags to a file.

        Args:
            tags: List of logcat tag filters (e.g., ['TVM_RUNTIME:V']).
            output_file: Path on the host to write the log output.
            duration: Optional duration in seconds; if None, runs until
                interrupted.
        """
        tag_filters = [f"{t}:V" for t in tags] + ["*:S"]
        cmd = self._build_adb_cmd(["logcat"] + tag_filters)

        os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)

        logger.info("Streaming logcat to %s (tags: %s)", output_file, tags)
        with open(output_file, "w") as f:
            proc = subprocess.Popen(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
            try:
                if duration:
                    time.sleep(duration)
                    proc.terminate()
                else:
                    proc.wait()
            except KeyboardInterrupt:
                proc.terminate()
            finally:
                proc.wait()
        logger.info("Logcat streaming finished: %s", output_file)

    def remove_device_files(self, path_pattern: str):
        """Remove files matching a pattern on the device.

        Args:
            path_pattern: Shell glob pattern on the device
                (e.g., '/data/local/tmp/traces/trace_*.json').
        """
        self.shell(f"rm -f {path_pattern}")
        logger.info("Removed device files matching: %s", path_pattern)

    def list_device_files(self, directory: str) -> List[str]:
        """List files in a directory on the device.

        Args:
            directory: Directory path on the device.

        Returns:
            List of filenames in the directory.
        """
        try:
            output = self.shell(f"ls {directory}")
            return [f.strip() for f in output.split("\n") if f.strip()]
        except RuntimeError:
            return []

    def get_device_model(self) -> str:
        """Get the device model name."""
        return self.shell("getprop ro.product.model")

    def get_android_version(self) -> str:
        """Get the Android version string."""
        return self.shell("getprop ro.build.version.release")

    @staticmethod
    def list_connected_devices() -> List[str]:
        """List all connected ADB device serial numbers."""
        output = subprocess.run(
            ["adb", "devices"], capture_output=True, text=True
        ).stdout
        devices = []
        for line in output.strip().split("\n")[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        return devices
