# Stub worker

Minimal out-of-process worker used to exercise [WORKER_HOST.md](../../docs/design/WORKER_HOST.md) before the GStreamer camera worker lands.

Speaks `Hello` → `HelloAck` → `Identify` / `IdentifyReply` with `capabilities.isolation = per_source`. No capture, preview, or disk writes.

```text
capture_worker_stub.exe --pipe <name> --worker-id <id> --plugin <plugin_id>
```

Build with the normal CMake tree (`CAPTURE_ENABLE_CAMERA_WORKER` is not required). The camera worker under `workers/camera/` remains the Milestone 5 GStreamer target and still needs the official GStreamer MSVC install.
