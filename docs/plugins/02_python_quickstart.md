# Python plugin quickstart

1. Subclass `capture_worker.Worker`.
2. Implement `discover()`, optionally `config_schema` / `start` / `stop`.
3. Ship `plugin.json` + a `.cmd` launcher that runs
   `python -m capture_worker run your_mod:YourWorker`.

See `plugins/example_sine_py/` for a complete sine-wave demo that emits
`generic.numeric_batch/1` and live trace previews.

```powershell
$env:PYTHONPATH = "libs/python/capture_worker;libs/python/capture_protocol;plugins/example_sine_py"
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -c "from example_sine import SineWorker; print(SineWorker().discover())"
```

Drop the folder under `%LOCALAPPDATA%\CaptureSuite\plugins\` or the repo
`plugins/` tree and restart the daemon.
