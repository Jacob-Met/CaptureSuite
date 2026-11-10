# Inspect a recorded session offline

CaptureSuite's native desktop can open finalized `.mmsession` directories without a
capture daemon. This is an experimental Linux source distribution; acquisition and
Windows named-pipe daemon connections remain Windows-only. Python 3.12, a graphical
desktop and internet access for the first dependency install are required.

On a minimal Ubuntu desktop, Qt's X11 plugin also requires these system libraries:

```sh
sudo apt-get install libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
  libxcb-keysyms1 libxcb-render-util0 libxcb-xkb1
```

From the extracted release directory:

```sh
./scripts/run-desktop-offline.sh --review /path/to/recording.mmsession
```

Or run `./scripts/run-desktop-offline.sh`, select **Review**, then **Open recorded
session…**. The picker reads the directory directly. It does not recover, edit or
register the recording. Active packages are refused; stop recording or recover the
package first. **Analysis** continues to have its own package selector.

In **Events**, choose a kind or source and enter literal search text to find notes,
names, tags and other recorded fields. Select a row to inspect the full retained
record. Source IDs are case-sensitive; text search is case-insensitive. Clear
filters returns every loaded event. Duplicate records remain distinct. Exact
integer nanoseconds are preserved, including values above JavaScript's integer
precision limit. Malformed or missing times read **Unavailable**, after timed rows.
A malformed effective checkpoint time never silently falls back to its original.

Gap details come from the package reader's summary, with closure state, end time
and lost count displayed independently. Missing event records do not prove that a
recording is complete. Recorded video retains its explicit segment-local clock;
event selection does not claim synchronized video seeking. Failed or different
package loads clear old notes, video and session context.

The source install uses the repository's declared package dependencies. Set
`CAPTURE_DESKTOP_VENV` to an alternate isolated environment, or run
`./scripts/run-desktop-offline.sh --setup-only` to refresh it after replacing the
source. The supported invocation for an existing installation is
`python -m capture_desktop --offline` or `python -m capture_desktop --review PATH`.
Linux defaults to the existing offline Analysis/Review workspace; acquisition
controls are hidden. `--analysis [PATH]` opens Analysis directly. No live
connection is attempted by these offline entries.

## Scope of current evidence

Author astra-mica-6f2b exercised native Qt on Linux with authored on-disk event
records, including duplicate timestamps, Unicode, literal markup, invalid values,
recovered and failed package transitions. Native recorded-video decoding was also
run. These are software and recorded-file workflow checks, not physical sensor,
calibration, Windows acquisition or timing-accuracy validation. Current release
notes and taskboard hold exact source and independent actual-use results.
