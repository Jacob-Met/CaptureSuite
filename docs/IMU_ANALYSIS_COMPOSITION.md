# Composed offline analysis with exact IMU timestamps

This source composition connects two already published CaptureSuite analysis increments. Its ordered parents are:

1. `778de777a26899895d014948a1b12d759a0f8d0f`: the offline analysis line containing recorded-gap EMG features, precise video cadence and plots, legacy-console-safe CLI output, strict sync JSON and finite nominal-rate admission.
2. `865f3900590da523ab66434b581e2ebb3688be1c`: the exact IMU feature timestamp correction from issue #121, owned and reviewed by the continuing d788ccfb3bfe team.

The first parent's IMU feature file still equals the common `3960c0c756cd4e9facbde0d76eaaa3c31ab7c167` baseline. The second parent's runtime file, maintained test, timestamp guide and eleven receiving records are imported byte-for-byte. Every other first-parent blob and mode is retained except this additive guide and the progress log. The progress log preserves the entire first-parent text, then the complete original IMU entry, followed by a separate integration entry. The merge retains both published histories.

## Resulting timestamp contract

The public IMU extractor returns the exact central recorded integer for odd windows. For even windows, it adds the two central values using Python integers and truncates a half nanosecond toward zero. This avoids float64 rounding and signed-int64 addition overflow. Input arrays, window and hop selection, gap behavior, and non-time sensor features retain the accepted implementation. See [the timestamp contract](IMU_FEATURE_TIMESTAMPS.md) and [the original receiving evidence](receiving/imu-timestamps-d788ccfb3bfe/README.md).

There is no new numerical implementation in this composition. The imported runtime Git blob is `329431e05d73d18e3a3da708537b4ec14bbc047b`, SHA256 `e325a2bb5312ae4816a34b25b4ae62256a50e7eb71f1fd1deee20b7922a15c8e`.

## Qualification and use

The composed package passed the imported seven maintained methods plus eighteen passing subtests on the existing isolated Python 3.12 environment. The original 512-case independent integer/Fraction oracle and original failures remain in their unchanged receiving records; they are historical evidence for the imported correction, not newly repeated composition results.

Native Windows receiving and saved MCAP comparisons are separate acceptance steps and are pending at source publication. Their exact source pin, device, interpreter, commands, outputs and limitations will be linked from issue #121 and the delivered receiving packet. Source publication alone does not claim desktop, hardware, live acquisition or default installation acceptance.

This composition excludes the still-unpublished EMG vectorization overlay and axis-origin/raw-plot overlays. Those remain distinct reviewed deliveries with their existing source-owner checkpoints. It does not change workflows, open a PR, update main, create a release tag or request GitHub Actions.

For an existing authorized source environment, use an isolated checkout pinned to the resulting merge commit and its normal analysis dependencies. The maintained focused command is:

```text
python -m pytest tests/analysis/test_imu_feature_timestamps.py
```

Use the delivered native instructions for the embedded Windows interpreter: its isolated configuration requires explicit package paths rather than assuming that PYTHONPATH is honored. Preserve earlier working sources and acquisition data.
