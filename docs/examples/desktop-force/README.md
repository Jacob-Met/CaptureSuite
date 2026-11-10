# Explore a saved measurement result

This example lets you reopen a saved recording, compare two analysis settings,
and export selected measurements without a device or a new capture.
Download [synthetic-force-example.zip](synthetic-force-example.zip), extract it
to a writable folder, and keep the `synthetic-force.mmsession` directory together.

The recording is **synthetic**. It contains 60 samples per channel at 10 Hz:
`ramp` increases from 12.5 to 27.25 in steps of 0.25, and `reference` stays
at 25.0. The unit label N is illustrative; no sensor calibration or physical
force measurement was performed. This demonstrates software behavior, not
hardware capture, signal quality, or clinical accuracy.

## Open and inspect

1. From the extracted native Linux desktop folder, open the sample in Analysis:

       ./capturesuite-desktop --analysis /path/to/synthetic-force.mmsession

   In an already open desktop, choose the Analysis workspace and use Browse
   to select that directory.
2. In Saved analysis, select **full-result**, then **Open saved result**.
   This reads the stored result; it does not run analysis again.
3. In Figure gallery, select the numeric **channel 0** tab. The title identifies
   the ramp channel. The plot covers the full six-second sample support.
   **Fit figure** shows the whole PNG; **Actual size (100%)** exposes original
   pixels with scrolling. Neither changes the saved image.
4. **Provenance and files** reveals the stored output inventory and hashes.
   The session is `example.synthetic-force`, and the result is `full-result`.
   The original raw MCAP remains under `sources/`.

## Compare the saved settings

Open **Parameters / compare**, choose the saved-job folder
`synthetic-force.mmsession/processing/jobs/late-window`, and inspect the
differences. That result uses **3,000,000,000 to 6,000,000,000 ns** (3–6 s)
and the Features command; the full result uses the full session and
Features + plots. The comparison is read-only.

Close the comparison, then open **late-window** from Saved analysis. It has
five measurement rows. Open **full-result** again for the export below;
that result has eleven rows.

## Carry three columns into another tool

1. Choose **Export measurements**. Confirm the visible session and saved result.
2. Choose **Clear selection**, then check `reference_rms`, `t_start_ns`, and
   `ramp_mean`. Select each row and use **Move up** until the selected columns
   are in that order. The units are N, ns, and N. Calibration is not recorded.
3. Choose **CSV + Parquet**, an existing folder outside the sample session, and
   a new folder name such as `force-review`. Choose **Export measurements**.
   The result should report **11 rows and 3 columns**.
4. Open the exported folder. `table.csv` and `table.parquet` have the same
   selected column order. `_schema.json`, `manifest.json`, and the `source/`
   metadata retain units and provenance. The original package is not rewritten.

The first exported row is approximately `25.0, 0, 13.625`; the last is
`25.0, 5000000000, 26.125`. Small floating-point display differences are normal.
Each row summarizes a one-second window with a half-second step.
An existing export destination is refused; select a new folder to retry.

Restart the application, reopen the session, and open **full-result** again.
Its figures and table are saved data and remain available without rerunning
the analysis.

## Provenance and reproduction

`EXAMPLE.json` inside the ZIP records the exact analysis source commit, generator
hash, raw MCAP hash, formulas, and limitations. The two saved jobs completed
without analysis warnings. That status describes the software job; it does not
validate an instrument or physical measurement.

With the repository's Python 3.12 analysis environment active, install the MCAP
writer used by this generator, then create a separate copy from the repository
root:

    python -m pip install mcap

    python docs/examples/desktop-force/create_example.py /existing/parent/new-example

The output directory must not exist. The generator uses the maintained analysis
engine and refuses to replace an existing example. It creates an explicitly
synthetic finalized package; it does not reproduce the daemon's acquisition
journal. The ZIP is the ready-to-open example, so recipients need no Python setup.

The guide and sample are produced by astra-ibis-57c90e21. Production and independent desktop
receiving are tracked on task `capturesuite-saved-example-ibis57c9`.
