# Video Capture and Encoding Pipeline

The camera record path for Milestone 5. Container and rotation rules are fixed in [SESSION_FORMAT.md](SESSION_FORMAT.md); this document pins the capture stack, codec, timing sidecar, and drop accounting.

## Resolving the capture-stack conflict

Two documents disagreed. [`scope.json`](../../docs/spec/scope.json) and [`ARCHITECTURE.md`](../../docs/spec/ARCHITECTURE.md) specify the camera worker as C++ plus GStreamer. Milestone 4 shipped an in-process Media Foundation grabber instead, for preview and timing-only record.

**Decision: GStreamer owns the record path. Media Foundation remains only the Milestone 4 in-process implementation and is retired when the worker lands.**

The deciding constraint is the container. [SESSION_FORMAT.md](SESSION_FORMAT.md) requires Matroska because it tolerates truncation, and [RECOVERY.md](RECOVERY.md) recovers video by parsing clusters forward to the last complete one. Media Foundation's `SinkWriter` has no Matroska sink; getting there means writing a custom `IMFMediaSink`, which is a mux implementation we would own and test ourselves. GStreamer's `matroskamux` behind `splitmuxsink` does segmented, keyframe-aligned MKV as a supported configuration, and brings hardware encoder elements with it.

Milestone 4's Media Foundation code was never wasted: it validated device identity, preview shape, and per-frame timing against real hardware, and those are the parts that carry over.

### One API owns the device

A UVC device cannot be reliably opened twice. Preview and record therefore both derive from a single open, via a `tee`, never from two independent captures. This is a correctness constraint, not an optimization.

### Identity must survive the switch

Source IDs are derived from the Media Foundation symbolic link (`MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_SYMBOLIC_LINK`). GStreamer's `mfvideosrc` accepts and reports that same string as `device-path`, so the cutover keeps existing IDs stable. Any enumeration change that alters a source ID would orphan device-registry entries and presets, so the symbolic link stays the hardware key regardless of which stack reads it.

## Pipeline

```text
mfvideosrc device-path=<symbolic-link>
  ! capsfilter caps=<raw or image/jpeg>
  ! [jpegdec]                                   # ahead of tee when MJPEG-only
  ! tee name=t

  t. ! queue max-size-buffers=8 leaky=no          # record branch
     ! videoconvert
     ! <encoder>
     ! h264parse config-interval=-1
     ! splitmuxsink muxer=matroskamux

  t. ! queue max-size-buffers=1 leaky=downstream  # preview branch
     ! videorate ! videoscale ! jpegenc
     ! appsink
```

Decode belongs ahead of the tee when the camera only offers MJPEG: record and preview both consume raw from one open. On Stop the worker sends EOS so `splitmuxsink` finalizes the open fragment before NULL (otherwise the MKV can seal as 0 bytes while the timing sidecar is populated).

`ksvideosrc` is the fallback source for devices `mfvideosrc` refuses.

GStreamer is the single dependency not managed by vcpkg, and the reasoning plus the containment rules are in [BUILD_TOOLCHAIN.md](BUILD_TOOLCHAIN.md). Only the camera worker links it.

The two queues encode the guarantee difference from [PROTOCOL.md](PROTOCOL.md). The record queue is non-leaky at the 8-frame capacity from the backpressure table, so a full queue reports `OVERLOAD_DROP` rather than silently discarding. The preview queue is `leaky=downstream` at depth 1, so a stalled UI drops preview frames and can never stall the encoder. Preview loss is normal and unreported; record loss is a defect and always reported.

## Codec and encoding mode

Three modes, because the honest choice depends on what the camera offers.

| Mode | When | Cost |
|---|---|---|
| `passthrough` | camera emits H.264 natively | no transcode, no generation loss, lowest CPU |
| `encode_raw` | camera offers NV12 or YUY2 at the requested mode | one encode from raw, no generation loss |
| `encode_transcoded` | camera only offers MJPEG at the requested mode | decode plus encode, visible generation loss |

Preference order is `passthrough`, then `encode_raw`, then `encode_transcoded`. Most UVC webcams only reach high resolution and frame rate over MJPEG, so `encode_transcoded` will be common; `stream.json` records the actual mode, the source pixel format, and `transcoded: true` so the loss appears in provenance instead of being discovered later. `passthrough` remains selectable when an operator prefers zero transcode over file size.

Encoder selection is probed once at preflight and the chosen element is recorded in the session:

