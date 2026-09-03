# Vendor replay spike fixtures

Sim-first tooling for replaying vendor-captured batches without bench hardware.

## Layout

```
tests/fixtures/vendor_replay/
  emg/sample_batches.jsonl   — minimal Delsys-shaped batch export (8 ch)
```

Each JSONL line is one EMG batch with native `timestamp_ns` and per-channel samples.
Use these fixtures to validate replay ingest before wiring `capture_worker_emg`.

## Ingest helper

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" `
  tools/vendor_spike/ingest_replay_fixture.py `
  --modality emg `
  --source tests/fixtures/vendor_replay/emg/sample_batches.jsonl
```

Copies the fixture into a session-scoped replay folder under `%LOCALAPPDATA%\CaptureSuite\vendor_replay\`.

## Phase 4 scope

- Fixtures + ingest script only (no hardware worker)
- Sim sources tagged **provisional** in the desktop expanded card
- Full Delsys worker remains Phase 8 hardware validation
