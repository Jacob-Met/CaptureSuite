# Xsens — Spike Checklist (M7)

Exact Xsens family / receiver / sensor models are TBD until inventory at the lab. Families are not assumed interchangeable.

Sim stand-in today: `sim.imu.upper` with `ORIENTATION` preview already in the UI. Pairing workflow and logical slots are TBD on hardware. Sim record writes `imu.frame/1` (multi-sensor `ImuFrame`) into MCAP — vendor worker still blocked on this spike.

Do **not** integrate the Xsens SDK into CaptureSuite during this spike. Use a standalone probe under `tools/vendor_spike/`.

---

## 1. Product / board / firmware / SDK / license

| Field | Value |
|---|---|
| Exact family (Awinda / DOT / Link / …) | TBD |
| Receiver / base (if any) | TBD |
| Sensor model(s) | TBD |
| Sensor count intended | TBD |
| Firmware versions | TBD |
| SDK version installed for spike | TBD |
| License / redistributable terms | TBD |

## 2. Discovery and stable identity

| Field | Value |
|---|---|
| How systems and sensors are discovered | TBD |
| Stable identity fields | TBD |
| Pairing procedure (first-class for V1) | TBD |
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
| Clock domain / counters | TBD |
| Drift vs QPC (rough) | TBD |
| Sample vs packet timing | TBD |

## 5. Start / stop / arm

| Field | Value |
|---|---|
| Arm / start / stop sequence | TBD |
| First-sample latency | TBD |
| Update rate / config apply timing | TBD |
| Calibration / heading reset interaction | TBD |

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
| Max sustained update rate observed | TBD |
| Payload / channel set observed | TBD |
| Orientation + inertial fields available | TBD |
| Drop behavior under load | TBD |

## 8. Hardware sync (real vs marketing)

| Field | Value |
|---|---|
| Vendor sync / trigger modes advertised | TBD |
| Modes actually exercised | TBD |
| Evidence | TBD |

Pairing and slot assignment stay lab-validated; do not hard-code a family-specific layout into core session code.
