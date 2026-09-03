# Camera worker

Milestone 5 out-of-process GStreamer camera worker (`capture_worker_camera`).

## Build

Requires the official GStreamer MSVC tree (1.24+), discovered via
`GSTREAMER_1_0_ROOT_MSVC_X86_64` or a local extract under
`third_party/gstreamer/gstreamer/1.0/msvc_x86_64` (see
`tools/gstreamer-installers/`).

```powershell
$env:GSTREAMER_1_0_ROOT_MSVC_X86_64 = "…\msvc_x86_64"
cmake -S . -B build/windows-debug -DCAPTURE_ENABLE_CAMERA_WORKER=ON
cmake --build build/windows-debug --target capture_worker_camera
```

## Current slice

- `Hello` / `Identify` / `Discover` / `Connect` / `Start` / `Stop` /
  `GetPreviewDescriptor`
- Device identity from Media Foundation symbolic links (`camera.<hash>`)
- Record path: `mfvideosrc` → `tee` → non-leaky queue → encode → `h264parse` →
  `splitmuxsink` (Matroska) with paired `*.timing.mcap`
- Preview path: leaky queue → `jpegenc` → `appsink`, pushed as `PreviewFrame`
- `SegmentSealed` events on fragment rotate/stop
- `CAPTURE_CAMERA_FAKE=1` uses `videotestsrc` for CI without a webcam

Daemon still serves in-process MF cameras until it is switched to spawn this
worker. Process model: [WORKER_HOST.md](../../docs/design/WORKER_HOST.md).

## Milestone 4 note

Until the daemon spawns this worker for live sessions, `capture_daemon` still
uses the in-process Media Foundation grabber for preview and timing-only record.
