# Operator quick start

## Prerequisites

- Windows 10 21H2+ x64
- Built `capture_daemon.exe` (see README)
- Python 3.12 for the desktop UI

## Demo (sim only)

```powershell
.\tools\run-demo.ps1
```

Or manually:

1. Start `capture_daemon.exe`
2. From `desktop/`: `python -m capture_desktop`
3. Status bar shows **Connected · instance …**
4. **Create Session** → select sim sources → **Rehearse** or **Start Selected**

## Why are buttons greyed out?

| State | Enabled actions |
|-------|-----------------|
| Not connected | Almost none (Logs only) |
| Connected, idle | Create/Open/Select/Preflight/Rehearse/Start |
| Rehearsing or recording | Checkpoint / Annotation / Sync |
| Recording | Stop |

If the status bar says the daemon was not found, start `capture_daemon.exe` and
relaunch the desktop (it reads `%LOCALAPPDATA%\CaptureSuite\instance.json` at
startup).

## Worker stderr

Workers spawn with `CREATE_NO_WINDOW`. Set `CAPTURE_WORKER_STDERR_LOG` to a file
path to capture stderr.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Daemon not found | Is `capture_daemon` running? `instance.json` present? |
| No hardware sources | Plugin enabled? SDK env set? See Setup → plugins |
| LNK1168 on build | Stop daemon/workers before linking |
| Camera worker missing | Use local CMake preset with GStreamer |
