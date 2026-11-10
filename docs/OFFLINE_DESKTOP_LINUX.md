# CaptureSuite native offline desktop for Linux

This experimental distribution contains the existing CaptureSuite desktop,
its Python runtime, Qt, plotting and measurement dependencies. Extract the
whole folder and launch the executable; no Python installation is required.

## Launch

The release targets Linux x86_64. It is built on Ubuntu 24.04 with glibc 2.39
and needs a graphical desktop, its usual display/OpenGL libraries and fonts.
Other distributions and older glibc versions are not yet claimed as tested.
This is the offline research workbench; physical acquisition still uses the
Windows daemon and hardware plug-ins.

```sh
tar -xzf capturesuite-desktop-linux-x86_64.tar.gz
cd capturesuite-desktop
./capturesuite-desktop
```

Keep the executable and its `_internal` directory together. You can move the
whole extracted folder or launch it from another working directory. The
`SOURCE_COMMIT` file identifies the exact source used for the build.

## Work with a recording

Open a sealed or recovered `.mmsession` folder in Review or Analysis.
Use Review to inspect the recording and its notes, checkpoints and gaps.
In Analysis, choose the recording, sources and time scope before running QC,
features, plots or combined analysis. Generated jobs stay under the recording's
`processing/jobs/` folder. Original streams remain unchanged.

Reopen a retained job to inspect its figures and measurement tables. Export the
selected measurements when another analysis tool needs them. Keep warnings and
units with the data: simulated inputs and provisional feature methods do not
establish instrument accuracy or clinical validity.

The session export dialog uses the bundled exporter. It does not need an
external Python. Video rewrapping uses an external `ffmpeg` if installed;
otherwise the original MKV is copied and the export manifest says so. The
bundled Qt player handles recorded-video playback through Qt's media backend;
codec availability and damaged recordings can still limit playback.

Real pose-model packages, model weights and hardware drivers are not included.
Do not infer working physical capture or model inference from this offline
release. The bundled repository mini-session includes placeholder MCAP files;
use a genuine recording for payload analysis.

## Build from source

Use CPython 3.12 in a separate environment and install the local packages
together so their declared dependency constraints are respected:

```sh
python3.12 -m venv .venv-desktop-release
. .venv-desktop-release/bin/activate
python -m pip install ./libs/python/capture_protocol \
  ./libs/python/capture_session './libs/python/capture_analysis[analysis]' \
  './desktop[analysis]' 'mcap>=1.6,<2' pyinstaller
python -m pip check
PYTHON="$VIRTUAL_ENV/bin/python" bash scripts/build-desktop-linux.sh
```

The result is `build/desktop-linux-release/dist/capturesuite-desktop/`.
`OUTPUT_ROOT` can select an isolated output directory. Build on the target
platform; a Linux bundle is not a Windows or macOS distribution. Before
publishing, launch the extracted folder through the actual application entry
point, exercise a real MCAP-derived analysis and exported result, and have
another contributor judge the resulting native interface.

The bundle includes application and contract licenses, dependency notices and
the versions actually collected by PyInstaller. Corresponding source is
available at the exact commit in the same repository as the release.
