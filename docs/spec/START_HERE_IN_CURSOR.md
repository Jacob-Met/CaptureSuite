# Start Here in Cursor

## Recommended first message to Cursor

Paste or reference this:

> Read `AGENTS.md`, `MASTER_SPEC.md`, `CURSOR_CONTEXT.md`, `ARCHITECTURE.md`, `DATA_MODEL.md`, `IMPLEMENTATION_PLAN.md`, and `DECISIONS_LOG.md` before writing code. Treat those documents as the current product specification. We are beginning Capture V1. Do not redesign the product around only EMG and video. The core must support arbitrary source plugins, and Capture V1 must implement Delsys, cameras, Xsens, and BGT60TR13C radar including multi-radar configurations. First, propose the repository skeleton and versioned protocol/session-schema design for Milestones 1–3. Do not begin vendor-specific drivers until the generic simulator, daemon, storage, and recovery architecture is coherent.

## First coding objective

Create only the architectural skeleton:

- CMake/C++ capture daemon project
- Python/PySide6 desktop project
- protocol schema project
- Python/C++ generated protocol bindings
- simulator worker
- session-schema definitions
- storage abstraction
- worker registry
- source state machine
- structured logging
- unit-test harness

Avoid polished UI work at this stage.

## First proof-of-concept

The first end-to-end test should be:

1. Start desktop UI.
2. UI discovers capture daemon.
3. Daemon discovers four simulated source families:
   - simulated camera
   - simulated EMG
   - simulated IMU
   - simulated radar
4. User selects an arbitrary subset.
5. `Start Selected` arms them.
6. All produce independently timestamped streams.
7. Data is written incrementally.
8. UI receives reduced-rate previews.
9. Checkpoint button creates one global timestamped checkpoint.
10. One simulator deliberately disconnects.
11. Healthy simulators continue.
12. Disconnected source rejoins with an explicit gap.
13. Stop finalizes the session.
14. Reopen the saved session.
15. Verify stream timing, checkpoint metadata, gap metadata, and integrity information.

Do this before integrating real hardware.

## Important reminder

The later analysis suite is out of current scope except for ensuring the session format can support it. Post-capture video landmark extraction is part of the first product, but it should be implemented only after capture reliability is mature.