`nvh264enc`, then `qsvh264enc`, then `amfh264enc` or `mfh264enc`, then `x264enc` (`speed-preset=veryfast`).

| Parameter | Value | Reason |
|---|---|---|
| Profile | H.264 High | broad tool support, no licensing surprise for research use |
| Rate control | constant quality, not constant bitrate | scene complexity should change file size, not image quality |
| B-frames | 0 | keeps PTS monotonic, so frame index maps to presentation time without reorder bookkeeping |
| Keyframe interval | 1 s (`gop-size = fps`) | bounds both segment split alignment and post-crash decode loss to one second |

The CPU fallback will not sustain several 1080p60 streams. Preflight measures it and warns rather than silently degrading, because a researcher discovering dropped frames after a participant session cannot re-run the trial.

## Segmentation

`splitmuxsink` with `max-size-bytes=536870912` (512 MiB) and `max-size-time=300000000000` (300 s), matching the rotation thresholds in [SESSION_FORMAT.md](SESSION_FORMAT.md), plus `send-keyframe-requests=true` so every segment starts at a keyframe and is independently decodable.

The `format-location-full` signal is where the worker opens the paired files: `segments/%06d.mkv` and `segments/%06d.timing.mcap`. Video and sidecar rotate together and are sealed together, so their frame ranges always correspond — which is what makes the cross-check in [RECOVERY.md](RECOVERY.md) a lookup rather than a guess.

On each split the worker hashes both files and sends one `SegmentSealed` per file, per [WORKER_HOST.md](WORKER_HOST.md).

## Timing sidecar

One MCAP record per frame on a single channel with schema `video.frame_timing/1`. No compression, per [SESSION_FORMAT.md](SESSION_FORMAT.md).

Each record carries the canonical `TimingHeader` from [TIMING.md](TIMING.md) plus:

| Field | Meaning |
|---|---|
| `frame_index_in_segment` | zero-based within this segment |
| `pts_ns` | the presentation timestamp actually muxed into the MKV |
| `keyframe` | whether this frame starts a GOP |
| `encoded_bytes` | size of the encoded frame |

`TimingHeader` population for cameras:

- `device_index` — driver-reported frame index when available, otherwise a running counter
- `device_timestamp` — source buffer PTS as reported by the driver, unit `ns`, never rewritten
- `host_arrival_ns` — QPC read in the pad probe on the record branch
- `session_time_ns` — the device timestamp through the active clock mapping, like any other device
- `timestamp_uncertainty_ns` — half the frame period, the estimate from [TIMING.md](TIMING.md)

`pts_ns` exists so review can align sidecar to video exactly, without assuming the muxer preserved the source timeline.

## Dropped-frame accounting

Preferred detection is the driver-reported frame index: any delta above one raises a `SEQUENCE_LOSS` gap for the missing interval and sets `SEQUENCE_DISCONTINUITY` on the next frame.

When the driver reports no index, infer from PTS. With a nominal period `T`, a delta of at least `1.5 T` means `round(delta / T) - 1` frames were dropped. Inferred timestamps set `INTERPOLATED_TIMESTAMP`, so an inference is never presented as a measurement.

Encoder-side loss is separate: a full record queue is `OVERLOAD_DROP`, per [PROTOCOL.md](PROTOCOL.md). Both kinds are journaled. Frames discarded by the leaky preview queue are not.

## Multiple cameras

Each camera is an independent source with its own clock mapping and its own worker process (`per_source` isolation, per [WORKER_HOST.md](WORKER_HOST.md)), so one failing camera cannot disturb the others.

There is no hardware synchronization between UVC cameras. Alignment is through session time only, and with half-frame-period uncertainty on each, worst-case inter-camera skew is about one frame period. Nothing in the app claims genlock. Sync anchors — a clap or an LED visible to several cameras — remain the operator's independent cross-check, which is the reason they exist.

## Camera controls

Exposure, gain, and white balance are exposed as source configuration through the JSON Schema mechanism in [CONFIGURATION_UI.md](CONFIGURATION_UI.md), backed by the source element's camera-control properties. They are snapshotted into `source.json` and locked during `RECORDING` like any other configuration.

Preflight warns when auto-exposure is enabled, because UVC auto-exposure extends frame duration in low light, which shows up as a frame rate drop the operator did not ask for. It is a warning and not a refusal: sometimes auto is what the operator wants, and the app's job is to make the tradeoff visible rather than to overrule it.
