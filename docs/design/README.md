# Design Specifications

Implementation-level decisions for CaptureSuite Capture V1. The product specification lives in [`docs/spec/`](../../docs/spec/); these documents pin the choices that specification deliberately left open.

Read in this order:

| Document | Covers |
|---|---|
| [BUILD_TOOLCHAIN.md](BUILD_TOOLCHAIN.md) | compiler, CMake, vcpkg dependencies, protoc wiring, Python packaging, CI |
| [PROTOCOL.md](PROTOCOL.md) | named-pipe transport, frame format, handshake and versioning, timeouts, ACLs, job objects, backpressure numbers |
| [TIMING.md](TIMING.md) | QPC clock model, T0 establishment, drift estimation, `TimingHeader`, uncertainty budget, gap taxonomy |
| [STATE_MACHINES.md](STATE_MACHINES.md) | session and source transition tables, health rules, worker restart policy |
| [SESSION_FORMAT.md](SESSION_FORMAT.md) | `.mmsession` layout, MCAP batching and schema registration, rotation, integrity, journal, migrations |
| [RECOVERY.md](RECOVERY.md) | recovery procedure, idempotency, disk watchdog, rehearsal, fault injection |
| [OPERATIONS.md](OPERATIONS.md) | structured logging, diagnostic bundle, settings scopes, daemon-enforced safety |
| [UI_CONTRACT.md](UI_CONTRACT.md) | preview payload kinds, health fields, interaction guarantees |
| [WORKER_HOST.md](WORKER_HOST.md) | worker process granularity, spawn and job-object ordering, supervision, who writes raw bytes, segment sealing |
| [VIDEO_PIPELINE.md](VIDEO_PIPELINE.md) | GStreamer capture graph, codec and encoder selection, segmentation, timing sidecar, dropped-frame accounting |
| [PREVIEW_TRANSPORT.md](PREVIEW_TRANSPORT.md) | pipe-carried preview today, shared-memory ring layout and protocol, measured cutover criteria |
| [CONFIGURATION_UI.md](CONFIGURATION_UI.md) | JSON Schema subset for source configuration, validation layers, apply semantics, Setup tab rendering |
| [SETTINGS_REGISTRY.md](SETTINGS_REGISTRY.md) | `settings.json` keys, `registry.sqlite` schema, preset library, ownership rules |
| [VENDOR_SPIKE.md](VENDOR_SPIKE.md) | what must be measured on real hardware before each vendor adapter is designed |
| [RADAR_PIPELINE.md](RADAR_PIPELINE.md) | radar family scope, FMCW/Doppler record fidelity, timing, gaps, preview |
| [RADAR_ARRAY.md](RADAR_ARRAY.md) | RadarArray membership, software-coordinated timing only, `arrays.json` snapshot |
| [ANALYSIS.md](ANALYSIS.md) | Offline analysis jobs under `processing/`, streaming loaders, gap policy, QC, phases D–F |
| [DATA_COLLECTION_PROTOCOL.md](DATA_COLLECTION_PROTOCOL.md) | ML-ready multimodal capture: activities, sync anchors, quality gates |
| [KINEMATICS_PIPELINE.md](KINEMATICS_PIPELINE.md) | Teacher kinematic labels for radar ML (Phase D2) |
| [PLUGIN_REGISTRY.md](PLUGIN_REGISTRY.md) | On-disk `plugin.json` discovery, ListPlugins RPC, author contract |

**Full-stack research (2026-09):** [research/README.md](research/README.md) — IA, modality depth, plugin architecture, analysis workbench, implementation roadmap.

**Plugin author docs:** [docs/plugins/](../plugins/). **Operator quick start:** [docs/operator/](../operator/).

**Autonomous execution:** [research/AUTONOMOUS_EXECUTION_PLAN.md](research/AUTONOMOUS_EXECUTION_PLAN.md) — agent playbook (debug, test, phases, blockers). Session state: [research/PROGRESS.md](research/PROGRESS.md).

