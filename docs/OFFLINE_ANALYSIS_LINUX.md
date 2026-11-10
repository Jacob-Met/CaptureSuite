# CaptureSuite Offline Analysis — experimental Linux build

**Purpose:** Open a sealed `.mmsession` recording and get usable QC, numeric
feature tables, and signal plots **without** installing Python or starting the
Windows-first capture desktop. This does not record live sensors or replace
hardware validation.

## Get started

Download the experimental **Linux x86-64** archive from this repository's
GitHub Releases page. Verify its published SHA-256 before extracting. After extraction,
`./capturesuite-analysis/capturesuite-analysis --version` prints the exact
source commit shipped in the bundle. On a
compatible Linux system, from a terminal:

```bash
tar -xzf capturesuite-analysis-linux-x86_64.tar.gz
cd capturesuite-analysis
./capturesuite-analysis qc "/data/my experiment.mmsession" --inspect-payloads --strict-warnings
```

The `qc` command writes an HTML report and machine-readable JSON to
`SESSION/processing/jobs/JOB_ID/reports/qc.html` and `qc.json`. The CLI prints
the exact generated job directory. Open the HTML with a browser. The original
sealed recording is **read only**; derived analysis jobs appear under
`processing/jobs` in that same package.

To compute provisional EMG/IMU features, create Parquet/CSV tables and
figures with the bundled offline analysis pipeline:

```bash
./capturesuite-analysis all "/data/my experiment.mmsession" --inspect-payloads
```

Five commands are supported in this experimental bundle: `qc`, `features`,
`plots`, `all` and `export-table`. Run `./capturesuite-analysis qc --help` for options,
including `--overwrite-job-id`, `--start-ns`, `--end-ns`, gap handling and
the `--inspect-payloads` switch (available for `qc` and `all`). Exit code 0
means a job completed, 2 means strict warnings triggered or an unsupported
bundled command was requested, and 1 means a job failed to run.

`--inspect-payloads` **reads and decodes real MCAP samples** for
`generic.numeric_batch/1`, `emg.batch/1`, and `imu.frame/1`. Unsupported
wire schemas are reported as structurally inspected only, not sample-validated.
It checks frame shapes, finite samples, channel or sensor identifiers, and
selected timestamp consistency. It can report constant EMG channels and zero
IMU quaternions as observations. **Passing is not proof of sensor calibration,
electrode contact, noise floor, sampling-rate truth or medical validity.**
Metadata-only QC (without the switch) cannot validate payloads.

## Export selected saved features

Start from the job directory printed by `features` or `all`. You can inspect its
tables and export a column selection without rerunning analysis:

```bash
./capturesuite-analysis export-table "/data/my experiment.mmsession/processing/jobs/JOB_ID" --list
./capturesuite-analysis export-table "/data/my experiment.mmsession/processing/jobs/JOB_ID" \
  --table TABLE_PATH_FROM_LIST --column t_start_ns --column "input 1_mean" \
  --output "/data/selected-features"
```

Use the exact path and column names shown by `--list`; `--list --json` is available
for scripts. The destination must be a new directory outside the session package.
Every retained row stays in its original order. CSV and Parquet are written by
default, with types, units, original warnings and job provenance beside them.
See the bundled [feature export guide](FEATURE_TABLE_EXPORT.md) for typed CSV
import, format options and failure behavior.

## Supported and unsupported

- The artifact is built on Linux x86-64, Python 3.12, Ubuntu 24.04-era glibc.
  It requires compatible glibc and basic runtime system libraries, but not a
  Python installation. It is **not** a Windows/macOS desktop application, and
  no native Windows binary or hardware integration is shipped here.
- The bundled `qc` and `all` workflows have been exercised with generated
  protobuf MCAP EMG, IMU, numeric-batch samples and deliberately invalid data,
  outside the source checkout. Real instrument calibration, full multi-hour
  stress performance, Windows GUI operation and physical acquisition remain
  unverified.
- `features`/`plots` inherit CaptureSuite's current supported offline
  streams. Features are research/provisional, not clinical diagnostics.
  `pose`, `kinematics`, `ml_bundle` and `eval` are intentionally not
  exposed in this Linux standalone package. Use the full source/desktop
  distribution for those workflows.
- Running a job creates derived files inside the package. Back up or copy
  recordings if you need them immutable as a directory. Raw files under
  `sources` are never overwritten by the analysis program.
- GitHub Release is explicitly marked **pre-release/experimental** until
  independent cross-platform and real-recording reviews are available.

## Build from source

From the exact release commit:

```bash
python3.12 -m venv .venv-analysis
.venv-analysis/bin/python -m pip install ./libs/python/capture_protocol \
    ./libs/python/capture_session './libs/python/capture_analysis[analysis]' pyinstaller mcap
.venv-analysis/bin/python -m pip check
PYTHON=.venv-analysis/bin/python scripts/build-analysis-linux.sh
```

This script packages the existing `run_analysis.py` pipeline with PyInstaller,
bundles the plugin manifest and session schemas explicitly, checks the frozen
entrypoint, and fails if required schema files are missing. The executable
lives at `build/analysis-linux-release/dist/capturesuite-analysis/`.
A build marker alone is not acceptance: test the frozen binary on both actual
MCAP data and corrupted inputs, then open `qc.html` and inspect feature CSV
and figure files.

The project is GPL-3.0-only; see the bundled `LICENSE` and `LICENSING.md`.

`all --inspect-payloads --strict-warnings` combines decoded-sample QC, features and plots in one job. Without the flag, QC remains metadata-only. Inspection warnings propagate to strict exit 2; feature calculation does not turn a QC warning into a calibration claim.
The build copies actual bundled third-party license/notice texts into
`THIRD_PARTY_NOTICES/`, including the Python runtime, PyInstaller bootloader
and CaptureSuite Apache-licensed contracts. `manifest.json` records notice hashes;
`DEPENDENCY_VERSIONS.txt` records exact installed versions. Missing distribution
notices fail the build. The local package install above respects each package's
dependency constraints, including capture-protocol's protobuf range.

Ubuntu builds require dpkg-query metadata and /usr/share/doc package copyright
files for native libraries copied into the bundle; absent attribution fails the
build. Their exact package versions and library basenames are in the same manifest.
