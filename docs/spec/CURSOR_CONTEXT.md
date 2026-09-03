# Cursor Context — Paste This Into a Fresh Chat

We are building a Windows-first installable research application for synchronized multimodal data capture.

The application must be designed from the beginning for future extensibility. The capture core must not be hard-coded around EMG or video. It should understand generic concepts such as sources, streams, timestamps, sessions, checkpoints, metadata, health, configuration, storage, and plugins.

## Capture V1 hardware

Implement real acquisition support for:

1. Delsys Trigno EMG
2. Conventional video cameras
3. Xsens IMUs
4. Infineon BGT60TR13C radar, including multi-radar configurations

Vicon Nexus infrared mocap is available in the lab but should be treated as a later/special integration rather than a Capture V1 requirement. Future wearables and other sensors should fit through the same plugin system.

Delsys and Xsens require pairing/setup workflows. Cameras and radar are treated as directly connected computer sources.

Users must be able to run:
- one source alone
- any subset
- all available/configured sources simultaneously

## Current project usage

The immediate research project primarily uses Delsys EMG + conventional video. Video is recorded raw and post-processed later in the same application using selectable pose/landmark models.

However, the capture engine itself must already be built to support Delsys, camera, Xsens, and radar properly.

## Timing philosophy

Highest achievable synchronization precision is the goal.

Do not force all streams to the same sample rate.

Examples:
- EMG may be ~2000 Hz
- IMU may be ~100–200 Hz
- video may be 30/60/120 FPS
- radar may have its own frame rate

They all describe the same physical time. Preserve every stream at its native rate.

Store:
- device-native timestamp if available
- sequence/sample/frame index
- host-arrival timestamp where useful
- mapped session timestamp
- timing uncertainty/quality where feasible

Use signed 64-bit integer nanoseconds for canonical session time representation.

Never permanently upsample a lower-rate stream merely to match a higher-rate stream. Interpolation/resampling belongs to later derived analysis and must preserve the original stream.

## Start behavior

One button should coordinate selected sources.

Preferred behavior:
1. validate selected sources
2. prepare storage
3. arm sources that support arming
4. wait for readiness
5. establish session T0 / clock mappings
6. issue coordinated start
7. record actual first datum from each source
8. preserve start offsets

The session clock belongs to the session, not any one device.

## Checkpoints

Recording should continue continuously.

A checkpoint is a global session event that applies to all active streams.

The checkpoint names the section that just ended.

Example:
- Start session
- after baseline, press checkpoint and name it `Baseline`
- the range from session start to that checkpoint becomes the Baseline section
- the next checkpoint closes/names the next section

Checkpoint timestamp capture must happen immediately when the button/hotkey is pressed. Naming can happen afterward.

Checkpoint names, tags, notes, and structured metadata should be easy to edit.

Moving a checkpoint on the timeline should be possible only through an advanced/protected workflow. Preserve:
- original timestamp
- effective/corrected timestamp
- modification reason
- revision history

Also support annotations/notes that do not create section boundaries.

Support synchronization anchors/events separately from experimental checkpoints.

## Source preview philosophy

Every source gets a compact "proof of life" card showing enough to confirm it is working.

Expandable views provide detailed diagnostics/configuration.

Camera:
- live preview is enough to prove life
- show actual FPS and dropped frames

Delsys:
- compact live EMG traces
- active/paired sensor count
- rate/dropped data
- expanded full channel diagnostics

Xsens:
- compact selected-sensor orientation cube
- acceleration/gyro activity
- connected sensor count
- expanded all-sensor diagnostics

Radar:
- compact live range profile or motion-energy view
- frame rate/dropped frames
- expanded range-Doppler/raw/channel/configuration diagnostics

Preview must be completely non-critical. Raw acquisition must continue even if the UI or graph is slow.

## Naming

Every source, sensor, radar, IMU, EMG sensor, and camera can have a custom user-facing name.

Never replace immutable hardware identity with the alias.

Preserve:
- vendor
- model
- serial/UUID/device identity
- firmware where available
- user alias
- logical role/slot
- anatomical or spatial placement

Naming schemes must be reusable as presets.

Examples:
- `Left_Biceps_EMG`
- `Left_Forearm_IMU`
- `Radar_Front_Left`
- `Camera_Sagittal`

Use logical slots so a replacement physical sensor can be rebound without changing the experimental role.

## Multi-radar

Multi-radar support is a Capture V1 requirement.

A radar array preset should support:
- multiple radar devices
- stable device identity
- custom aliases
- enable/disable per radar
- per-radar configuration
- shared/global profile where useful
- per-radar overrides
- physical position
- orientation
- coordinate frame
- calibration references
- timing/acquisition mode
- preview selection
- naming presets

UI should eventually include a top-down/3D spatial editor for radar placement and field of view.

Actual supported simultaneous/staggered/hardware-synchronized modes must be validated against the real Infineon hardware/RDK. Do not falsely label an unvalidated software-start mode as hardware synchronized.

