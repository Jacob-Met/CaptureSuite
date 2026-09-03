# C++ worker template

`workers/stub/` is an Apache-2.0 minimal worker that completes Hello + Identify.
Copy it, add Start/Stop + your vendor SDK, and register with a `plugin.json`.

CLI contract (required):

```text
capture_worker_mydevice.exe --pipe <name> --worker-id <id> --plugin <plugin_id>
```

See [WORKER_HOST.md](../design/WORKER_HOST.md) and
[ACQUISITION_PLUGIN_CONTRACT.md](../design/research/ACQUISITION_PLUGIN_CONTRACT.md).
