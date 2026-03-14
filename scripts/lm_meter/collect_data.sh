#!/usr/bin/env bash
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.
#
# LM-Meter Data Collection Script
#
# Collects phase-level and kernel-level latency data from an Android device
# running an LLM inference app (MLC LLM).
#
# This script:
#   1. Removes old trace files on the device
#   2. Clears logcat buffers
#   3. Streams runtime logs (TVM_RUNTIME, MLC_Profile, MLC_EVENT)
#   4. Pulls structured trace JSON files from the device
#   5. Organizes outputs under a timestamped folder
#
# Prerequisites:
#   - Android device connected via USB with ADB enabled
#   - MLC LLM app installed on the device
#   - adb in PATH
#
# Usage:
#   chmod +x collect_data.sh
#   ./collect_data.sh [--output-dir <dir>] [--duration <seconds>]
#
# Reference: https://github.com/amai-gsu/LM-Meter

set -euo pipefail

# Default settings
OUTPUT_DIR="./lm_meter_output"
DURATION=120
DEVICE_TRACE_DIR="/data/local/tmp/traces"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --duration)
            DURATION="$2"
            shift 2
            ;;
        --device-serial|-s)
            ADB_SERIAL="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [--output-dir <dir>] [--duration <seconds>] [-s <serial>]"
            echo ""
            echo "Options:"
            echo "  --output-dir   Host directory for output files (default: ./lm_meter_output)"
            echo "  --duration     Profiling duration in seconds (default: 120)"
            echo "  -s, --device-serial  ADB device serial number"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ADB command with optional serial
ADB_CMD="adb"
if [ -n "${ADB_SERIAL:-}" ]; then
    ADB_CMD="adb -s $ADB_SERIAL"
fi

# Verify ADB connection
echo "============================================="
echo "  LM-Meter Data Collection"
echo "============================================="
echo ""
echo "Checking ADB connection..."
DEVICE_MODEL=$($ADB_CMD shell getprop ro.product.model 2>/dev/null || echo "unknown")
ANDROID_VER=$($ADB_CMD shell getprop ro.build.version.release 2>/dev/null || echo "unknown")
echo "  Device: $DEVICE_MODEL (Android $ANDROID_VER)"

# Create timestamped output directory
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
SESSION_DIR="${OUTPUT_DIR}/session_${TIMESTAMP}"
TRACES_DIR="${SESSION_DIR}/traces"
mkdir -p "$TRACES_DIR"

echo "  Output: $SESSION_DIR"
echo "  Duration: ${DURATION}s"
echo ""

# Step 1: Remove old traces on device
echo "[1/5] Removing old trace files on device..."
$ADB_CMD shell "rm -f ${DEVICE_TRACE_DIR}/trace_*.json" 2>/dev/null || true

# Step 2: Clear logcat
echo "[2/5] Clearing logcat buffers..."
$ADB_CMD logcat -c

# Step 3: Stream logcat to file
LOG_FILE="${SESSION_DIR}/tvm_mlc.log"
echo "[3/5] Streaming logcat (tags: TVM_RUNTIME, MLC_Profile, MLC_EVENT)..."
echo "  -> $LOG_FILE"

$ADB_CMD logcat TVM_RUNTIME:V MLC_Profile:V MLC_EVENT:V '*:S' > "$LOG_FILE" &
LOGCAT_PID=$!

echo ""
echo "=========================================================="
echo "  Profiling is ACTIVE. Launch the LLM app on your device"
echo "  and start inference now."
echo ""
echo "  Waiting ${DURATION} seconds..."
echo "=========================================================="
echo ""

# Step 4: Wait for inference
sleep "$DURATION"

# Stop logcat
kill $LOGCAT_PID 2>/dev/null || true
wait $LOGCAT_PID 2>/dev/null || true
echo "[4/5] Logcat streaming stopped."

# Step 5: Pull trace files
echo "[5/5] Pulling trace files from device..."
TRACE_FILES=$($ADB_CMD shell "ls ${DEVICE_TRACE_DIR}/trace_*.json 2>/dev/null" || echo "")

if [ -z "$TRACE_FILES" ]; then
    echo "  WARNING: No trace files found on device at ${DEVICE_TRACE_DIR}"
    echo "  Make sure the MLC LLM app with LM-Meter instrumentation was running."
else
    for TRACE_FILE in $TRACE_FILES; do
        TRACE_FILE=$(echo "$TRACE_FILE" | tr -d '\r')
        BASENAME=$(basename "$TRACE_FILE")
        $ADB_CMD pull "$TRACE_FILE" "${TRACES_DIR}/${BASENAME}" 2>/dev/null || true
        echo "  Pulled: $BASENAME"
    done
fi

# Save session metadata
cat > "${SESSION_DIR}/metadata.json" << EOF
{
    "timestamp": "${TIMESTAMP}",
    "device_model": "${DEVICE_MODEL}",
    "android_version": "${ANDROID_VER}",
    "duration_seconds": ${DURATION},
    "device_trace_dir": "${DEVICE_TRACE_DIR}"
}
EOF

echo ""
echo "============================================="
echo "  Data Collection Complete!"
echo "============================================="
echo ""
echo "Output directory: $SESSION_DIR"
echo "  - tvm_mlc.log        (runtime logs)"
echo "  - traces/             (trace JSON files)"
echo "  - metadata.json       (session info)"
echo ""
echo "Next steps:"
echo "  Analyze the collected data with:"
echo "    python -m lm_meter.analyze --traces ${TRACES_DIR}"
echo ""
