# Offline Analysis desktop

Open a recorded session, reopen saved analysis, inspect complete figures and
carry selected measurement columns into another analysis tool. This is the
maintained CaptureSuite Analysis workspace, shared with the Windows capture
desktop.

## Run the Linux bundle

Extract the entire archive, keep the directory together, and run:

    ./RUN.sh /path/to/session.mmsession

With no package argument, use File → Open recorded session or Browse. No Python
installation is needed for the frozen bundle. The supported receiving target is
Linux x86_64 with glibc 2.39 or newer and an X11 desktop (tested on Ubuntu 24.04).
The build includes the Qt libraries collected from its actual dependencies.
A working display server and system graphics driver remain required.

For a source environment whose Qt X11 runtime is missing, the observed Ubuntu
24.04 prerequisites are:

    sudo apt-get install libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4         libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxcb-xkb1

A display-library error is a failed launch; an offscreen render is not evidence
that the X11 application runs. The release notes record the actual receiving
check and any additional runtime limitations.

## Reopen and use a result

Choose a job in Saved analysis, then Open saved result. This reads the saved job
without rerunning analysis. Figure tabs include nested source and stream images.
Fit figure shows the entire PNG; Actual size (100%) lets you inspect original
pixels. Viewing scale never changes saved figures or exported files.

Parameters / compare and Result details show the settings and diagnostics of
the open job. Provenance and files reveals the exact stored paths and hashes.
Switching sessions clears the old result. If the recording has no known duration,
the timeline says so; an explicit time range can still be entered.

Export figures keeps the original PNGs. Export measurements identifies the
session and saved result, then lets you choose a table, select columns, arrange
their order and export CSV, Parquet or both. Finding a column only filters the
visible list: hidden selected columns remain selected, and the count shows the
full selection.

Choose an existing parent directory outside the session and a new folder name.
Existing destinations are refused. All rows retain their original order; the
export includes recorded units, calibration flags, source warnings and provenance.
Calibration flags are recorded metadata, not a new validation of the sensor.
A failed export explains what happened and can be retried with a new destination.

## Run or build from source

Use Python 3.12 and the maintained local package dependencies from the repository:

    python3.12 -m venv .venv
    .venv/bin/python -m pip install -e libs/python/capture_protocol         -e libs/python/capture_session -e 'libs/python/capture_analysis[analysis]'         -e 'desktop[analysis]'
    .venv/bin/python -m capture_desktop --offline /path/to/session.mmsession

To create the same standalone distribution, install PyInstaller in that
environment and use the maintained builder:

    .venv/bin/python -m pip install pyinstaller
    PYTHON="$PWD/.venv/bin/python" scripts/build-desktop-linux.sh

The builder checks dependencies, freezes the actual desktop entry, collects the
included distribution and native-library notices, records SOURCE_COMMIT, and
checks the packaged command line. A real display/session/export receiving check
is still needed before publishing. The root LICENSE, NOTICE, LICENSING.md,
THIRD_PARTY_NOTICES and exact matching source accompany the delivered bundle.

## Current limits

This offline desktop is experimental. QC, Features, Plots, and Features + plots
are available. Capture and teacher-model workflows remain in the full Windows
desktop. Receiving checks use synthetic signals encoded in actual MCAP files;
they establish software behavior, not physical-device or clinical accuracy.

The source workflow and an independent X11 operator course have been exercised.
Packaging and the revised visual judgment are still in progress; this document
does not yet claim a published desktop release.

## Implementation

Offline startup does not import Windows named-pipe transport. The offline window
hosts the existing SessionHeader and AnalysisScreen. Analysis workers, persistence,
saved history, figures and table export stay shared with the full desktop; there
is no separate analysis algorithm or data format.
