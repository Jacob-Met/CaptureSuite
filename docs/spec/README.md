# Multimodal Capture Platform — Cursor Handoff

This package contains the complete agreed capture-side plan for a research application that records and synchronizes multiple human-sensing modalities.

## Current Capture V1 scope

Fully implement:

- Delsys Trigno EMG
- Conventional video cameras
- Xsens IMUs
- Infineon BGT60TR13C radar, including configurable multi-radar setups

Also include:

- Post-capture video landmark/pose processing in the same app
- Generalized plugin architecture for future capture sources
- Vicon as a later/special integration, not a Capture V1 blocker
- Future wearable/physiology integrations as plugins

## Product principle

This is not an "EMG + camera app." It is a general-purpose synchronized multimodal capture platform whose first implemented source families are Delsys, cameras, Xsens, and Infineon radar.

Any one source, any subset, or all configured sources must be usable in a session.

## Recommended implementation

- Windows 11 x64 first
- Python + PySide6/Qt for the desktop application and scientific/post-processing layers
- C++20 for the capture daemon and performance-critical/native SDK workers where beneficial
- Separate worker processes for source isolation
- Shared-memory preview buffers
- Versioned IPC protocol between UI/daemon/workers
- Native-rate raw-data preservation
- Master session timeline with per-device time mapping
- Crash-safe incremental recording
- Packaged executable with persistent settings, presets, hotkeys, and an updater

Start by reading `MASTER_SPEC.md`, then `CURSOR_CONTEXT.md`, then `IMPLEMENTATION_PLAN.md`.
