# Development Instructions for Cursor / Coding Agents

Read these files before making architectural changes:

1. `MASTER_SPEC.md`
2. `CURSOR_CONTEXT.md`
3. `ARCHITECTURE.md`
4. `DATA_MODEL.md`
5. `IMPLEMENTATION_PLAN.md`
6. `DECISIONS_LOG.md`

## Core rules

- Do not hard-code the app around one camera or one EMG source.
- Do not route raw capture through the GUI process.
- Do not make preview reliability equivalent to capture reliability.
- Do not overwrite raw data with processed data.
- Do not resample raw streams during acquisition.
- Do not discard native device timestamps.
- Do not use aliases as hardware identity.
- Do not silently hide source gaps or dropped data.
- Do not make checkpoint naming delay checkpoint timestamp capture.
- Do not make destructive checkpoint timeline edits easy.
- Do not create vendor-specific logic in core session/storage code when it belongs in a plugin.
- Do not assume a multi-radar synchronization mode until verified on actual hardware.
- Do not begin the full analysis suite until Capture V1 foundations are stable.
- Preserve forward compatibility and version every on-disk/IPC schema.

## Implementation order

Prioritize:
1. schemas
2. protocol
3. simulator
4. daemon
5. storage/recovery
6. UI shell
7. real device backends
8. unified reliability
9. presets/mapping
10. export/review
11. pose processing
12. packaging/updater

## Coding style

- Strong typing where practical.
- Explicit state machines.
- Structured logging.
- Clear module boundaries.
- No hidden global mutable state.
- Every long-running worker must have deterministic shutdown.
- Bounded queues only for live streaming paths.
- Backpressure policy must be explicit.
- Preview paths may drop old data.
- Raw capture paths must report overload rather than silently dropping.
- Schema migrations must be tested.
- Hardware-specific assumptions must be documented near the adapter.

## Testing

Every new source backend should ship with:
- simulator/fake source
- unit tests
- failure-mode tests
- disconnect/reconnect tests
- timing tests
- long-duration test plan
