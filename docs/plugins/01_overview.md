# Plugin overview

## Philosophy

- Raw capture never goes through the GUI.
- Workers advertise streams with versioned `data_schema_id` values.
- Vendor SDKs stay inside the plugin process.
- Core session/storage code must not grow vendor branches.

## Layout

```text
plugins/
  camera_gstreamer/plugin.json      # reference hardware (GPL)
  radar_infineon/plugin.json        # reference hardware (GPL)
  example_sine_py/                  # Python SDK tutorial (Apache)
  lsl_bridge/                       # LSL bridge (Apache)
```

Discovery paths: `{daemon_dir}/plugins/*/plugin.json`,
`%LOCALAPPDATA%\CaptureSuite\plugins`, `CAPTURE_PLUGIN_PATH`.

## Two ways to write a plugin

1. **Python SDK** (`capture_worker`) — fastest for serial, UDP, LSL, vendor Python wheels.
2. **C++ stub** (`workers/stub`) — for SDKs that are C/C++-only or need tight loops.

Both speak the same Apache-2.0 wire protocol in `schemas/` /
`capture_protocol`.
