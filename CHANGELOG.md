# Changelog

All notable changes to CaptureSuite are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-09-03

### Added

- Plugin registry (`plugin.json`) replacing hardcoded camera/radar worker specs
- `ListPlugins` control RPC (protocol **1.5**)
- Python worker SDK (`libs/python/capture_worker`, Apache-2.0)
- Example sine plugin (`plugins/example_sine_py`)
- LSL bridge plugin (`plugins/lsl_bridge`) for Lab Streaming Layer outlets
- `generic.numeric_batch/1` payload schema + analysis loader/features
- GPL-3.0 / Apache-2.0 split licensing, community health files, `CITATION.cff`
- Operator docs (`docs/operator/`) and plugin author guide (`docs/plugins/`)
- `tools/run-demo.ps1`, expanded Windows CI + release workflows

### Changed

- Neutral sim source aliases (no vendor product names in core)
- Product specification moved to `docs/spec/`
- Lab hub paths / sync docs removed from the public product tree

### License

- Application (daemon, UI, analysis, tools): **GPL-3.0**
- Schemas, `capture_protocol`, `capture_worker` SDK, C++ stub: **Apache-2.0**
