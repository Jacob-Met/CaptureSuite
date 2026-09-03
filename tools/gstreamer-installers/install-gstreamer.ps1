# Installs or extracts GStreamer 1.24.13 MSVC x86_64 for CaptureSuite M5.
# Installers must already be in this directory (from gstreamer.freedesktop.org).
#
# Default: msiexec /a extract into repo third_party/gstreamer (no admin).
# Pass -SystemInstall from an elevated shell for a machine-wide MSI install.

param(
  [switch]$SystemInstall
)

$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$repo = (Resolve-Path (Join-Path $here "..\..")).Path
$runtime = Join-Path $here "gstreamer-1.0-msvc-x86_64-1.24.13.msi"
$devel = Join-Path $here "gstreamer-1.0-devel-msvc-x86_64-1.24.13.msi"

function Test-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $p = New-Object Security.Principal.WindowsPrincipal($id)
  return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

foreach ($msi in @($runtime, $devel)) {
  if (-not (Test-Path $msi)) {
    Write-Error "Missing installer: $msi"
  }
}

if ($SystemInstall) {
  if (-not (Test-Admin)) {
    Write-Error "SystemInstall requires an elevated PowerShell (Administrator)."
  }
  Write-Host "Installing runtime (ADDLOCAL=ALL)..."
  $r1 = Start-Process msiexec.exe -ArgumentList @(
    "/i", $runtime, "/qn", "/norestart", "ADDLOCAL=ALL"
  ) -Wait -PassThru
  if ($r1.ExitCode -ne 0) {
    Write-Error "Runtime install failed with exit $($r1.ExitCode)"
  }
  Write-Host "Installing devel..."
  $r2 = Start-Process msiexec.exe -ArgumentList @(
    "/i", $devel, "/qn", "/norestart", "ADDLOCAL=ALL"
  ) -Wait -PassThru
  if ($r2.ExitCode -ne 0) {
    Write-Error "Devel install failed with exit $($r2.ExitCode)"
  }
  $root = [Environment]::GetEnvironmentVariable(
    "GSTREAMER_1_0_ROOT_MSVC_X86_64", "Machine")
  if (-not $root) {
    $guess = "C:\Program Files\gstreamer\1.0\msvc_x86_64"
    if (Test-Path $guess) { $root = $guess }
  }
} else {
  $extractRoot = Join-Path $repo "third_party\gstreamer"
  New-Item -ItemType Directory -Force -Path $extractRoot | Out-Null
  Write-Host "Extracting runtime to $extractRoot ..."
  $r1 = Start-Process msiexec.exe -ArgumentList @(
    "/a", $runtime, "/qn", "TARGETDIR=$extractRoot"
  ) -Wait -PassThru
  if ($r1.ExitCode -ne 0) {
    Write-Error "Runtime extract failed with exit $($r1.ExitCode)"
  }
  Write-Host "Extracting devel..."
  $r2 = Start-Process msiexec.exe -ArgumentList @(
    "/a", $devel, "/qn", "TARGETDIR=$extractRoot"
  ) -Wait -PassThru
  if ($r2.ExitCode -ne 0) {
    Write-Error "Devel extract failed with exit $($r2.ExitCode)"
  }
  $root = Join-Path $extractRoot "gstreamer\1.0\msvc_x86_64"
  if (-not (Test-Path (Join-Path $root "bin\gst-launch-1.0.exe"))) {
    Write-Error "Extract finished but gst-launch-1.0.exe was not found under $root"
  }
  [Environment]::SetEnvironmentVariable(
    "GSTREAMER_1_0_ROOT_MSVC_X86_64", $root, "User")
}

Write-Host "Done."
Write-Host "GSTREAMER_1_0_ROOT_MSVC_X86_64=$root"
Write-Host "Open a new terminal so CMake picks up the env var (or set it in the current session)."