## Ground rules

These hold everywhere and override convenience:

1. Raw capture never depends on the UI process or the UI event loop.
2. Preview may drop data freely. The raw path reports overload instead of dropping silently.
3. Native rates and native timestamps are preserved. No resampling during acquisition.
4. Gaps are always explicit. Nothing is interpolated to hide a hole.
5. Hardware identity is immutable; aliases never replace it.
6. Every on-disk and IPC schema is versioned, and migrations are tested against frozen fixtures.
7. Vendor-specific behavior lives in plugins, never in core session or storage code.
8. One source failing must not disturb healthy sources.

## Status

Milestones 1 through 4 are implemented. Milestone 4 ships the PySide6 UI against the daemon with pipe-carried preview and in-process Media Foundation cameras (timing-only record).

Milestone 5 (camera) is implemented: `capture_worker_camera` (GStreamer tee → MKV + timing sidecar + JPEG preview), `WorkerHost` / `CameraWorkerBridge`, daemon `SegmentSealed` → integrity, multi-camera record with sealed segments, and `ApplyConfig` proxied into the worker (`encoder_preference`, preview rate / quality). Out-of-process cameras auto-enable when the worker binary and GStreamer are present (`CAPTURE_USE_CAMERA_WORKER=0` forces the MF timing-only path). Encoder selection probes usability (broken NVENC factories fall through). A 120 s two-camera soak (MX Brio + FHD) held ~30 Hz with zero drops, ~125 MiB MKV each, and clean finalize (`tools/soak_multi_cam.py`). Remaining optional: shared-memory preview cutover in [PREVIEW_TRANSPORT.md](PREVIEW_TRANSPORT.md) if pipe JPEG becomes the bottleneck. [CONFIGURATION_UI.md](CONFIGURATION_UI.md) and [SETTINGS_REGISTRY.md](SETTINGS_REGISTRY.md) cover the Setup tab; camera schema revision is `camera.gstreamer/4` when workers are active (`exposure_auto` / `exposure_time` / `gain` via MF UVC controls).

`camera.gstreamer/2` adds `capture_mode`, a per-device enum built by reading the camera's native Media Foundation media types (`workers/camera/src/capture_mode.cpp`), so resolution and frame rate are never hard-coded per model. Entries are deduplicated to one per resolution/rate, preferring raw over MJPEG and NV12 over other raw formats so the record branch's `videoconvert` stays a passthrough. Selecting a mode pins the source capsfilter and sets the stream's nominal rate.

`camera.gstreamer/3` adds `preview_quality`: `thumbnail` (default 320×240 JPEG) or `capture` (JPEG scaled to the armed capture mode resolution, still rate-capped and droppable). Record quality is unchanged either way.

Measured on an MX Brio with `tools/probe_capture_modes.py`, 10 s per mode, frame counts read from the timing sidecar:

| Mode | Negotiated | Delivered |
|---|---|---|
| 3840x2160@30 (YUY2) | as requested | ~31 Hz |
| 2560x1440@30 (NV12) | as requested | ~31 Hz |
| 1920x1080@30 (NV12) | as requested | ~31 Hz |
| 1920x1080@60 (NV12) | as requested | ~31 Hz |
| 1280x720@60 (NV12) | as requested | ~31 Hz |

Every mode negotiates its exact caps and finalizes in about 3 s. The 30 Hz modes hit their full rate at every resolution including 4K. The 60 Hz modes negotiate 60/1 but the device still delivers ~30, which is a device-side limit rather than a pipeline one: the shortfall is present with a bare `mfvideosrc ! fakesink` graph. The usual cause is auto-exposure refusing a sub-16 ms integration time in dim light. Nothing hides the shortfall — the timing sidecar records the frames that actually arrived.

