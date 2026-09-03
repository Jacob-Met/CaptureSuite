# Prompt: register analysis for a schema

```text
Register CaptureSuite analysis support for data_schema_id: [domain.name/1]

Context:
- Produced by plugin(s): [plugin_id…]
- Modality: […]
- Sample shape / units / rate: […]

Do:
1. If the wire schema is new (not generic.numeric_batch/1), add
   schemas/proto/capture/v1/data/<name>.proto, regenerate with tools/gen_protos.py,
   and document the schema id/version.
2. Add loader under libs/python/capture_analysis/capture_analysis/loaders/
3. Add ≥1 feature extractor under features/ (mark provisional: true until
   hardware_validated)
4. Register both in capture_analysis/plugins/manifest.yaml
5. Optional: plot entry + Analysis UI affordance only if an existing kind cannot
   render it
6. tests/analysis/test_<schema>_features.py on synthetic or fixture data

Do NOT: invent vendor names in core; bake overlays into raw camera files;
silently interpolate gaps.

Refs: docs/plugins/06_analysis_plugins.md,
docs/design/research/ANALYSIS_PLUGIN_ARCHITECTURE.md
```
