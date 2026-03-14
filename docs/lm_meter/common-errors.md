# LM-Meter Common Errors and Troubleshooting

## ADB Issues

### `adb: device not found`

**Problem**: No Android device detected.

**Solutions**:
1. Ensure USB debugging is enabled on the device:
   - Go to **Settings → Developer Options → USB Debugging → ON**
2. Check the USB cable is properly connected
3. Run `adb devices` to verify the connection
4. Try `adb kill-server && adb start-server`

### `adb: insufficient permissions`

**Problem**: ADB doesn't have permission to access the device.

**Solutions**:
1. On the Android device, accept the "Allow USB debugging" prompt
2. On Linux, add udev rules:
   ```bash
   sudo usermod -aG plugdev $USER
   echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="18d1", MODE="0666", GROUP="plugdev"' | sudo tee /etc/udev/rules.d/51-android.rules
   sudo udevadm control --reload-rules
   ```

## Build Errors

### `rustc: command not found`

**Problem**: Rust is not installed or not in PATH.

**Solution**: Run the setup script or install manually:
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"
rustup default 1.75.0
```

### `ANDROID_NDK is not set`

**Problem**: Android NDK environment variable is missing.

**Solution**: Add to `~/.bashrc`:
```bash
export ANDROID_NDK="$HOME/Android/Sdk/ndk/27.0.11718014"
export TVM_NDK_CC="$ANDROID_NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang"
```
Then run `source ~/.bashrc`.

### Java version mismatch

**Problem**: Build requires Java 17 but a different version is active.

**Solution**:
```bash
sudo update-alternatives --config java
# Select Java 17
export JAVA_HOME="/usr/lib/jvm/java-17-openjdk-amd64"
```

## Profiling Issues

### No trace files collected

**Problem**: `collect_data.sh` finds no `trace_*.json` files on the device.

**Possible causes**:
1. The MLC LLM app was not running during profiling
2. The app was built without LM-Meter instrumentation
3. The device trace directory is incorrect

**Solutions**:
1. Verify the app is installed: `adb shell pm list packages | grep mlc`
2. Rebuild with instrumentation enabled (see `build_lm_meter.sh`)
3. Check the trace directory: `adb shell ls /data/local/tmp/traces/`

### Empty or corrupt trace files

**Problem**: Trace JSON files exist but are empty or malformed.

**Solutions**:
1. Ensure inference completed fully before pulling traces
2. Increase the `--duration` parameter in `collect_data.sh`
3. Check available storage on the device: `adb shell df /data`

### Very high ε★ values

**Problem**: Large normalized errors in profiling results.

**Possible causes**:
1. Thermal throttling on the device
2. Background processes interfering
3. GPU frequency scaling

**Solutions**:
1. Set CPU governor to `performance` mode
2. Close background apps on the device
3. Let the device cool down between profiling sessions
4. Run multiple iterations and average results

## Python Module Issues

### `ModuleNotFoundError: No module named 'lm_meter'`

**Problem**: LM-Meter Python module is not installed.

**Solution**:
```bash
cd /path/to/nn-Meter-LLM
pip install -e ".[lm_meter]"
```

### `ImportError: No module named 'yaml'`

**Problem**: PyYAML is not installed.

**Solution**:
```bash
pip install PyYAML
```

## Getting Help

If you encounter other issues, please:
1. Check the [LM-Meter GitHub Issues](https://github.com/amai-gsu/LM-Meter/issues)
2. Open an issue in this repository with:
   - Your OS and Python version
   - The exact error message
   - Steps to reproduce the problem
