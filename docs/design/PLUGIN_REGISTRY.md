# Plugin registry

Pinned decision: acquisition plugins are discovered from on-disk `plugin.json`
manifests. Daemon core session/storage code must not hard-code vendor or
modality branches for worker selection.

**Status:** Normative (promoted from research `ACQUISITION_PLUGIN_CONTRACT.md`).

## Discovery order

1. `{daemon_dir}/plugins/*/plugin.json`
2. `%LOCALAPPDATA%\CaptureSuite\plugins/*/plugin.json`
3. Each directory listed in `CAPTURE_PLUGIN_PATH` (`;`-separated on Windows)
4. Built-in fallbacks for `camera.gstreamer` and `radar.ifx` when no JSON is
   found (legacy layout under `workers/`), so existing builds keep working.

`sim.builtin` is always registered as an `in_process` plugin.

## Manifest

See [schemas/plugin/plugin_manifest.schema.json](../../schemas/plugin/plugin_manifest.schema.json)
and examples under `schemas/plugin/examples/`.

## Runtime PATH / env

Worker spawn prepends `runtime.path_prepend` and applies `runtime.env` from the
manifest. GStreamer and Infineon SDK paths belong in plugin manifests, not in
hardcoded daemon logic (legacy prepend remains as a safety net until all
plugins ship manifests).

## Control RPC

`ListPlugins` (protocol ≥ 1.5) returns installed plugins with enablement state
and a human-readable `disabled_reason` when an SDK env is missing.

## Author checklist

See [docs/plugins/](../plugins/) and the research contract
[ACQUISITION_PLUGIN_CONTRACT.md](research/ACQUISITION_PLUGIN_CONTRACT.md).
