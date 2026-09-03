# LSL bridge plugin

Records [Lab Streaming Layer](https://labstreaminglayer.org/) outlets into
CaptureSuite using `generic.numeric_batch/1`.

## Requirements

```powershell
pip install pylsl
```

## Behavior

- One `SourceInstance` per resolved LSL stream
- `source_id` from LSL `source_id` / UID
- `modality` from LSL `type` (open string)
- Device timestamps preserved; `time_correction()` applied per chunk (no resample)
- Gaps appear when the inlet times out with no samples (logged by the worker)

## Config

`name_filter`, `type_filter`, `chunk_size`, `timeout_s` via ApplyConfig JSON Schema.
