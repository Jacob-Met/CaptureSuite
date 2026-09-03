# Master Specification — Capture Side

## Mission

Build a reliable, extensible, installable multimodal research capture application that can synchronize heterogeneous sensor systems on a common session timeline while preserving the rawest accessible data from each device.

The app must be designed so that additional acquisition modalities can be added in the future as plugins without rewriting the core session, synchronization, checkpoint, storage, export, or UI systems.

## Capture V1

### Fully implemented source families

- Delsys Trigno EMG
- Conventional video cameras
- Xsens IMUs
- Infineon BGT60TR13C radar, including configurable multi-radar setups

### Additional V1 processing

- Post-capture video pose/landmark processing

### Deferred

- Full integrated analysis suite
- Advanced EMG/kinematic statistical analysis
- ML model training
- Vicon Nexus live integration
- Additional wearables/physiology devices

Vicon remains architecturally supported as a future/special source plugin or import/live bridge.

## Non-negotiable principles

1. Preserve rawest accessible source data.
2. Preserve native rates.
3. Never overwrite raw data with derived data.
4. Every stream is mapped to one session timeline.
5. Native device timing is preserved separately.
6. UI previews are non-critical.
7. Raw recording does not depend on the GUI event loop.
8. One source failure must not normally destroy others.
9. Recording is incremental and recoverable.
10. Every source is optional.
11. Any subset can be used.
12. Device aliases never replace immutable hardware identity.
13. Capture configuration is reproducible through versioned presets.
14. Checkpoints are global metadata, not physical cuts in the source streams.
15. Export is non-destructive.
16. Future source plugins must not require core rewrites.
17. Sessions must remain usable for future analysis/ML without changing raw capture design.

## Functional areas

### Setup
- discover sources
- connect devices
- pair Delsys
- pair Xsens
- configure source settings
- custom names
- logical slots
- anatomical mapping
- spatial mapping
- calibration
- load/save presets
- preflight
- rehearsal

### Capture
- select sources
- start selected
- start all ready
- common session timeline
- compact source health previews
- expandable source details
- checkpoints
- annotations
- sync events
- alerts
- disconnect/reconnect
- continuous writes
- stop/finalize

### Review
- session summary
- timeline
- checkpoint list
- gaps/errors
- source status summary
- quick source-data verification
- final notes

### Export
- full session
- checkpoint-organized references
- materialized checkpoint sections
- CSV/Parquet/HDF5/JSON/video
- integrity report

### Post-processing
- video pose/landmark model selection
- processing queue
- model-native output
- canonical skeleton output
- timestamp preservation

## Source card philosophy

Every active source should provide a compact proof-of-life view that answers:

- Is it connected?
- Is data arriving now?
- Is it arriving at roughly the expected rate?
- Is anything obviously wrong?
- Is raw data successfully being written?

Expand for detailed configuration/diagnostics.

## Checkpoint semantics

Checkpoint is timestamped immediately.

A checkpoint closes and names the section preceding it.

Editable:
- name
- tags
- notes
- structured metadata

Protected:
- timestamp movement
- destructive deletion
- section merging

Always preserve original timestamp and revision history.

## Session timing

Canonical session time:
- signed 64-bit integer nanoseconds

Per data unit preserve where available:
- sequence/sample/frame index
- device timestamp
- host arrival timestamp
- session timestamp
- uncertainty/quality
- clock mapping version

Do not claim nanosecond physical accuracy merely because nanoseconds are used for representation.

## Future analysis compatibility

The session format must allow later access to:
- arbitrary time windows
- checkpoint sections
- multiple device-native streams
- anatomical mappings
- spatial mappings
- calibration
- quality flags
- model outputs
- provenance
- app/plugin/SDK versions

Later analysis must be able to produce:
- graphs
- derived streams
- features
- ML-ready data
- externally graphable tabular data
without modifying the raw capture representation.