## Anatomical mapping

Capture metadata should include sensor placement.

Use a 3D human avatar.

Delsys EMG:
- allow selecting essentially any muscle
- superficial/deep layers
- custom regions
- one or more sensors per muscle if needed
- optional placement/orientation notes

Xsens:
- map to body segments such as forearm, upper arm, torso, pelvis, thigh, shank, etc.

The future analysis system will use default muscle-to-landmark/joint relationships, but relationships must remain editable.

Nonstandard custom anatomical regions must be supported and can be manually mapped to relevant landmarks/joints later.

Cameras and radars use spatial/lab mapping rather than muscle mapping.

## Storage principles

Capture must preserve the rawest accessible form of every stream.

Examples:
- Delsys: rawest samples the official API exposes
- camera: original captured video + timing
- Xsens: raw inertial/orientation data exposed by SDK
- radar: rawest accessible radar frames + acquisition configuration

Do not bake pose overlays into source video.

Derived data belongs later.

Use continuous incremental writes. Never wait until Stop to save.

A UI crash, source-worker crash, or power loss should not destroy an entire session.

Support segmented files, journaling, recovery, and integrity manifests.

Canonical sessions should be directly reopenable by the app. Export is for interoperable copies/alternate organization, not required to use the data later.

## Export

Default export: complete continuous streams.

Optional structured export:
- organize sections based on checkpoint boundaries/names
- section manifests can reference time ranges without duplicating huge raw files

Optional materialized section export:
- physically cut video/data files into checkpoint-defined sections

Future analysis can run on:
- full session using checkpoint metadata
- selected sections
- materialized section files

## Post-capture video processing

Part of the first app release.

Recorded raw video -> selectable pose/landmark model -> model-native output -> canonical normalized skeleton.

Preserve:
- source video ID
- frame index
- source timestamp
- session timestamp
- model name/version
- confidence
- native landmarks
- normalized landmarks
- processing settings

Do not yet implement the full analysis suite.

## Future analysis direction

Later analysis must support:
- full-stream analysis with checkpoint awareness
- checkpoint-section analysis
- customizable graphs
- EMG processing
- mocap/kinematic metrics
- joint angles, speed, mobility, acceleration
- multimodal EMG-to-motion relationships
- extracted features for ML
- exportable graph data
- ML-ready feature matrices
- MATLAB compatibility if needed
- canonical non-proprietary Python/SciPy/NumPy implementations preferred over MATLAB dependencies

This future requirement affects the session format now, but the actual analysis suite is deferred.

## Recommended technical architecture

Desktop UI:
- Python
- PySide6/Qt

Capture:
- C++20 capture daemon
- isolated source workers
- C++ workers where vendor SDK/native throughput benefits
- Python worker acceptable where official vendor integration is Python-first

Suggested:
- camera: C++ + GStreamer
- Delsys: Python worker using official API initially
- Xsens: C++ worker using exact applicable SDK
- radar: C++ worker using Infineon RDK
- post-capture pose processing: Python

Control/status:
- versioned IPC, preferably Protocol Buffers
- local transport
- shared memory for preview payloads

Raw data must not travel through the GUI process.

## Executable and updates

The end product is a normal installable application.

Users should not need to install Python manually.

Need:
- Windows installer
- persistent settings
- persistent source names/presets/hotkeys/workspaces
- code signing
- stable/beta update channels
- signed update packages/manifests
- rollback
- schema migration
- no updates during active capture
- offline installer/update path for lab computers

## QoL / reliability requirements

Include:
- preflight validation
- rehearsal mode
- storage-speed check
- free-space estimate
- expected recording duration estimate
- source health cards
- restore last working setup
- capture presets
- naming presets
- anatomy presets
- radar array presets
- checkpoint protocol presets
- hotkey presets
- workspace/layout presets
- export presets
- keyboard shortcuts
- foot pedal/USB HID support later
- countdown start
- audible/visual recording/checkpoint/warning feedback
- quick timestamped notes
- protected Stop action
- dangerous settings locked during recording
- source-specific reconnect policies
- one source failure should normally not stop healthy sources
- post-capture session verification
- diagnostic bundle excluding raw participant data by default
- replay recorded sessions as simulated live sources
- synthetic failure injection for testing
- multi-monitor layouts
- restore previous setup
- logs
- audit trail
- crash recovery

## Build order

1. Hardware/SDK inventory and qualification
2. Versioned session schema and source-worker protocol
3. Capture daemon + simulated workers
4. Storage/journaling/recovery
5. PySide6 UI foundation
6. Camera backend
7. Infineon radar + multi-radar arrays
8. Xsens backend
9. Delsys backend
10. Unified all-source capture testing
11. Naming/anatomy/spatial mappings and presets
12. Export and post-capture review
13. Video landmark processing
14. Installer/updater/signing
15. Capture V1 hardening and release

Do not jump immediately into polishing the UI before the session schema, timing model, worker protocol, storage behavior, and simulation framework are stable.
