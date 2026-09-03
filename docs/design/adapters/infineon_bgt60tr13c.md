# Infineon BGT60TR13C — Spike Checklist (M6)

Primary radar target is **BGT60TR13C**. It is not interchangeable with BGT60LTR11AIP (different product, API surface, and bring-up path — see [infineon_bgt60ltr11aip.md](infineon_bgt60ltr11aip.md)). Opening the device needs the Infineon Radar Development Kit (RDK), not a webcam-style Media Foundation / UVC open.

Recording decisions derived from these measurements are pinned in [../RADAR_PIPELINE.md](../RADAR_PIPELINE.md).

Sim stand-ins today: `sim.radar.1` / `sim.radar.2` with `MATRIX_2D` preview. No multi-radar sync claim until validated on real boards (see §8 and [VENDOR_SPIKE.md](../VENDOR_SPIKE.md)).

Standalone probe: `tools/vendor_spike/spike_infineon_bgt60tr13c.py`. Lab notes: [notes/infineon_bgt60tr13c_2026-08-08.md](notes/infineon_bgt60tr13c_2026-08-08.md).

---

## 1. Product / board / firmware / SDK / license

| Field | Value |
|---|---|
| Target IC | BGT60TR13C (`RadarSensor.BGT60TR13C` = 0) |
| Eval / development board | Radar Baseboard MCU7 + Shield BGT60TR13C (USB `VID_058B&PID_0251`; COM number is not stable, see §2) |
| Board revision | TBD (silkscreen not recorded this session) |
| Firmware | `Radar Baseboard MCU7 (MCU B)` 2.9.0 via `get_firmware_information()` |
| Sensor capabilities | 58 – 63.5 GHz, 1 TX / 3 RX, `max_tx_power` 31, 12-bit ADC, up to 4095 samples/chirp, ADC 78.2 kHz – 4 MHz, `lp_cutoff_list` [500 kHz], `hp_cutoff_list` [20/45/70/80 kHz], 14 discrete `if_gain` steps |
| RDK version | 3.6.5 installed under `%USERPROFILE%\Infineon\Tools\Radar-Development-Kit\3.6.5` |
| Radar SDK / wheel | `ifxradarsdk` 3.6.4+4b4a6245 (`python_wheels\ifxradarsdk-*-win_amd64.whl` from `radar_sdk.zip`) |
| License / redistributable terms | Infineon RDK license; SDK not checked into CaptureSuite — install on the lab machine only |
| Host OS / toolchain used for spike | Windows 11, Python 3.12.2 |

## 2. Discovery and stable identity

| Field | Value |
|---|---|
| How devices are enumerated | `DeviceFmcw()` opens the first attached FMCW board (context manager). USB PnP: Infineon `VID_058B` / `PID_0251` CDC serial |
| Stable identity fields | `device.get_board_uuid()` → `00323353-4834-4a57-3230-303038303139` on this board; use as `stable_device_key` |
| What changes across reboot / port move | UUID stable across replug; COM number is **not** identity — this board was observed as COM5, then COM4 after a replug |
| Concurrent board count observed | 2 (with the LTR11 board attached simultaneously) |

USB identifiers cannot distinguish Infineon boards. The LTR11 baseboard presents the identical `VID_058B&PID_0251` and the same `Radar Baseboard MCU7` firmware description, so discovery must resolve identity through the SDK (UUID plus sensor type), never from the USB tree or COM number.

A charge-only USB cable leaves the board powered and blinking but never enumerated — no COM port, no SDK visibility, sometimes a transient `Device Descriptor Request Failed` on the hub port. Preflight should hint at the cable when a known board fails to appear.

## 3. Threading / callback model

| Field | Value |
|---|---|
| Callback vs poll | **Poll** — blocking `device.get_next_frame()` on the caller thread |
| Who owns sample buffers | SDK returns numpy arrays to the caller; treat as owned after return (copy before next pull if retaining) |
| May the callback block? | N/A (no callback API used) |
| Recommended worker thread model (notes only) | One acquisition thread per board calling `get_next_frame`; never block that thread on UI/disk; latest-wins preview queue |

## 4. Timestamps

| Field | Value |
|---|---|
| Format / units | Host stamp only in spike: `time.perf_counter_ns()` at frame pull. Device-native frame timestamp API not confirmed in this spike |
| Clock domain | Host QPC via `perf_counter_ns` |
| Drift vs QPC (rough) | Frame interval p50 ≈ 45.9 ms vs configured 50 ms FRT (close); p95 ≈ 61 ms |
| First-sample vs arm relationship | First frame ~123 ms after `set_acquisition_sequence` |

## 5. Start / stop / arm

| Field | Value |
|---|---|
| Arm / start / stop sequence | `create_simple_sequence(config)` → `set_acquisition_sequence(seq)` → loop `get_next_frame()`; leave `with DeviceFmcw()` to tear down |
| First-sample latency | ~123 ms (8 s soak, 20 Hz config) |
| Chirp / frame config applied when | On `set_acquisition_sequence` |
| Tear-down / flush behavior | Context-manager exit closes device; Fusion GUI must not hold the handle |

## 6. Disconnect / reconnect

