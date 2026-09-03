# Delsys Trigno — Spike Checklist (M8)

Official Delsys API path for V1 (Python worker planned later). Credentials load from Windows Credential Manager via DPAPI per [OPERATIONS.md](../OPERATIONS.md). **No secrets in this repo**, settings files, logs, or diagnostic bundles.

Sim stand-in today: `sim.emg.main` with `TRACE_BLOCK` preview already in the UI. Sim record writes `emg.batch/1` (multi-channel `EmgBatch`) into MCAP — vendor worker still blocked on this spike.

Do **not** integrate the Delsys API into CaptureSuite during this spike. Use a standalone probe under `tools/vendor_spike/`.

---

## 1. Product / board / firmware / SDK / license

| Field | Value |
|---|---|
| Trigno receiver / base model | TBD |
| Sensor model(s) | TBD |
| Sensor count intended | TBD |
| Firmware versions | TBD |
| Delsys API version | TBD |
| License / key deployment constraints | TBD |
| Vendor DLL / runtime install path | TBD |

## 2. Discovery and stable identity

| Field | Value |
|---|---|
| How the base is detected | TBD |
| Stable identity fields (serials, …) | TBD |
| Pairing / scan / sensor allocation | TBD |
| Logical slots vs physical IDs | TBD |

## 3. Threading / callback model

| Field | Value |
|---|---|
| Callback vs poll | TBD |
| Who owns sample buffers | TBD |
| May the callback block? | TBD |
| Recommended worker thread model (notes only) | TBD |

## 4. Timestamps

| Field | Value |
|---|---|
| Format / units | TBD |
| Clock domain | TBD |
| Drift vs QPC (rough) | TBD |
| Batch vs sample timing | TBD |

## 5. Start / stop / arm

| Field | Value |
|---|---|
| Arm / start / stop sequence | TBD |
| First-sample latency | TBD |
| Mode / channel config apply timing | TBD |
| Trigger support (if any) | TBD |

## 6. Disconnect / reconnect

| Field | Value |
|---|---|
| Disconnect signals / error codes | TBD |
| Reconnect path | TBD |
| Sequence numbering across gap | TBD |
| Explicit gap evidence from spike | TBD |

## 7. Sustained rate and payload

| Field | Value |
|---|---|
| Expected / observed EMG sample rates | TBD |
| Channel set / auxiliary channels | TBD |
| IMU channels in intended modes | TBD |
| Drop behavior under load | TBD |

## 8. Hardware sync (real vs marketing)

| Field | Value |
|---|---|
| Vendor sync / trigger modes advertised | TBD |
| Modes actually exercised | TBD |
| Evidence | TBD |

Credential handling for the eventual worker: read from Credential Manager only; never commit keys or paste them into adapter notes.
