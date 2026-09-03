# Reliability and Testing Plan

## Non-negotiable reliability behavior

- Raw capture is independent from UI preview.
- UI crash must not automatically destroy recording.
- One worker failure should not corrupt healthy sources.
- All active streams write incrementally.
- Gaps must be explicit, never hidden.
- Source reconnection must create documented gap/re-sync events.
- A full disk must produce an immediate critical alert and safe degradation/finalization behavior.
- Power loss should permit best-effort session recovery.

## Simulation framework

Implement simulated:
- EMG
- video
- IMU
- radar
- event streams

Fault injection:
- clock drift
- jitter
- dropped frames
- dropped packets
- duplicate sequence numbers
- source disconnect
- reconnect
- slow disk
- full disk
- worker crash
- UI crash
- corrupted tail segment
- time discontinuity

## Unit tests

- state machines
- clock mapping
- checkpoint/section derivation
- preset migration
- alias/logical-slot binding
- schema compatibility
- journal recovery
- export range calculations

## Integration combinations

Test:
- camera only
- Delsys only
- Xsens only
- radar only
- every pair
- three-way combinations
- all four
- multiple cameras
- multiple radars

## Soak tests

- 1 hour
- 4 hours
- 8 hours
- overnight

Track:
- RAM growth
- worker CPU
- disk throughput
- queue depth
- dropped data
- drift
- reconnect behavior
- source temperature/battery where applicable

## Synchronization tests

Use observable sync anchors and measure:
- start offset
- drift
- repeated-anchor consistency
- reconnect mapping
- timing uncertainty

## Multi-radar testing

Explicitly validate:
- stable identity
- array preset rebinding
- simultaneous acquisition
- RF interference
- staggered modes
- USB bandwidth
- dropped frames
- per-radar failure
- array recovery
