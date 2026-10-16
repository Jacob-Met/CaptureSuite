# Metric Human Lab — Independent Research Subproject

This is an **independent MIT-licensed experimental project**, deposited in a
separate `research/metric-human-lab/` namespace in CaptureSuite for source custody
and collaboration. It does **not** alter or integrate with CaptureSuite's capture
daemon, analysis pipeline, or GPL-3.0 application code.

- Human reconstruction: `src/metric_human/`
- Tests: `tests/`
- Synthetic data/benchmark reports: `demo/`
- Architecture and results: `docs/`
- Packaging: `pyproject.toml`
- Complete immutable source/demo/release history archive: `releases/parts/` + `releases/reassemble.py`

The historical archive contains **all three archived v0.1.0-v0.3.0 versions**,
synthetic mesh/viewer assets, and original execution evidence; some large synthetic
binary demo assets are in that archive rather than duplicated as source-tree blobs.

Current validated version: **v0.3.0**, with **76 passing tests** in its documented
environment. This is a research prototype; real RGB-photo physical measurement
accuracy, scale estimates and real-scan generalization are not validated.

From this directory, use the standalone package's README for installation and
`python -m pytest -q` for tests. This GitHub branch intentionally does not run
or change any CaptureSuite CI workflows.