| Field | Value |
|---|---|
| Disconnect signals / error codes | Documented in `DeviceFmcw.h`, not yet exercised: `IFX_ERROR_COMMUNICATION_ERROR` (board unplugged mid-fetch), `IFX_ERROR_FIFO_OVERFLOW`, `IFX_ERROR_TIMEOUT` |
| Reconnect path | Expected: new `DeviceFmcw()` after USB re-enumerate; TBD |
| Sequence / frame numbering across gap | Host sequence only in spike; SDK frame counter TBD |
| Explicit gap evidence from spike | None yet |

`IFX_ERROR_FIFO_OVERFLOW` means the board could not drain the sensor FIFO fast enough **and the sensor state machine stopped**. Frames are not silently skipped, so the worker can report an honest gap rather than infer one. Mapping of these codes to gap types is in [../RADAR_PIPELINE.md](../RADAR_PIPELINE.md).

## 7. Sustained rate and payload

| Field | Value |
|---|---|
| Max sustained frame rate observed | **~19.9 Hz** at `frame_repetition_time_s=50 ms`, 32 chirps × 128 samples × 3 RX |
| Payload size(s) observed | Deinterleaved `float32` cube ≈ **49 152 bytes/frame** (`float32` 3×32×128) before range-Doppler |
| USB / host bottlenecks noted | None at 20 Hz on this host |
| Drop behavior under load | Not stressed; Fusion GUI must be closed or open fails |

Spike metrics from SDK: max_range ≈ 6.40 m, range_resolution ≈ 0.10 m, max_speed ≈ 2.47 m/s.

Fan-in-FOV note: range-profile peak stayed on bin 0 with energy CV ≈ 0.006 — DC/leakage dominates the naive FFT magnitude; presence/motion will need MTI / range-Doppler (see SDK `range_doppler_map.py` helpers), not raw energy.

### Two fidelity levels, and which one is recorded

The C SDK exposes a level below the float cube that the Python wheel does not:

| API | Output | Bytes per frame at 3 RX / 32 chirps / 128 samples |
|---|---|---|
| `ifx_fmcw_get_next_frame` | `ifx_Fmcw_Frame_t` — deinterleaved real `float32` cubes | 49152 |
| `ifx_fmcw_get_next_raw_frame` | `ifx_Fmcw_Raw_Frame_t` — interleaved `uint16` in chip order | 24576 |

The cube is the raw frame after `ifx_fmcw_convert_raw_data_to_float_array` (12-bit integer scaled to float) and `ifx_fmcw_deinterleave_raw_frame` (chip order to Rx × chirp × sample). Both are published, deterministic, and reproducible offline; neither filters nor discards. Recording the raw frame is therefore strictly rawer *and* half the bytes.

`ifxradarsdk` exposes only `get_next_frame`, so the raw path requires the C SDK — which is why the worker is C++. Samples are real-valued IF, not complex I/Q.

### Frame delivery is sliced, not frame-aligned

`DeviceFmcw.h` states the sensor transfers time-domain data in slices unrelated to frame boundaries, so one slice may carry several frames and consecutive `get_next_frame` calls can return immediately. Host arrival time is therefore a loose proxy for acquisition time — consistent with the p50 45.9 ms / p95 61 ms spread measured against a 50 ms configured period.

## 8. Hardware sync (real vs marketing)

| Field | Value |
|---|---|
| Vendor “sync” / trigger modes advertised | RDK docs mention multi-device use cases; not exercised |
| Modes actually exercised on this board + RDK | **None** (no hardware trigger/sync API used) |
| Concurrent TX with LTR11 (throughput soak) | **Exercised** 2026-08-08 — see below |
| Evidence of hardware frame sync | **None** |

### Concurrent soak with BGT60LTR11AIP (2026-08-08)

Script: `tools/vendor_spike/spike_dual_radar_interference.py` (report under `tools/vendor_spike/out/`).

| Phase | TR13C Hz | LTR11 Hz | TR13C energy CV | Errors |
|---|---|---|---|---|
| solo TR13C | 20.01 | — | 0.0048 | 0 |
| solo LTR11 | — | 7.82 | — | 0 |
| concurrent 15 s | 20.01 | 7.82 | 0.0032 | 0 |
| solo TR13C after | 20.01 | — | 0.0034 | 0 |

**Throughput verdict:** no rate drop, no FIFO/communication errors, no energy-CV spike at this config. **Not** a hardware-sync claim; both boards still use host-arrival timestamps only.

**Decision rule:** do not document or expose a multi-radar synchronization mode in CaptureSuite until a real trigger/GPIO path has lab evidence. Software-coordinated start is not hardware sync.

---

## Install quick reference (this workstation)

```text
RDK:   %USERPROFILE%\Infineon\Tools\Radar-Development-Kit\3.6.5
SDK:   %USERPROFILE%\Infineon\Tools\radar_sdk_3.6.5\radar_sdk   (extracted from assets\software\radar_sdk.zip)
Wheel: ...\radar_sdk\python_wheels\ifxradarsdk-3.6.4+4b4a6245-py3-none-win_amd64.whl
```

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m pip install `
  "$env:USERPROFILE\Infineon\Tools\radar_sdk_3.6.5\radar_sdk\python_wheels\ifxradarsdk-3.6.4+4b4a6245-py3-none-win_amd64.whl"

& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" `
  tools/vendor_spike/spike_infineon_bgt60tr13c.py --seconds 8 --write-notes
```
