# Testing and validation

| Level | Requirement |
|-------|-------------|
| Unit | Formula/extractor on synthetic data |
| Integration | mini_session / generated MCAP |
| Protocol | Hello + Identify via stub or Python SDK |
| Hardware | Tag features `hardware_validated` only after bench parity |

Until hardware validation, mark analysis features `provisional: true` in the
YAML manifest. Never claim calibrated units from sim.

Vendor spike checklist: [VENDOR_SPIKE.md](../design/VENDOR_SPIKE.md).
