# Radar worker (Infineon FMCW + LTR11)

Out-of-process worker for Milestone 6. FMCW boards record raw interleaved
`uint16` frames via `ifx_fmcw_get_next_raw_frame` (`radar.frame/1`). LTR11
boards record complex float IQ (`radar.doppler/1`). Preview is derived and
droppable (latest-wins); config `preview_view` selects Fusion-style views.

Design: [`docs/design/RADAR_PIPELINE.md`](../../docs/design/RADAR_PIPELINE.md).

## Build

Requires the Infineon Radar SDK (RDK 3.6.x) on the machine. CMake locates it
via `IFX_RADAR_SDK_ROOT` or `%USERPROFILE%/Infineon/Tools/radar_sdk_3.6.5/radar_sdk`.

```powershell
. .\scripts\dev-env.ps1
cmake --preset windows-release-local   # CAPTURE_ENABLE_RADAR_WORKER=ON in local-env
cmake --build build/windows-release --target capture_worker_radar
```

The worker target is gated by `CAPTURE_ENABLE_RADAR_WORKER`. The local preset
sets it `ON` and exports `IFX_RADAR_SDK_ROOT`.

POST_BUILD copies `capture_worker_radar.exe` and all SDK DLLs from
`libs/win32_x64` next to `capture_daemon` under `workers/radar/`.

## Run (with daemon)

| Variable | Purpose |
|---|---|
| `CAPTURE_USE_RADAR_WORKER=1` | Force out-of-process radar (auto when exe present) |
| `CAPTURE_USE_RADAR_WORKER=0` | Disable radar worker bridge |
| `CAPTURE_RADAR_WORKER_EXE` | Override path to `capture_worker_radar.exe` |
| `IFX_RADAR_SDK_ROOT` | SDK root (daemon prepends `libs/win32_x64` to worker PATH) |
| `CAPTURE_IFX_RADAR_SDK_ROOT` | Alternate SDK root env name |
| `CAPTURE_WORKER_STDERR_LOG` | Capture worker stderr (workers use `CREATE_NO_WINDOW`) |

Plugin id: `radar.ifx`. Config schema revision: `radar.ifx/3`.

| Board | `preview_view` values |
|---|---|
| FMCW (TR13C) | `range_doppler` (default), `range_doppler_hd`, `range_spectrum`, `range_spectrogram`, `time_domain` |
| LTR11 | `motion_trace` (default), `doppler_spectrogram` |

FMCW also exposes restart-required chirp geometry (`num_chirps`, `num_samples`, start/end frequency, sample rate, RX/TX masks, TX power, IF gain, LP/HP cutoffs, frame/chirp repetition times). Defaults match the vendor spike (1.5 GHz / 32×128 / 20 Hz). Geometry changes while capturing return `RESTART_REQUIRED`.

Close Infineon Fusion GUI before connect — it holds the USB device exclusively.
