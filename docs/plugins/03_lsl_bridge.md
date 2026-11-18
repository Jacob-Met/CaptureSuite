# LSL bridge

The `lsl.bridge` plugin records any Lab Streaming Layer outlet without writing
vendor-specific code.

```powershell
pip install pylsl
# ensure plugins/lsl_bridge is discoverable, restart daemon
```

Details: [plugins/lsl_bridge/README.md](../../plugins/lsl_bridge/README.md).

Version 0.1.3 stores the outlet's original LSL timestamps in integer nanoseconds.
The SDK records the session arrival anchor independently and retains the original samples.
