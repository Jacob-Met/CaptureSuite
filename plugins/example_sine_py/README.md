# Example sine worker (Python SDK)

Minimal reference plugin for [`libs/python/capture_worker`](../../libs/python/capture_worker/). Emits a 2-channel sine at ~100 Hz as `generic.numeric_batch/1`.

## Manifest

`plugin.json` sets `plugin_id` to `example.sine`, `family` to `numeric`, and `executable` to `run_worker.cmd`.

The daemon launches workers by resolving `executable` relative to the plugin directory and appending `--pipe`, `--worker-id`, and `--plugin` (see [WORKER_HOST.md](../../docs/design/WORKER_HOST.md)). Prefer a `.cmd` launcher or a `pythonw` wrapper rather than assuming `python` is on `PATH`.

## Run manually

```bat
cd plugins\example_sine_py
run_worker.cmd --pipe \\.\pipe\capturesuite.test.worker.sine --worker-id sine-1 --plugin example.sine
```

Or:

```bat
set PYTHONPATH=%CD%;..\..\libs\python\capture_worker;..\..\libs\python\capture_protocol
"%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -m capture_worker run example_sine:SineWorker --pipe ... --worker-id ... --plugin example.sine
```

## Subclass sketch

```python
from capture_worker import Worker

class SineWorker(Worker):
    def discover(self): ...
    def config_schema(self, source_id: str): ...
    def start(self, source_id, start_req): ...
    def stop(self, source_id): ...
    # inside acquisition: self.emit_samples(...); self.emit_preview(...)
```
