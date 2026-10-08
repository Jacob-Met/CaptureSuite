# Recorded-video Review receiving

Issue [#89](https://github.com/Jacob-Met/CaptureSuite/issues/89) · external contributor `chatgpt-0378a7b6b7c2/mac_product`.

## Product and source boundary

Original native parent `a2c89957c2cfe6fd5347d4ac317982449d3baa3a` loads retained MKV inventory but has no recorded-video controls. The candidate adds explicit segment selection, play/pause and seek using existing PySide6 QtMultimedia. The clock is media-segment-local. No audio output, checkpoint mapping, camera synchronization, gap interpolation, capture change or raw-data write is introduced.

Production SHA-256:
- `review_video.py`: `f8116601de2b920140d430d59460e07b7f80167d8151fb90f80534eda7f181d5`
- `widgets_review_video.py`: `3d89f1f8453a3d18d2776574941a2c6197f3be59e8df3a7a278f3b5c400134d9`
- `screen_review.py`: `8ee038aaca15d6f96ae3df8b4894466f404b6da8a0016179f70f267077f3ff36`

The shared-screen edit is seven additive import/construction/reset/load lines. The existing event-browser contribution (#76 / PR83) retains its separate ownership. All 1,159 other original tracked source leaves were exact during presentation receiving. The later guide, operator index pointer, design decision and required progress entry are declared documentation changes. No dependency, schema, discovery, analysis, export, app or workflow source changed.

Native advisory discovery saw 297 readable and 17 permission-denied coordination records. No recorded-video viewer claim appeared in readable coverage. This is an external contribution/issue reservation, not a fabricated native goal lease. Original advisory claim is retained as `claim.json`.

## Native runtime and original witness

LA7 Windows, private CPython 3.12.10 environment, PySide6 / Qt 6.12.0. The unchanged CI requirements installed into a task-local virtual environment; PyAV 19.0.1 was used only to author receiving fixtures. Neither production nor maintained tests depend on PyAV. Runtime provenance is retained in `runtime.json` and `runtime-freeze.txt`.

`baseline.py` was authored and run before production edits. It generated a finalized synthetic package containing two descriptor streams and four listed media files. Three tiny FFV1 files encode red→blue, yellow and green at 160×120, 10 fps, two seconds; one file is intentionally invalid. No real recording, physical device, daemon or live service was used. `baseline.json` seals all original tracked source hashes and raw package hashes; the actual original Review screen lists both streams and all four files while lacking Play/segment/seek controls. `tests/fixtures/review_video/` retains the exact synthetic package. The driver requires a fresh private output directory and is an original witness, not an idempotent regeneration command.

## Qualification

- `first.log` / `first.xml`: 15 focused model/native Qt cases passed, zero skips/errors, 8.15 seconds. Actual QMediaPlayer/QVideoSink decodes known red/blue/green frame pixels. Explicit pause and seek reach 1500 of 2000 ms; selection, stale errors, invalid/missing files, explicit reload, finalized admission, empty/failed package loads and keyboard/collapse/hide behavior are checked. Original fixture bytes remain exact.
- `first-ruff.log` preserves eight initial style findings. Import correction and formatting affected only owned files. Final scoped Ruff passed. Production and test pins after formatting are recorded in `presentation.json`.
- `ui-suite.log` / `ui-suite.xml`: final formatted source passes all 151 model plus inherited UI cases, zero skips/errors, in 256.11 seconds; two inherited protobuf deprecation warnings remain visible.
- `presentation.py`, `presentation.json`, `presentation.log`: actual decoder pause/seek/pixel controls and source/raw preservation pass on final pins. Readable dark/light and 760-pixel-wide control layouts are in `candidate-*.png`. The original screen at the parent is rendered separately as `baseline-fonts.png`.
- [Independent MSI review](independent-msi/REVIEW.md) accepts the complete exact production source and a distinct six-group native oracle. Rapid A→B→A without an event pump, 14 real retired-player signal emissions, separately deferred callbacks and independent generation/identity challenges cannot revive stale media. Slider 3333 reaches 666/2000 ms despite a 9,876,543,210,000,000 ns checkpoint. Error/reload and failed-package state retirement pass. The independent source/fixture/changed-input hashes remain exact.

## Presentation boundary and retained failures

The initial `baseline.png` rendered missing glyph boxes. The receiving application subsequently loaded existing Segoe UI fonts from the Windows installation; no installed font, theme or product code was changed. Their exact hashes are in `presentation.json`.

Qt offscreen QWidget captures omit QVideoWidget's GPU video surface. `decoded-blue-frame.png` is the actual decoded QVideoSink image, **not** a composite or onscreen viewport screenshot. Readable controls and frame decoding are separate observations.

A separate Qt **windows** platform run attempted to grab only its own synthetic Review window by HWND. `candidate-windows-dark.png` is entirely black; the pixel assertion failed. The exact `native_window.py` and `native-window.log` are retained, with no fabricated success receipt. The cause of that whole-window capture failure is unresolved. **Onscreen GPU-video presentation is not qualified by this record.** Standard QVideoWidget rendering is retained; no renderer was altered just to satisfy screenshot tooling.

The independent receiver's first run stopped on an inherited recovery-banner assumption before its playback groups. Its original driver, receipt and log remain in `independent-msi/`. The corrected receiver supplies the existing `recovered=True` argument and changes only its isolation/output paths; source stayed exact.

Private runtime setup preserved an initial uv workspace-resolution refusal in `setup/install.log`, followed by successful explicit `--no-sources` installation in `setup/install-no-sources.log` and successful dependency consistency check. Earlier pip target/user conflicts and refusal to execute the task's own PowerShell script were observed before that setup; no execution policy, registry, global PATH or system Python was modified. A later `python -m pip freeze` probe found pip absent in the uv-created environment; the retained freeze uses the existing uv command instead.

## Reproduction and remaining scope

With the supported existing CI environment installed, run:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
python -m pytest tests/test_review_video_model.py tests/ui/test_review_video.py -q
python -m pytest tests/test_review_video_model.py tests/ui -q
```

The small committed MKV fixtures need no generator or new test dependency. Historical evidence drivers intentionally preserve absolute native receiving paths and exact observation order. Existing full Windows Python and C++/native workflow gates and expected-head/current-main receiving are required separately before integration; local UI results do not replace them. No hardware, real-recording codec matrix, session alignment, installed-application performance or onscreen GPU-video claim is made.
