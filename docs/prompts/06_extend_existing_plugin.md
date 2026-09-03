# Prompt: extend an existing plugin family

```text
Extend an existing CaptureSuite plugin family instead of creating a new plugin_id.

Existing plugin_id: [e.g. radar.ifx / camera.gstreamer]
Change: [new board, capture mode, stream class, config keys, …]

Rules:
1. Prefer ApplyConfig + StreamDescriptor fields over new plugin_id when the SDK
   and process model are the same
2. Bump schema_revision (never reuse a revision for a changed shape) — see
   .cursor/rules/config-schema-revision.mdc
3. Keep vendor logic inside the worker; update adapter doc with spike deltas
4. Update tests that assert schema_revision / capabilities
5. If the new board needs a different data_schema_id, that is OK on a new stream;
   do not overload an existing schema's meaning

Deliverables: worker + schema_revision bump + adapter note + tests green.
```