Exposure and the other UVC controls are not settable from the app yet. `mfvideosrc` exposes no such properties, and Windows' frame server hides this device's MJPEG media types (`image/jpeg` fails to negotiate), so the only route is `IAMCameraControl` / `IAMVideoProcAmp` on the MF device source. That is standard UVC and needs no vendor SDK.

Milestones 6–8 (Infineon radar, Xsens, Delsys) proceed via adapter spikes in [adapters/](adapters/) before any vendor SDK is wired into the daemon. Sim sources (`sim.radar.*`, `sim.imu.upper`, `sim.emg.main`) remain the stand-ins until hardware measurements fill those stubs. Sim IMU/EMG record now writes real `imu.frame/1` / `emg.batch/1` protobuf into MCAP (multi-sensor frames and multi-channel batches); vendor workers stay blocked on spikes.

Milestone 6 is scoped to the radar **family** rather than a single part number, with one data schema per radar class; [RADAR_PIPELINE.md](RADAR_PIPELINE.md) pins that scope decision, what is recorded and at what fidelity, timing honesty, and gap semantics. Two boards are on the bench: BGT60TR13C (FMCW, range-capable — [adapters/infineon_bgt60tr13c.md](adapters/infineon_bgt60tr13c.md)) and BGT60LTR11AIP (Doppler-only, a deliberate scope addition — [adapters/infineon_bgt60ltr11aip.md](adapters/infineon_bgt60ltr11aip.md)). Both enumerate simultaneously and are distinguishable only by SDK UUID and sensor type, never by USB IDs or COM number.

Recording decision: the raw interleaved `uint16` ADC frame from the C SDK, which is both rawer and half the size of the `float32` cube the Python wheel exposes — so the worker is C++ against `radar_sdk.lib`. Timestamps are host-arrival with tens-of-milliseconds uncertainty (no device clock; sliced USB transfer), which revised the radar row of the [TIMING.md](TIMING.md) budget.

`capture_worker_radar` (`radar.ifx/3`) is gated by `CAPTURE_ENABLE_RADAR_WORKER` and auto-enabled when the exe is present (`CAPTURE_USE_RADAR_WORKER=0` forces off). It discovers both bench boards by SDK UUID: BGT60TR13C → `radar.frame/1` (`uint16_le_raw_interleaved`, default 3×32×128 → 24576 B/frame; chirp geometry is ApplyConfig-driven) and BGT60LTR11AIP → `radar.doppler/1` (`complex_float32_le`). Config exposes restart-required FMCW chirp parameters (bandwidth, samples, chirps, antennas, gain/cutoffs) plus `preview_view` for Fusion-style derived previews — droppable, never recorded. Smoke: `tools/probe_radar_worker.py`, `tools/probe_radar_record.py`, `tools/probe_ltr11_record.py`. Concurrent TR13C+LTR11 throughput soak is under the TR13C adapter §8 — not a hardware-sync claim. Session start writes `arrays.json` with software-coordinated membership ([RADAR_ARRAY.md](RADAR_ARRAY.md)); spatial editor / named array presets remain UI follow-up. The interim `CAPTURE_IFX_PREVIEW` file bridge remains for `sim.radar.1` only.

Deliberately not specified yet, because guessing would be worse than waiting:

| Area | Blocked on |
|---|---|
| Vendor adapters (Delsys, Xsens, radar) — discovery, pairing, timestamp semantics, uncertainty | real-hardware measurements per [VENDOR_SPIKE.md](VENDOR_SPIKE.md); each becomes `docs/design/adapters/<vendor>.md` |
| Multi-radar synchronization | validation on real boards; no sync claim until then |
| Review and export implementation (Milestone 11) | continuous export + Review tab exist; checkpoint-organized / Parquet / HDF5 modes still open |
| Pose and landmark processing (Milestone 12) | [ANALYSIS.md](ANALYSIS.md) pose registry — UrologyMoCap catalog (RTMO/RTMW/ViTPose/YOLO/MediaPipe/…); MediaPipe is one backend, not the only option; hand/face specialists expand after spike |
