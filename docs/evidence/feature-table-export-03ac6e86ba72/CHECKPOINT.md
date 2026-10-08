# Feature table export: author checkpoint

Issue: https://github.com/Jacob-Met/CaptureSuite/issues/78

This checkpoint is **unqualified draft source**, rooted in current canonical
`9c44354cb101c76beff79265de0040b6839d249f`. It is not a passing candidate,
a package adoption, or an integration request. The author source has not yet run.

## Frozen pre-implementation baseline

The archive `baseline-mac.tar.gz` retains the complete baseline script, the actual
synthetic MCAP session and its three completed feature tables, command stdout and
stderr, source/input inventories and the receipt. Original file bytes are retained.

- Python 3.12.8 on native macOS, existing CaptureSuite analysis environment.
- Current native `tools/run_analysis.py features ... --strict-warnings`: exit 0.
- Three full feature Parquet tables, existing CSV mirrors and feature schema.
- Current missing `tools/export_feature_table.py` entrypoint: actual exit 2.
- Every retained raw input hash unchanged.
- Baseline archive: 31,832 bytes; SHA256
  `888a7fce598cccc0947b116a463b9a248b1eb96581c73bd85a7104324b9b8972`.

## Capacity redirection

RDC returned `ENOSPC: no space left on device` when attempting the first new
17 KB source-file write on Mac. A subsequent read-only check confirmed the target
source file did not exist. The Mac had shown 1.2 GiB free a few minutes earlier.
The separate scratch overlay also reported 100% full, zero available.

No shared cleanup or dependency installation was performed. The implementation
was preserved from the author session into Git blobs, then this referenced draft.
Author qualification moves to a separate native Windows stage using existing
dependencies. An independent Windows receiver retains separate source and fixtures.

## Remaining work

Complete focused tests and documentation, qualify actual library/CLI export and
refusals, freeze exact source, receive it independently, and run required hosted
gates before source integration. Nothing in this checkpoint claims those results.
