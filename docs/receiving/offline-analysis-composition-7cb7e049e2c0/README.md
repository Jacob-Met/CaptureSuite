# One pinned offline analysis receiving composition

This source composition joins two independently reviewed parents in this order:
- First parent, video timing, observation plotting and CLI console output:
  ee0c9a2c0149c28de5089568680163f540610591.
- Second parent, EMG gap adjacency: 95ae1955dcff15c7cc4df77ebe66817dbc9b8094.

The first parent contains video timing 5b775845e480420b80a30a620c292624a2106a34
and plotting d34dabc4b0826481f91c2f229def2d11d063fd60. The second parent contributes
the exact accepted EMG extractor, regression test and guide. No numerical
implementation is edited during composition. The separately reviewed EMG
vectorization proposal is outside this source.

## What the combined checkout provides

EMG waveform/crossing features respect original sample adjacency and recorded
gaps. Video cadence uses valid original intervals with exact integer timestamp
subtraction. Relative plot axes preserve short offsets at large timestamp origins,
and isolated finite points stay visible without connecting missing intervals.
The offline CLI retains the actual job exit policy when a result path contains
characters outside its console encoding. Existing raw data and stored paths are
preserved.

The change from the first parent is limited to the three exact EMG files, this
guide, and additive PROGRESS history. Its complete existing progress prefix
remains intact, followed by the original root EMG entry and a new composition
note. Historical references to hosted CI in that original entry are preserved as
history; this composition uses direct local/native receiving and no GitHub Actions.

## Combined receiving selection

Use Python >=3.12,<3.13 and the existing analysis dependencies. From the checkout:

    python -B -m pytest tests/analysis/test_emg_gap_adjacency.py tests/analysis/test_video_qc_intervals.py tests/analysis/test_plot_observations.py tests/analysis/test_cli_console_encoding.py tests/analysis/test_job_failure_cli.py tests/analysis/test_phase_b_features.py tests/analysis/test_numeric_batch_pipeline.py tests/analysis/test_stream_gap_scope.py tests/analysis/test_feature_table_paths.py -q -p no:cacheprovider

The selection combines 14 EMG methods, the previously received 98-case video/plot/
neighboring gate, and 22 CLI/failure-recovery cases: 134 concrete cases. Passing
unittest subtests may increase a JUnit aggregate count; report concrete testcase
elements and aggregate totals separately. Source fingerprints must remain
unchanged. A source publication alone does not establish a passing combined gate.

Independent whole-tree/source-identity review and the exact native combined
result are tracked on issue119's shared-team composition comments. This guide
does not assert a native pass before that receipt exists. Previous individual
receiving results remain attached to their original source pins.

## Intended consumer and limits

The consumer is an isolated owned Windows offline-analysis checkout. Run
tools/run_analysis.py on a new copy of a synthetic or authorized recording, using
a fresh generated job ID. Keep recorded sources and retained jobs unchanged.
The maintained CLI guide and individual EMG/video/plot/output guides retain their
respective contracts.

This is a focused analysis composition, not the full project/protocol gate,
desktop acceptance, physical capture, hardware synchronization or a change to an
existing owner's installed application. No daemon, service, hardware, PR, main,
tag, workflow change or Actions operation is part of this contribution.
