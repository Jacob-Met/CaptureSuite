# Prompt: new C++ acquisition plugin

```text
Add a CaptureSuite C++ acquisition worker for:

- plugin_id: [vendor.product]
- display_name: [Human name]
- family / modality: […]
- data_schema_id: […]
- Vendor SDK: [path / package / license terms]

Requirements:
1. Start from workers/stub/ (Apache-2.0 template). Keep vendor SDK code inside the
   worker process only.
2. Speak Hello → Identify → Discover → GetConfigSchema → ApplyConfig → Start/Stop
   per docs/design/WORKER_HOST.md. CLI must accept:
   --pipe <name> --worker-id <id> --plugin <plugin_id>
3. Add plugins/<dir>/plugin.json pointing at the built .exe; set runtime.path_prepend
   / requires.env for SDK DLLs. Prefer CMake POST_BUILD copy into
   $<TARGET_FILE_DIR:capture_daemon>/plugins/<dir>/ (see workers/camera).
4. Do NOT add ExternalWorkerPluginSpec hardcoding in daemon — registry scans plugin.json.
5. StreamDescriptor: stable source_id, versioned data_schema_id, nominal_rate_hz,
   timestamp_source documented, explicit DISCONNECT gaps.
6. Adapter doc docs/design/adapters/<vendor>.md must exist (spike complete).
7. Tests: extend tests/cpp and/or protocol e2e; fake/replay path if hardware absent.

Verify: cmake build of the worker target; daemon ListPlugins shows enabled;
rescan lists sources; short record seals an MCAP/MKV segment.

Refs: docs/plugins/04_cpp_worker.md, workers/stub/, workers/camera/, workers/radar/
```
