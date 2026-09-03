# Camera (GStreamer) plugin

Reference hardware plugin. Sources live under `workers/camera/` and are copied
into `plugins/camera_gstreamer/` next to the daemon at build time.

## Prerequisites

- GStreamer 1.24+ MSVC x86_64 (`GSTREAMER_1_0_ROOT_MSVC_X86_64`)
- Configure with `CAPTURE_ENABLE_CAMERA_WORKER=ON` (see `CMakeUserPresets.example.json`)

## License

Plugin code: GPL-3.0-only (same as the CaptureSuite application).
GStreamer itself is LGPL/other — redistribute according to GStreamer terms.
