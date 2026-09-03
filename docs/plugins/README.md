# CaptureSuite plugins

CaptureSuite acquires data through **plugins**. The daemon discovers them from
`plugin.json` manifests ([PLUGIN_REGISTRY.md](../design/PLUGIN_REGISTRY.md)).

| Doc | Topic |
|-----|-------|
| [01_overview.md](01_overview.md) | Philosophy and layout |
| [02_python_quickstart.md](02_python_quickstart.md) | Write a plugin in ~80 lines of Python |
| [03_lsl_bridge.md](03_lsl_bridge.md) | Lab Streaming Layer (zero vendor code) |
| [04_cpp_worker.md](04_cpp_worker.md) | C++ stub template |
| [05_manifest_reference.md](05_manifest_reference.md) | `plugin.json` fields |
| [06_analysis_plugins.md](06_analysis_plugins.md) | Analysis loaders / features |
| [07_testing_and_validation.md](07_testing_and_validation.md) | provisional → hardware_validated |

## Scaffold + prompts

```powershell
.\tools\new_plugin.ps1 -PluginId "lab.force" -DisplayName "Force plate" -Family numeric -Modality force
```

Copy-paste Cursor/agent prompts: [docs/prompts/](../prompts/).
Cursor rule: `.cursor/rules/add-acquisition-plugin.mdc`.
