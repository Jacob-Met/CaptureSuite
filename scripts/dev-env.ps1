# Load Visual Studio Build Tools + vcpkg into the current PowerShell session.
# Usage (from repo root):
#   . .\scripts\dev-env.ps1
#   cmake --preset windows-debug-local
#   cmake --build --preset windows-debug-local

param([switch]$Force)

$ErrorActionPreference = "Stop"

# Re-sourcing into an already-initialised session makes VsDevCmd emit a reduced
# environment, and importing that overwrites PATH with one that has lost
# System32. Bail out instead; the session is already usable.
if ($env:CAPTURE_DEV_ENV_LOADED -eq "1" -and -not $Force) {
    Write-Host "Dev environment already loaded in this session (pass -Force to reload)."
    return
}

$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path $vswhere)) {
    throw "vswhere.exe not found. Install Visual Studio Build Tools with the C++ workload."
}

$vsPath = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vsPath) {
    throw "MSVC C++ tools not found. Install the 'Desktop development with C++' workload."
}

$vsdev = Join-Path $vsPath "Common7\Tools\VsDevCmd.bat"
if (-not (Test-Path $vsdev)) {
    throw "VsDevCmd.bat missing under $vsPath"
}

$vcpkgRoot = Join-Path $env:USERPROFILE "vcpkg"
if (-not (Test-Path (Join-Path $vcpkgRoot "vcpkg.exe"))) {
    throw "vcpkg not found at $vcpkgRoot. Clone https://github.com/microsoft/vcpkg and run bootstrap-vcpkg.bat."
}

# Import VsDevCmd environment into this PowerShell process.
$envBlock = cmd /c "`"$vsdev`" -arch=amd64 -host_arch=amd64 >NUL && set"
foreach ($line in $envBlock) {
    if ($line -match "^(.*?)=(.*)$") {
        Set-Item -Path "Env:$($matches[1])" -Value $matches[2]
    }
}

$env:VCPKG_ROOT = $vcpkgRoot
$env:CAPTURE_DEV_ENV_LOADED = "1"
Write-Host "MSVC ready from: $vsPath"
Write-Host "VCPKG_ROOT=$env:VCPKG_ROOT"
Write-Host "cl.exe: $((Get-Command cl).Source)"
