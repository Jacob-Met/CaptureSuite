# Windows console receiving

PR [#45](https://github.com/Jacob-Met/CaptureSuite/pull/45) first published the
exact qualified tree `57c6c75981bb14535a79d474fe419748f0423eac` at server-assigned
head `1ae47ae44a4a07d732a2c773c9cb62dc17253d01`. Its parent main was
`c43b2819b149e1e87d7f957d8b3583881c29ffb4`; the original PR #30 head was the
second parent, retaining the donor's commits.

## First Windows gate: failed and retained

[Run 37758185607](https://github.com/Jacob-Met/CaptureSuite/actions/runs/37758185607)
checked out merge commit `1fc4ed6f67a5288c16ee043c0ee4d4c759b68d1f`.
Its Python job reached all 255 cases: **246 passed, three failed, six skipped**.
The six skips explicitly require a separately built daemon. All three failures
were real Unicode destination cases: export files and the manifest were
successfully written, then `print("wrote", man_path)` raised
`UnicodeEncodeError` through a cp1252 stdout pipe. The process exited 1.

The Python artifact was downloaded, its ZIP SHA-256 checked against the hosted
digest, and its receipt, raw JUnit, raw test log and source manifest retained in
`windows-first/`. The receipt's JUnit and log hashes were independently checked.
The original receipt remains `accepted: false`.

The same run's CMake job reports successful configuration, strict compilation,
CTest and native daemon/recovery integration. Its artifact metadata is retained
in `windows-first-run.json`; that C++ archive was not downloaded for this
record. A passing CMake job does not override the failed Python gate.

## Narrow repair and local control

The CLI now configures stdout's encoding-error policy as `backslashreplace`
at its entry point. It preserves the stream's encoding. A terminal that can
represent the path continues to display it; a legacy pipe receives escaped
status text for characters it cannot represent. Filesystem paths, stream data,
manifest content, stderr handling and export error policy are unchanged.

A real exporter child process under `PYTHONIOENCODING=cp1252:strict` reproduces
the hosted failure on the earlier source. The added test verifies successful
mixed EMG/IMU output in the original Unicode directory, an escaped status path,
correct decoded records and unchanged raw hashes. It does not claim to emulate
the Windows filesystem.

| Gate | Result |
|---|---|
| Added legacy-pipe case on pre-repair source | 1 failed, 18 deselected; exit 1 |
| All analysis tests on clean correction `8794bea09f25dc3525d0c273fef2d8b277704afd` | 60 passed, no skips; exit 0 |
| Configured repository Ruff | Passed |
| Next full hosted Windows run | Required; not yet accepted by this record |

`receipt.json` and `source-manifest.json` bind the 60-case run to clean,
unchanged source through the project's native receipt helpers. Raw before/after
logs and JUnit are included. `artifact-hashes.json` covers the retained outputs.
The source runtime was CPython 3.12.14 on Linux; the first hosted failure used
CPython 3.12.10 on Windows Server 2022. No installed app or device was changed.

Replay the focused console case with the repository's declared dependencies:

```sh
QT_QPA_PLATFORM=offscreen python -m pytest \
  tests/analysis/test_export_selection_mcap.py -k legacy_pipe_encoding -q -ra
```

The test sets the child pipe encoding explicitly. Existing tests continue to
exercise ordinary Unicode paths and the separately accepted output-failure
behavior from [r2](../r2/README.md).

Independent lead receiving also ran a separate real child process under
`cp1252:strict`, using the long-source-ID fixture and an actual Unicode
destination. It exited 0 with both EMG and IMU present, no stderr and unchanged
raw source hashes. `peer-console-receipt.json` binds that result to exporter
SHA-256 `0b83d42da26fa62426741f1dcca6814f4d5631a8d700d3c31cf6eb64a1da8b0e`.
The lead accepted the narrow source change while retaining the separate hosted
Windows gate.

## Current-main composition

Before the forward update, main advanced to
`52203f5ceedfa0da8f1813e700a41ec8c364263e`, including the independently received
Linux storage/recovery work and stream-gap analysis fix. A normal merge at
local `e73ea7641dbb55a74d7c8c2d021cab2cfd5af045` preserved every upstream file
and both progress records without conflicts. The exporter hash remains the
same one accepted by the lead. All **68 analysis tests passed**, including the
new upstream stream-gap cases, on clean and unchanged source. Exact receipt,
source manifest, log and JUnit are retained in `composed-main-522/`.
