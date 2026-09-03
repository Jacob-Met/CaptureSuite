# Protocol Buffers — `capture.v1`

Source of truth for IPC messages. Session JSON Schemas are generated from the descriptor set — do not hand-edit `schemas/session/jsonschema/`.

```powershell
py -3.12 tools\gen_protos.py
py -3.12 tools\gen_session_schemas.py
```

Package version: major `1` (breaking changes require `capture.v2`).
