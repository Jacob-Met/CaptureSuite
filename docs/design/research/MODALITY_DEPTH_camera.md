# Modality depth scorecard: Camera / Video

Research date: **2026-09-01**  
Schema: `video.frame_timing/1` + H.264 MKV segments ([VIDEO_PIPELINE.md](../VIDEO_PIPELINE.md))

---

## Scorecard

| Dimension | Today (sim/replay) | Target (HW) | Gap / action |
|-----------|--------------------|-------------|--------------|
| Proof of life | **4** | 5 | Segment + drop counts on Focus card |
| Expanded card | **4** | 5 | Resolution/slot/encoder/serial; timing-only honesty |
| Setup schema | **4** | 5 | UVC exposure/gain apply path (`camera.gstreamer/4`) |
| Preflight | 3 | 5 | Disk space for MKV (shared preflight); encoder probe HW |
| Failure modes | **4** | 5 | Overload → health drops; alert bar |
| Spatial / anatomy | 3 | 3 | Logical slot labels (sagittal/oblique) |
| Record honesty | **5** | 5 | Raw MKV + timing sidecar; overlay never in sealed path |
| Export / review | **4** | 4 | Stream inventory: schema, rate, segments |

**Phase 4 sim gate:** met for camera family on sim/replay (+ optional UVC).

---

## Proof of life (health card)

**Minimum (UI_CONTRACT):** connected, nominal rate, last frame age, write_ok.

**Add:**
- `encoder_in_use` (x264/nvenc/qsv)
- `segments_sealed` / current segment index
- `dropped_frames_session` (cumulative)
- `preview_quality` mode (thumbnail vs capture-resolution JPEG)

---

## Expanded card (Focus view)

| Field | Source |
|-------|--------|
| Resolution × fps | stream.json / effective config |
| Instantaneous fps | timing sidecar rolling |
| Exposure / gain | UVC when available |
| Bitrate estimate | segment size / duration |
| Preview latency | host receive − device timestamp (approx) |

**Multi-cam grid:** cap preview rate globally (`preview_rate_limit_hz`); show per-cam drop badge if preview decimated.

---

## Setup schema gaps

- Validate `capture_mode` enum against device caps ([VIDEO_PIPELINE.md](../VIDEO_PIPELINE.md)).
- `preview_quality`: thumbnail vs capture — document bandwidth tradeoff in UI help.
- Future: ROI / crop for radar co-location (research only).

---

## Preflight checks

| Check | Severity |
|-------|----------|
| Worker binary + GStreamer present | fail |
| Encoder factory opens | warn → fall through |
| Free disk ≥ N × duration × cam count | fail/warn |
| Duplicate stable_device_key | warn |

---

## Failure modes

| Event | UX |
|-------|-----|
| Preview overload | Drop preview; show OVERLOAD on card |
| Record path stall | CRITICAL alert; write_ok false |
| Segment seal fail | Stop protected; session_doctor guidance |
| MF timing-only fallback | Banner: “No pixel record — timing only” |

---

## Operator education

Persistent help link: **“Sealed MKV is the analysis source; preview JPEG is not recorded.”** Aligns with AGENTS overlay rule for any future realtime overlay feature (overlays under `processing/` only).

---

## Preview transport

Pipe JPEG today; SHM ring when [PREVIEW_TRANSPORT.md](../PREVIEW_TRANSPORT.md) criteria met (CPU > X%, latency > Y ms for 2+ cams).

---

## Analysis hooks

Phase B: timing QC only. Phase D: segment-indexed decode → pose registry. See [ANALYSIS.md](../ANALYSIS.md).

---

## References

- [VIDEO_PIPELINE.md](../VIDEO_PIPELINE.md)
- [PREVIEW_TRANSPORT.md](../PREVIEW_TRANSPORT.md)
- [capture_worker_camera](../../workers/camera/)
