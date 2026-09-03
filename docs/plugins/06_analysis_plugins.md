# Analysis plugins

Acquisition plugins write versioned streams. Analysis discovers them via
`stream.json` + `capture_analysis/plugins/manifest.yaml`.

To support a new `data_schema_id`:

1. Add a loader entry under `loaders:`
2. Add ≥1 feature extractor under `features:`
3. Optionally a plot entry

`generic.numeric_batch/1` ships with a basic RMS/mean feature
(`numeric.basic.v1`) so LSL and Python-SDK streams get QC without extra code.

See [ANALYSIS_PLUGIN_ARCHITECTURE.md](../design/research/ANALYSIS_PLUGIN_ARCHITECTURE.md).
