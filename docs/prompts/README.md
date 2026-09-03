# Prompt templates

Copy one of these into a Cursor chat (or issue) and fill the bracketed fields.
Agents should also load `.cursor/rules/add-acquisition-plugin.mdc` when working
these tasks.

| Template | Use when |
|----------|----------|
| [01_vendor_spike.md](01_vendor_spike.md) | First contact with a vendor SDK / board |
| [02_python_plugin.md](02_python_plugin.md) | New out-of-process acquisition plugin in Python |
| [03_cpp_plugin.md](03_cpp_plugin.md) | C/C++-only SDK or tight capture loop |
| [04_analysis_schema.md](04_analysis_schema.md) | New `data_schema_id` needs loaders/features |
| [05_lsl_only.md](05_lsl_only.md) | Device already speaks Lab Streaming Layer |
| [06_extend_existing_plugin.md](06_extend_existing_plugin.md) | New board/mode inside an existing family |

Scaffold without an agent:

```powershell
.\tools\new_plugin.ps1 -PluginId "lab.force" -DisplayName "Force plate" -Family numeric -Modality force
```
