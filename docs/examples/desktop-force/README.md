# Explore a saved measurement result

This example lets you reopen a saved recording, compare two analysis settings,
and export selected measurements without a device or a new capture.

Use the [native Linux desktop b520a9c release](https://github.com/Jacob-Met/CaptureSuite/releases/tag/native-desktop-2026-11-10-b520a9c)
or a later compatible desktop. Extract the whole application folder and keep
its executable and _internal directory together. The example ZIP contains data,
not another copy of the application.

Download [synthetic-force-example.zip](synthetic-force-example.zip), extract it
to a writable folder, and keep the synthetic-force.mmsession directory together.

The recording is **synthetic**. It contains 60 samples per channel at 10 Hz:
ramp increases from 12.5 to 27.25 in steps of 0.25, and reference stays
at 25.0. The unit label N is illustrative; no sensor calibration or physical
force measurement was performed. This demonstrates software behavior, not
hardware capture, signal quality, or clinical accuracy.

## Open and inspect

1. From the extracted native Linux desktop folder, open the sample in Analysis:

       ./capturesuite-desktop --analysis /path/to/synthetic-force.mmsession

   In an already open desktop, choose the **Analysis** workspace and
   **Open recording…** to select that directory.
2. In **Saved analysis**, select **Features + plots · 1 table · 3 figures**,
   then **Open saved result**. The date and completed status follow that label.
   This is the saved job full-result; opening it does not run analysis again.
3. In **Figures**, select the numeric **channel 0** tab. The title identifies
   the ramp channel. The plot covers the full six-second sample support.
   The entire PNG fits by default. **Actual size** exposes its original pixels
   with scrolling; **Fit figure** restores the complete view.
   Neither changes the saved image.
4. **Details** shows job_id=full-result, the saved settings, output inventory
   and hashes. The session header identifies example.synthetic-force.
   The original raw MCAP remains under sources/.

## Compare the saved settings

In **Details**, choose **Parameters / compare…**, then **Compare with saved job…**.
Select the folder synthetic-force.mmsession/processing/jobs/late-window.
The comparison shows 3,000,000,000 to 6,000,000,000 ns (3–6 s) and the
Features command, while the loaded result uses the full session and
Features + plots. The comparison is read-only.

Close the comparison. In **Saved analysis**, select the **Features · 1 table**
entry and choose **Open saved result**. This is late-window; **Tables** shows
five saved rows. Open the **Features + plots · 1 table · 3 figures** entry
again for the export below; it has eleven rows.

## Carry three columns into another tool

1. Open **Tables**. Confirm the session header, the loaded Features + plots
   result, the example.force · force.samples table, and **11 saved rows**.
2. Choose **None** below the column list, then check reference_rms, t_start_ns,
   and ramp_mean. Click the reference_rms **row label** to select that row,
   then use **Up** until it is first. The checked columns should now be in
   the order reference_rms, t_start_ns, ramp_mean. Checking a box alone does
   not select the row to move. The units are N, ns, and N; each says
   **Not calibrated**. If names are clipped, widen the column list using the
   divider beside the values preview.
3. Leave **Rows** at **All saved rows**. Choose **CSV + Parquet**, set **Save in**
   to an existing folder outside the sample session, and enter a new folder
   name such as force-review. Choose **Export selected columns**.
   The result should report **11 rows and 3 columns**.
4. Open the exported folder. table.csv and table.parquet have the same
   selected column order. _schema.json, manifest.json, and the source/
   metadata retain units and provenance. The original package is not rewritten.

The first exported row is approximately 25.0, 0, 13.625; the last is
25.0, 5000000000, 26.125. Small floating-point display differences are normal.
Each row summarizes a one-second window with a half-second step.
An existing export destination is refused; select a new folder to retry.

Restart the application, reopen the session, and open the saved
**Features + plots · 1 table · 3 figures** result again. Its figures and table
remain available without rerunning the analysis.

## Provenance and reproduction

EXAMPLE.json inside the ZIP records the exact analysis source commit, generator
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

The guide and sample are produced by astra-ibis-57c90e21. Production and independent
desktop receiving are tracked on task capturesuite-saved-example-ibis57c9.
