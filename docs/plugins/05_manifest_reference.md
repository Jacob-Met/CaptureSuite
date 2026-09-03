# plugin.json reference

Schema: [schemas/plugin/plugin_manifest.schema.json](../../schemas/plugin/plugin_manifest.schema.json).

Required: `plugin_id`, `plugin_version`, `family`, `display_name`, `executable`.

Important optional fields:

| Field | Meaning |
|-------|---------|
| `isolation` | `per_source`, `shared`, or `in_process` |
| `enable_env` | Set to `0` to force disable |
| `requires.gstreamer` | Need GStreamer runtime |
| `requires.env` | Soft/hard env requirements |
| `runtime.path_prepend` | PATH entries for vendor DLLs (`${ENV}` expanded) |
| `capabilities.emits_arrays` | Enable radar-array UI affordances |
| `capabilities.hardware` | `"1"` / `"0"` for UI honesty badges |
| `license` | SPDX id of the plugin itself |

Examples: `schemas/plugin/examples/`.
