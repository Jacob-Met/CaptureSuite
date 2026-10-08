# SPDX-License-Identifier: GPL-3.0-only
# Extract an isolated official SDK for the real camera-worker CI build.
# No product installation or machine/user environment changes are performed.
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$SdkDirectory,
  [Parameter(Mandatory = $true)]
  [string]$EvidenceDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $IsWindows) {
  throw "The GStreamer MSVC SDK receiver requires Windows PowerShell 7."
}

function Get-OwnedDirectory([string]$Value) {
  if (-not [IO.Path]::IsPathFullyQualified($Value)) {
    throw "Use an absolute path for an isolated SDK/evidence directory."
  }
  if ($Value.Contains('"') -or $Value.Contains([char]13) -or $Value.Contains([char]10)) {
    throw "Directory names must not contain quote or newline characters."
  }
  $resolved = [IO.Path]::GetFullPath($Value).TrimEnd('\', '/')
  $root = [IO.Path]::GetPathRoot($resolved).TrimEnd('\', '/')
  if ($resolved -eq $root) {
    throw "An SDK/evidence directory must be a new child directory."
  }
  return $resolved
}

function Get-FileReceipt([string]$Path, [string]$Label) {
  $item = Get-Item -LiteralPath $Path
  if ($item.PSIsContainer) {
    throw "Expected a regular SDK file: $Label"
  }
  return [ordered]@{
    path = $Label
    bytes = $item.Length
    sha256 = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
  }
}

$sdkDirectoryPath = Get-OwnedDirectory $SdkDirectory
$evidenceDirectoryPath = Get-OwnedDirectory $EvidenceDirectory
if (Test-Path -LiteralPath $evidenceDirectoryPath) {
  throw "Evidence directory already exists; retain it and choose a fresh directory."
}
New-Item -ItemType Directory -Path $evidenceDirectoryPath -Force | Out-Null
$manifestPath = Join-Path $evidenceDirectoryPath "manifest.json"
$manifest = [ordered]@{
  schema = "capturesuite.camera-sdk.v1"
  accepted = $false
  created_at = [DateTime]::UtcNow.ToString("o")
  gstreamer_version = "1.24.13"
  gstreamer_root = $null
  binary_coverage = "all_sdk_dll_and_exe"
  installers = @()
  extractions = @()
  probe = $null
  files = @()
  failure = $null
}

$packages = @(
  [ordered]@{
    name = "gstreamer-1.0-msvc-x86_64-1.24.13.msi"
    sha256 = "66915d82adda34189703c36a5d2ef145d2e3afb7afc12c66fcf2ea506e2466d2"
  },
  [ordered]@{
    name = "gstreamer-1.0-devel-msvc-x86_64-1.24.13.msi"
    sha256 = "0afb4394c2cba3999c0f5e74f28c2ac5d98f03131140e09246d4dcd60a0a0395"
  }
)
$vendor = "https://gstreamer.freedesktop.org/data/pkg/windows/1.24.13/msvc/"
$savedPath = $env:PATH

try {
  if (Test-Path -LiteralPath $sdkDirectoryPath) {
    throw "SDK directory already exists; no existing installation will be changed."
  }
  $downloadDirectory = Join-Path $sdkDirectoryPath "installers"
  $extractDirectory = Join-Path $sdkDirectoryPath "extracted"
  New-Item -ItemType Directory -Path $downloadDirectory, $extractDirectory -Force | Out-Null

  # Verify both inputs before executing either vendor administrative extraction.
  foreach ($package in $packages) {
    $destination = Join-Path $downloadDirectory $package.name
    $url = $vendor + $package.name
    Write-Host "Downloading the pinned vendor package $($package.name)"
    Invoke-WebRequest -Uri $url -OutFile $destination -TimeoutSec 600 -MaximumRedirection 4
    $receipt = Get-FileReceipt $destination $package.name
    $receipt["name"] = $package.name
    $receipt["url"] = $url
    $receipt["expected_sha256"] = $package.sha256
    $manifest.installers += $receipt
    if ($receipt.sha256 -ne $package.sha256) {
      throw "Vendor SHA-256 mismatch for $($package.name); no MSI will be executed."
    }
  }

  foreach ($package in $packages) {
    $source = Join-Path $downloadDirectory $package.name
    $logName = $package.name + ".extract.log"
    $logPath = Join-Path $evidenceDirectoryPath $logName
    $arguments = '/a "{0}" /qn /norestart TARGETDIR="{1}" /L*v "{2}"' -f $source, $extractDirectory, $logPath
    Write-Host "Extracting $($package.name) into the isolated SDK directory"
    $process = Start-Process -FilePath "msiexec.exe" -ArgumentList $arguments -Wait -PassThru
    $logHash = $null
    if (Test-Path -LiteralPath $logPath) {
      $logHash = (Get-FileHash -LiteralPath $logPath -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    $manifest.extractions += [ordered]@{
      name = $package.name
      exit_code = $process.ExitCode
      log = $logName
      log_sha256 = $logHash
    }
    if ($process.ExitCode -ne 0) {
      throw "Vendor administrative extraction failed: $($package.name), exit $($process.ExitCode)"
    }
  }

  $gstreamerRoot = Join-Path $extractDirectory "gstreamer/1.0/msvc_x86_64"
  $manifest.gstreamer_root = $gstreamerRoot
  $recorded = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
  foreach ($relative in @(
    "include/gstreamer-1.0/gst/gst.h",
    "lib/gstreamer-1.0.lib",
    "lib/gstapp-1.0.lib",
    "lib/gstvideo-1.0.lib",
    "bin/gst-inspect-1.0.exe",
    "bin/gst-launch-1.0.exe"
  )) {
    $manifest.files += Get-FileReceipt (Join-Path $gstreamerRoot $relative) $relative
    [void]$recorded.Add($relative)
  }
  # Cover runtime code, including codec plugins and plugin-scanner helpers.
  # Headers/import libraries above are required inputs, not a whole-SDK inventory.
  $runtimeBinaries = Get-ChildItem -LiteralPath $gstreamerRoot -Recurse -File |
    Where-Object { $_.Extension.ToLowerInvariant() -in @(".dll", ".exe") } |
    Sort-Object -Property FullName
  foreach ($binary in $runtimeBinaries) {
    $relative = [IO.Path]::GetRelativePath($gstreamerRoot, $binary.FullName).Replace('\', '/')
    if ($recorded.Add($relative)) {
      $manifest.files += Get-FileReceipt $binary.FullName $relative
    }
  }

  $env:PATH = (Join-Path $gstreamerRoot "bin") + ";" + $savedPath
  $inspector = Join-Path $gstreamerRoot "bin/gst-inspect-1.0.exe"
  $stdoutPath = Join-Path $evidenceDirectoryPath "gst-version.stdout.log"
  $stderrPath = Join-Path $evidenceDirectoryPath "gst-version.stderr.log"
  $probe = Start-Process -FilePath $inspector -ArgumentList "--version" -Wait -PassThru -NoNewWindow -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
  $probeOutput = [IO.File]::ReadAllText($stdoutPath) + [IO.File]::ReadAllText($stderrPath)
  $manifest.probe = [ordered]@{
    argv = @($inspector, "--version")
    exit_code = $probe.ExitCode
    output = $probeOutput
  }
  if ($probe.ExitCode -ne 0 -or $probeOutput -notmatch '(?m)^GStreamer 1\.24\.13\s*$') {
    throw "The extracted GStreamer runtime did not report version 1.24.13 successfully."
  }
  $manifest.accepted = $true
  Write-Host $probeOutput
  Write-Host "Verified isolated SDK: $gstreamerRoot"
} catch {
  $manifest.failure = $_.Exception.Message
  throw
} finally {
  $env:PATH = $savedPath
  $utf8 = [Text.UTF8Encoding]::new($false)
  [IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 10) + [Environment]::NewLine, $utf8)
  Write-Host "SDK receipt: $manifestPath"
}
