# Infineon BGT60LTR11AIP — Spike Checklist (M6)

A Doppler motion sensor, not a smaller BGT60TR13C: one TX, one RX, 8-bit ADC, no chirp sweep and therefore **no range information**. Separate SDK surface (`ifxradarsdk.ltr11` / `sdk_ltr11`) and a separate on-disk schema. Recording decisions are in [../RADAR_PIPELINE.md](../RADAR_PIPELINE.md).

Not named in the Milestone 6 plan; recording it is a deliberate scope addition made once the board was on the bench.

Sim stand-in today: none. `sim.radar.*` model FMCW range-Doppler and are the wrong shape for this device.

---

## 1. Product / board / firmware / SDK / license

| Field | Value |
|---|---|
| Target IC | BGT60LTR11AIP (`IFX_BGT60LTR11AIP` = 256) |
| Board | Radar Baseboard MCU7 + LTR11 shield (USB `VID_058B&PID_0251`) |
| Firmware | `Radar Baseboard MCU7 (MCU B)` 2.6.0, `extended_version` = `2.6.0-dirty` |
| RDK / SDK | same install as the TR13C — RDK 3.6.5, `ifxradarsdk` 3.6.4+4b4a6245 |
| Reported RF range | 61.044 – 61.452 GHz |
| Antennas | 1 TX, 1 RX, `max_tx_power` 7 |
| ADC | `adc_resolution_bits` 8. Chirp-oriented fields report 0 (`max_num_samples_per_chirp`, ADC rate limits) and the filter lists are empty — this device has no chirp concept |
| Host / toolchain | Windows 11, Python 3.12.2 |

The firmware string differs from the TR13C board's (2.9.0), confirming these are two independent baseboards rather than one baseboard with swapped shields.

## 2. Discovery and stable identity

| Field | Value |
|---|---|
| Enumeration | `DeviceLtr11.get_list()`; the C SDK filters the board list on `sensor_type == IFX_BGT60LTR11AIP` |
| Stable identity | `00313853-314c-4c35-3039-303034303430` — use as `stable_device_key` |
| Concurrent boards observed | 2 (this board plus the TR13C, simultaneously enumerated) |

**Both boards present the same USB VID/PID (`058B:0251`) and the same `Radar Baseboard MCU7` firmware description.** USB identifiers cannot tell them apart. Only the SDK UUID and reported sensor type distinguish the boards, so discovery must open through the SDK rather than infer identity from the USB tree.

COM port numbers are not identity and were observed to swap: the TR13C appeared as COM5, then COM4 after a replug, with the LTR11 subsequently taking COM5.

### Enumeration hazard: charge-only cables

The board powers up and blinks on a charge-only USB cable while never completing enumeration — no COM port, nothing in `DeviceLtr11.get_list()`, and an intermittent `Unknown USB Device (Device Descriptor Request Failed)` on the hub port. Blinking LEDs are not evidence of a working data link. A data-capable cable resolved it immediately.

Worth surfacing in preflight: "board expected but not enumerated" should hint at the cable, because the failure looks like a dead board.

## 3. Threading / callback model

| Field | Value |
|---|---|
| Callback vs poll | Poll — `get_next_frame()`, mirroring the FMCW device |
| Explicit start/stop | `start_acquisition()` / `stop_acquisition()` present as separate calls |
| Recommended thread model | one acquisition thread per board, same as FMCW; never block it on UI or disk |

## 4. Timestamps

| Field | Value |
|---|---|
| Device-native timestamp | **TBD** — not yet exercised |
| Expected clock domain | host QPC at frame return, as with the TR13C |
| Drift vs QPC | **TBD** |

## 5. Start / stop / arm

| Field | Value |
|---|---|
| Sequence | `set_config(cfg)` → `start_acquisition()` → loop `get_next_frame()` → `stop_acquisition()` |
| Config validation | `check_config()` and `get_limits()` exist — validate before applying rather than trial-and-error |
| First-sample latency | **TBD** |

### Default configuration reported by the device

```text
mode: 0                       rf_frequency_Hz: 61044000000
num_of_samples: 256           detector_threshold: 80
prt: 1                        pulse_width: 0
tx_power_level: 7             rx_if_gain: 8
aprt_factor: 4                hold_time: 8
disable_internal_detector: False
```

`disable_internal_detector` is the field that matters most for this project. The board carries an on-chip detector that produces a motion decision rather than samples. Capturing the decision instead of the signal would be recording a derived product, so the worker sets this true and records samples. Confirm on hardware that doing so does not change the sample path.

## 6. Disconnect / reconnect

| Field | Value |
|---|---|
| Disconnect signals | **TBD** |
| Reconnect path | **TBD** |
| Frame numbering across gap | **TBD** |

## 7. Sustained rate and payload

| Field | Value |
|---|---|
| Frame rate | **~11 Hz measured** (55 frames / 5 s soak, defaults, `disable_internal_detector=true`, host QPC stamp) |
| Nominal frame rate | **~7.8 Hz** from SDK defaults (`prt`=500 µs × 256 samples ≈ 128 ms/frame) — measured rate exceeds this; host scheduling and SDK batching may deliver faster |
| Payload size | **2048 B/frame** recorded — 256 complex float32 samples (`complex_float32_le`, interleaved I,Q) |
| Sampling frequency | queryable via `get_sampling_frequency()` |
| Raw-frame API below `get_next_frame` | **None** — `ifx_ltr11_get_next_frame_timeout` returns `ifx_Vector_C_t*` complex samples directly |

## 8. Hardware sync (real vs marketing)

| Field | Value |
|---|---|
| Modes advertised | none found in the SDK headers |
| Modes exercised | **None** |
| Evidence | **None** |

A GPIO/pins interface exists internally (`RemotePinsLtr11`), but it is not exposed as a synchronization API and must not be described as one without lab evidence.

**Decision rule:** no synchronization claim until this section carries measurements.

---

## Open question specific to this board

Both boards transmit near 61 GHz — the LTR11's entire tuning range sits inside the TR13C's 58–63.5 GHz span. Simultaneous operation may cause mutual interference. This is the multi-radar validation Milestone 6 requires, and both boards are now available to run it.
