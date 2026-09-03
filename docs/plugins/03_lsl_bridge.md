# LSL bridge

The `lsl.bridge` plugin records any Lab Streaming Layer outlet without writing
vendor-specific code.

```powershell
pip install pylsl
# ensure plugins/lsl_bridge is discoverable, restart daemon
```

Details: [plugins/lsl_bridge/README.md](../../plugins/lsl_bridge/README.md).

Timestamps: LSL device time + per-chunk `time_correction()`; CaptureSuite does
not resample.
