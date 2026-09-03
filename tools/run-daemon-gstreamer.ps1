# Launch capture_daemon with GStreamer (+ optional Infineon radar) on PATH.
# Usage: .\tools\run-daemon-gstreamer.ps1 [-FakeCamera] [-NoRadar] [-NoCameraWorker]

param(
    [switch]$FakeCamera,
    [switch]$NoRadar,
    [switch]$NoCameraWorker,
    [string]$GstRoot = $env:GSTREAMER_1_0_ROOT_MSVC_X86_64,
    [string]$IfxRoot = $env:IFX_RADAR_SDK_ROOT
)

$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
if (-not $GstRoot) {
    $GstRoot = Join-Path $repo "third_party\gstreamer\gstreamer\1.0\msvc_x86_64"
}
if (-not (Test-Path $GstRoot)) {
    throw "GStreamer root not found: $GstRoot (set GSTREAMER_1_0_ROOT_MSVC_X86_64)"
}

# Prefer release (local preset); fall back to debug.
$daemon = Join-Path $repo "build\windows-release\daemon\capture_daemon.exe"
if (-not (Test-Path $daemon)) {
    $daemon = Join-Path $repo "build\windows-debug\daemon\capture_daemon.exe"
}
if (-not (Test-Path $daemon)) {
    throw "capture_daemon.exe not found; build the daemon first"
}
$daemonDir = Split-Path $daemon -Parent

$env:GSTREAMER_1_0_ROOT_MSVC_X86_64 = $GstRoot
$pathPrefix = Join-Path $GstRoot 'bin'

$camWorker = Join-Path $daemonDir "workers\camera\capture_worker_camera.exe"
if (-not (Test-Path $camWorker)) {
    $camWorker = Join-Path $daemonDir "..\workers\camera\capture_worker_camera.exe"
}
if (Test-Path $camWorker) {
    $env:CAPTURE_CAMERA_WORKER_EXE = (Resolve-Path $camWorker).Path
}
# Set this explicitly either way: a stale CAPTURE_USE_CAMERA_WORKER=0 left in
# the shell silently downgrades cameras to the timing-only in-process path.
$env:CAPTURE_USE_CAMERA_WORKER = if ($NoCameraWorker) { "0" } else { "1" }
if ($FakeCamera) {
    $env:CAPTURE_CAMERA_FAKE = "1"
    $env:CAPTURE_USE_CAMERA_WORKER = "1"
}

if (-not $IfxRoot) {
    $IfxRoot = Join-Path $env:USERPROFILE "Infineon\Tools\radar_sdk_3.6.5\radar_sdk"
}
$radarWorker = Join-Path $daemonDir "workers\radar\capture_worker_radar.exe"
if (-not (Test-Path $radarWorker)) {
    $radarWorker = Join-Path $daemonDir "..\workers\radar\capture_worker_radar.exe"
}
if ($NoRadar) {
    $env:CAPTURE_USE_RADAR_WORKER = "0"
} elseif (Test-Path $radarWorker) {
    $env:CAPTURE_USE_RADAR_WORKER = "1"
    $env:CAPTURE_RADAR_WORKER_EXE = (Resolve-Path $radarWorker).Path
    if (Test-Path $IfxRoot) {
        $env:IFX_RADAR_SDK_ROOT = $IfxRoot
        $ifxBin = Join-Path $IfxRoot "libs\win32_x64"
        if (Test-Path $ifxBin) {
            $pathPrefix = "$ifxBin;$pathPrefix"
        }
    }
    Write-Host "Radar:     $env:CAPTURE_RADAR_WORKER_EXE"
}

$env:PATH = "$pathPrefix;$env:PATH"
Write-Host "GStreamer: $GstRoot"
Write-Host "Camera:    $env:CAPTURE_CAMERA_WORKER_EXE (worker=$env:CAPTURE_USE_CAMERA_WORKER)"
Write-Host "Daemon:    $daemon"
& $daemon @args
