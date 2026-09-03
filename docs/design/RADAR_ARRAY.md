# RadarArray

Session-level grouping of radar sources: membership, aliases, lab poses, and
the only timing mode that is honest today. Package file: `arrays.json`
([SESSION_FORMAT.md](SESSION_FORMAT.md)). Schema: `capture.v1.RadarArray` /
`DeviceArray` in `schemas/proto/capture/v1/arrays.proto`.

## Decisions

**Array membership is metadata, not a capture schedule.** Selecting sources and
starting the session still go through the normal source FSMs. The array does
not spawn workers or force a shared process. Each radar remains an independent
source with its own `source_id` (SDK UUID) and stream.

**`TIMING_MODE_SOFTWARE_COORDINATED` is the only legal value until hardware
validation says otherwise.** Proto reserves `HARDWARE_TRIGGERED` /
`HARDWARE_SYNC`; do not advertise them in UI or presets. Concurrent USB
acquisition is not sync — see [RADAR_PIPELINE.md](RADAR_PIPELINE.md) non-goals
and the dual-board soak in [adapters/infineon_bgt60tr13c.md](adapters/infineon_bgt60tr13c.md) §8.

**Poses are optional at record time.** Identity pose in `lab` frame is a valid
snapshot. A later spatial-layout preset can rewrite membership poses; the
session keeps the snapshot that was active when recording began.

**Heterogeneous arrays are allowed.** FMCW (`radar.frame/1`) and Doppler
(`radar.doppler/1`) boards may share one `RadarArray`. Preview kind stays
per-source (matrix vs trace); the array does not unify payloads.

## What the daemon writes today

On `begin_recording`, if any selected stream has modality `radar` or
`radar_doppler`, the package gets `arrays.json` with one array
`session_radar`, members = those sources, `timingMode: SOFTWARE_COORDINATED`,
identity poses. No members → `"arrays": []`.

No control RPCs yet for editing arrays mid-prepare. Preset type `radar_array`
in [SETTINGS_REGISTRY.md](SETTINGS_REGISTRY.md) remains the future home for
named layouts; wiring presets → prepare snapshot is Milestone 6 UI follow-up.

## UI (deferred / thin)

| Surface | Status |
|---|---|
| Source rail lists each radar independently | done (worker discovery) |
| Session `arrays.json` snapshot | done (auto membership) |
| Top-down / 3D spatial editor | not started — product sketch in handoff `CURSOR_CONTEXT.md` |
| Per-array preview picker | not started |
| Named `radar_array` presets | settings registry only |

## Non-goals

- Claiming hardware sync or fixed inter-radar phase
- Merging radar frames into one MCAP channel
- Vendor-specific array logic in core storage
