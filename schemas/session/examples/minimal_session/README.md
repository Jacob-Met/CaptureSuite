# Minimal session example

Generated at runtime by Milestone 3 tests (`test_session_package`, kill tests).

A package looks like:

```text
example.mmsession/
  manifest.json
  journal.sqlite
  integrity.json
  events/
  sources/<source_id>/streams/<stream_id>/segments/000000.mcap
```

Create one locally:

```powershell
$env:CAPTURE_SESSION_PARENT = "$env:TEMP\capturesuite_example"
.\build\windows-debug\daemon\capture_daemon.exe --self-test
```
