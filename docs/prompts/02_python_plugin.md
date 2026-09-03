# Prompt: new Python acquisition plugin

```text
Add a CaptureSuite acquisition plugin in Python.

Identity:
- plugin_id: [lab.device]          # dotted, lowercase
- display_name: [Human name]
- family: [numeric|emg|imu|camera|radar|…]
- modality: [open string, e.g. force]
- data_schema_id: [generic.numeric_batch/1 unless spike justified a new schema]
- hardware: [true|false]
- license of plugin code: [Apache-2.0 recommended for plugins]

Requirements:
1. Run: .\tools\new_plugin.ps1 -PluginId "…" -DisplayName "…" -Family … -Modality …
   (or create plugins/<dir>/ by hand mirroring example_sine_py)
2. Implement Worker subclass: discover, config_schema, start/stop; emit_samples
   with native device timestamps; emit_preview via build_trace_preview (or
   appropriate kind). Never resample. Log gaps on disconnect.
3. plugin.json must be discoverable; executable = run_worker.cmd
4. Prefer generic.numeric_batch/1. Do NOT edit daemon session/storage for vendor logic.
5. Unit tests in tests/protocol/test_<slug>_plugin.py (discover + config at minimum)
6. README in the plugin folder: SDK install, env vars, how to enable
7. If hardware: link or create docs/design/adapters/<vendor>.md; features stay
   provisional until bench parity

Verify:
- python -m pytest tests/protocol/test_<slug>_plugin.py -q
- Restart capture_daemon; source appears after ListSources / Rescan
- Create Session → Rehearse shows preview (if implemented)

Refs: docs/plugins/02_python_quickstart.md, docs/design/PLUGIN_REGISTRY.md,
libs/python/capture_worker/, plugins/example_sine_py/
```
