@echo off
setlocal
REM Launcher for the example.sine Python worker.
REM Daemon spawn: run_worker.cmd --pipe <name> --worker-id <id> --plugin example.sine
REM Prefer a .cmd (or pythonw) path in plugin.json; do not rely on a bare "python" on PATH.

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%..\.."
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"

set "PYTHONPATH=%SCRIPT_DIR%;%REPO_ROOT%\libs\python\capture_worker;%REPO_ROOT%\libs\python\capture_protocol;%PYTHONPATH%"

"%PY%" -m capture_worker run example_sine:SineWorker %*
exit /b %ERRORLEVEL%
