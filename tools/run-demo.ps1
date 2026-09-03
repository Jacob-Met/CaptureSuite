# SPDX-License-Identifier: GPL-3.0-only
<#
.SYNOPSIS
  Start capture_daemon (sim) and the PySide6 desktop for a local demo.
#>
param(
  [string]$BuildDir = "",
  [switch]$NoDesktop
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not $BuildDir) {
  $BuildDir = Join-Path $Root "build\windows-release"
}
$Daemon = Join-Path $BuildDir "daemon\capture_daemon.exe"
if (-not (Test-Path $Daemon)) {
  Write-Error "capture_daemon.exe not found at $Daemon. Build first: cmake --build build/windows-release --target capture_daemon"
}

Get-Process capture_daemon -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Process -FilePath $Daemon -WorkingDirectory (Split-Path $Daemon)
Start-Sleep -Seconds 1
if (-not (Test-Path "$env:LOCALAPPDATA\CaptureSuite\instance.json")) {
  Write-Warning "instance.json missing — daemon may have failed to start"
} else {
  Write-Host "Daemon running. instance.json OK."
}

if ($NoDesktop) { return }

$Py = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }
$Desktop = Join-Path $Root "desktop"
Write-Host "Launching desktop from $Desktop"
Start-Process -FilePath $Py -ArgumentList "-m","capture_desktop" -WorkingDirectory $Desktop
