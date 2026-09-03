# Decisions Log

## Product
- Build a generalized multimodal capture platform, not a device-specific recorder.
- Capture V1 includes Delsys, conventional cameras, Xsens, and BGT60TR13C radar.
- Multi-radar is in current scope.
- Vicon is later/special integration.
- Post-capture video landmarking is in first app release.
- Full analysis suite is later.

## Language
- Python/PySide6 desktop shell.
- C++20 capture daemon.
- Isolated workers.
- Native vendor SDK workers where appropriate.
- Python retained for scientific/ML/post-processing ecosystem.

## Timing
- Highest achievable precision.
- Same physical session time, independent native rates.
- 64-bit nanosecond session timestamps.
- Preserve native timestamps.
- Model clock offset/drift.
- No permanent forced common sample rate.
- Sync anchors are separate from experiment checkpoints.

## Checkpoints
- Global across active streams.
- Close/name preceding section.
- Timestamp immediately.
- Names/tags/notes easy to edit.
- Timeline movement protected/audited.
- Preserve original and effective timestamp.

## Capture
- Any single source/subset/all.
- Preflight + rehearsal.
- One source failure does not normally kill others.
- Preview decoupled from raw writes.
- Incremental crash-safe storage.

## Naming
- Custom names for every relevant source/sensor.
- Preserve immutable hardware identity.
- Logical slots allow device replacement.
- Naming schemes are presets.

## Radar
- Multi-radar array object.
- Aliases, positions, orientations, profiles, overrides, calibration, timing modes.
- Hardware modes must be validated, not assumed.

## Mapping
- 3D anatomical avatar.
- EMG -> muscles/custom regions.
- Xsens -> body segments.
- Camera/radar -> spatial/lab coordinate system.
- Future relationships remain editable.

## Distribution
- Installable executable.
- Users do not manually install Python.
- Persistent settings/hotkeys/presets.
- Signed update mechanism.
- Stable/beta channels.
- Rollback.
- Offline install/update path.

## Analysis later
- Graphs + extracted features + ML-ready outputs.
- External graphing/export.
- Prefer non-proprietary Python ecosystem.
- MATLAB optional only.
