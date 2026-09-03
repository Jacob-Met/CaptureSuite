# Prompt: vendor spike

```text
Run a CaptureSuite vendor spike for:

- Vendor / product / board: [e.g. OpenBCI Cyton, AMTI force plate, …]
- SDK language / package: [Python wheel / C++ lib / serial protocol]
- Goal: fill docs/design/adapters/<vendor_slug>.md from VENDOR_SPIKE.md §§1–8

Constraints:
- Standalone console probe only — do NOT wire into capture_daemon or workers yet
- Prefer tools/vendor_spike/ style scripts; print timestamped samples + identity fields
- Record: discovery, stable IDs, threading model, timestamp domain, start/stop latency,
  disconnect behavior, sustained rate/payload, whether "hardware sync" is real
- Keep secrets out of the repo (Credential Manager / env only)
- If useful, write dated notes under docs/design/adapters/notes/

Deliverables:
1. docs/design/adapters/<vendor_slug>.md (all 8 sections answered or explicitly unknown)
2. tools/vendor_spike/spike_<vendor_slug>.py (or .cpp) runnable on this machine
3. Short summary of what would block a CaptureSuite plugin next

Follow docs/design/VENDOR_SPIKE.md and docs/design/adapters/README.md.
```
