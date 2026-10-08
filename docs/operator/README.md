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

## Open saved analysis

In **Analysis**, use **Browse…** or **Use open session** to select a `.mmsession`
package. **Saved analysis** lists its retained completed and failed jobs, with
their recorded status. Choose a job and click **Open saved result** to load its
existing figures and output inventory into the gallery and job inspector.
Selecting a different item in the list keeps the current result open until you
explicitly open the selected one.

**Result details…** opens read-only **Parameters**, **Log** and **Manifest** tabs
for the currently displayed result. Failed jobs can be useful here: their saved
log explains the failure even when no figures were produced. Missing parameters
or logs are identified in their respective tabs. Long logs show their final
256 KiB, with the truncation stated; the JSON viewer accepts files up to 4 MiB.

Use **Refresh** to discover jobs written since the package was selected. Opening,
refreshing and reading details do not rerun analysis or change any package files.
Changing packages clears the previous package's result and details window. If an
earlier job completes after a package change, its result stays with the original
package; select that package to open it.

An **unavailable** row includes the reason it cannot be opened, such as a missing
manifest, unsupported job schema or mismatched session identity. A package copy
can retain the original absolute path in its manifest; the viewer reads the job
directory inside the package you selected. It does not follow job-directory
links into another package.

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
