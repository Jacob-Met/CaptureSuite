# Implementation Plan

## Milestone 0 — Hardware/SDK Qualification

Inventory:
- exact Delsys receiver/base and sensors
- Delsys API version and licensing behavior
- exact Xsens product family and receiver
- exact Infineon radar board/revision and number of boards
- camera models and expected maximum count
- target PC and storage hardware
- available sync/trigger hardware

Write minimal standalone prototypes for each vendor source.

Exit:
Each source can independently produce identifiable timestamped data.

## Milestone 1 — Schemas and Protocol

Implement:
- source manifest
- stream descriptor
- health schema
- event schema
- checkpoint schema
- clock-mapping schema
- worker handshake
- plugin compatibility/version handshake

Exit:
A simulated worker can advertise arbitrary source/stream types.

## Milestone 2 — Capture Daemon + Simulator

Implement:
- master monotonic clock
- session state machine
- worker lifecycle
- coordinated arm/start/stop
- source selection
- checkpoints
- annotations
- sync anchors
- simulator workers
- fault injection
- replay source

Exit:
Arbitrary simulated modalities record together.

## Milestone 3 — Storage/Journal/Recovery

Implement:
- session package
- MCAP/numeric writers
- video writer interface
- journal
- file rotation
- atomic metadata updates
- integrity manifests
- recovery
- incomplete-session finalization

Exit:
Killing UI or a worker does not destroy previously recorded data.

## Milestone 4 — PySide6 Capture UI

Implement:
- project/session creation
- source registry
- source cards
- selection
- setup/configuration dialogs
- start/stop
- checkpoint/annotation/sync controls
- health
- logs
- persistent settings
- hotkeys
- preflight
- rehearsal
- workspace layouts

Exit:
Simulator can be fully operated through packaged UI.

## Milestone 5 — Camera

Implement:
- enumeration
- naming
- configuration
- GStreamer capture
- live preview
- segmented recording
- per-frame timing
- multiple cameras
- dropped-frame health

Exit:
Validated camera count records reliably.

## Milestone 6 — Radar + Multi-Radar

Implement:
- Infineon RDK device discovery
- stable identity
- naming
- raw frames
- configuration
- compact preview
- expanded diagnostics
- multiple radar devices
- RadarArray object
- spatial layout editor
- geometry presets
- timing/acquisition mode abstraction
- calibration
- multi-radar interference/throughput validation

Exit:
Every radar can be independently named/configured/recorded and validated multi-radar modes work.

## Milestone 7 — Xsens

Implement:
- exact SDK backend
- discovery
- pairing
- naming/logical slots
- calibration
- anatomical segment mapping
- native streams
- orientation preview
- health
- disconnect/reconnect

Exit:
All intended Xsens devices record stably.

## Milestone 8 — Delsys

Implement:
- secure credential load
- receiver detection
- pairing
- scan/configuration
- naming/logical slots
- anatomical mapping
- native streams
- compact/full EMG views
- health
- trigger support
- reconnect/finalization

Exit:
Full intended Delsys setup records through official API.

## Milestone 9 — Unified Capture Hardening

Implement/test:
- arbitrary subsets
- Start Selected
- Start All Ready
- shared session time
- source failures
- reconnect
- sync health
- long-duration capture
- post-capture verification

Exit:
All four source families can operate simultaneously.

## Milestone 10 — Presets and Mapping

Implement:
- naming presets
- device presets
- logical slots
- 3D anatomy mapper
- custom anatomical regions
- spatial layout presets
- radar arrays
- checkpoint protocols
- workspace presets
- hotkey presets
- export presets

Exit:
Known lab configurations restore quickly with mismatch warnings.

## Milestone 11 — Review and Export

Implement:
- timeline
- session summary
- gap/error visualization
- continuous export
- checkpoint-organized export
- materialized section export
- CSV/Parquet/HDF5/JSON/video
- replay

Exit:
Researchers can reopen and export without vendor acquisition software.

## Milestone 12 — Video Landmark Processing

Implement:
- pose model registry
- processing jobs
- CPU/GPU choice
- native model output
- canonical skeleton
- timing preservation
- overlays
- model versions/provenance

Exit:
Recorded video can be post-processed reproducibly in-app.

## Milestone 13 — Installer/Updater

Implement:
- Windows installer
- packaged UI/runtime
- workers
- dependency checker
- vendor runtime handling
- signing
- stable/beta channels
- rollback
- migrations
- diagnostics
- offline install/update path

Exit:
Normal users can install and update without manually installing Python.

## Research track R1–R5 (radar-to-kinematics ML)

Parallel to Capture V1 product milestones. **Not** in the V1 installer scope. Master index: [`docs/PROJECT_OUTLINE.md`](../../docs/PROJECT_OUTLINE.md).

| Track | Phase | Delivers | Product dependency |
|-------|-------|----------|-------------------|
| **R1** | P0 Capture | Activity-driven multimodal sessions (radar + video + anchors) | M6 radar (partial OK), M5 camera |
| **R2** | P1 Labels | `landmarks.parquet` + `kinematics.parquet` | M12 / Analysis Phase D + D2 |
| **R3** | P2 Datasets | `ml_bundle` aligned radar windows → kinematic targets | Phase B features + D2 |
| **R4** | P3 Train | RadarKinematicsML trained model + model_card | R3 + Linux GPU env |
| **R5** | P4 Evaluate | Held-out eval reports (Phase F) | R4 |

Immediate operator priority: **R1** — follow [`DATA_COLLECTION_PROTOCOL.md`](../docs/design/DATA_COLLECTION_PROTOCOL.md) and activity catalog [`schemas/activity_catalog/1.json`](../schemas/activity_catalog/1.json).

## Milestone 14 — Capture V1 Release Qualification

- exhaustive hardware matrix
- long soak tests
- recovery tests
- updater tests
- documentation
- release notes
- known limitations
- provenance validation
