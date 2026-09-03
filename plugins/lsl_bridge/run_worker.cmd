@echo off
REM SPDX-License-Identifier: Apache-2.0
setlocal
set "ROOT=%~dp0..\.."
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"
set "PYTHONPATH=%ROOT%\libs\python\capture_worker;%ROOT%\libs\python\capture_protocol;%ROOT%\plugins\lsl_bridge;%PYTHONPATH%"
"%PY%" -m capture_worker run lsl_bridge:LslBridgeWorker %*
