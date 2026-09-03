# SPDX-License-Identifier: GPL-3.0-only
<#
.SYNOPSIS
  Scaffold a new CaptureSuite acquisition plugin (Python or C++ stub layout).

.EXAMPLE
  .\tools\new_plugin.ps1 -PluginId "lab.force" -DisplayName "Force plate" -Family numeric -Modality force

.EXAMPLE
  .\tools\new_plugin.ps1 -PluginId "vendor.imu" -DisplayName "Vendor IMU" -Lang cpp -Family imu -Modality imu -Hardware
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [ValidatePattern('^[a-z0-9]+(\.[a-z0-9_-]+)+$')]
  [string]$PluginId,

  [Parameter(Mandatory = $true)]
  [string]$DisplayName,

  [ValidateSet('python', 'cpp')]
  [string]$Lang = 'python',

  [string]$Family = 'numeric',

  [string]$Modality = 'numeric',

  [string]$SchemaId = 'generic.numeric_batch/1',

  [string]$DirName = '',

  [switch]$Hardware,

  [switch]$Force
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$TplRoot = Join-Path $PSScriptRoot 'plugin_templates'

if (-not $DirName) {
  $DirName = ($PluginId -replace '\.', '_')
}

$PluginDir = Join-Path $Root "plugins\$DirName"
if ((Test-Path $PluginDir) -and -not $Force) {
  Write-Error "Already exists: $PluginDir (pass -Force to overwrite generated files)"
}
New-Item -ItemType Directory -Force -Path $PluginDir | Out-Null

$hwBool = [bool]$Hardware
$hwCap = if ($Hardware) { '1' } else { '0' }
$license = if ($Lang -eq 'python') { 'Apache-2.0' } else { 'GPL-3.0-only' }
$classStem = ($PluginId -split '\.')[-1]
$className = ($classStem.Substring(0, 1).ToUpper() + $classStem.Substring(1)) + 'Worker'
$moduleName = $DirName
$enableEnv = ('CAPTURE_USE_' + ($PluginId.ToUpper() -replace '[^A-Z0-9]', '_'))
$sourceId = "$PluginId.main"
$streamId = "$PluginId.main.batch"
$schemaRev = "$PluginId/1"
$testSlug = ($PluginId -replace '\.', '_')

function Expand-Template([string]$TemplatePath, [hashtable]$Map) {
  $text = [System.IO.File]::ReadAllText($TemplatePath)
  foreach ($key in $Map.Keys) {
    $text = $text.Replace("{{${key}}}", [string]$Map[$key])
  }
  return $text
}

function Write-Utf8NoBom([string]$Path, [string]$Content) {
  $utf8 = New-Object System.Text.UTF8Encoding $false
  [System.IO.File]::WriteAllText($Path, $Content, $utf8)
}

$pluginJson = [ordered]@{
  plugin_id         = $PluginId
  plugin_version    = '0.1.0'
  family            = $Family
  display_name      = $DisplayName
  executable        = $(if ($Lang -eq 'python') { 'run_worker.cmd' } else { "capture_worker_$DirName.exe" })
  isolation         = 'per_source'
  enable_by_default = $true
  enable_env        = $enableEnv
  hardware          = $hwBool
  license           = $license
  capabilities      = [ordered]@{
    families = $Family
    hardware = $hwCap
  }
  timeouts_ms       = [ordered]@{
    spawn = 15000
    stop  = 10000
  }
}
($pluginJson | ConvertTo-Json -Depth 6) + "`n" | Set-Content -Path (Join-Path $PluginDir 'plugin.json') -Encoding utf8

$extra = if ($Lang -eq 'python') {
  "Smoke:`n`n``````powershell`npython -m pytest tests/protocol/test_${testSlug}_plugin.py -q`n``````"
} else {
  @"
## C++ next steps

1. Copy ``workers/stub/`` into a new ``workers/$DirName/`` target.
2. Implement Identify/Start/Stop against your SDK. CLI must accept
   ``--pipe --worker-id --plugin``.
3. Point ``plugin.json`` ``executable`` at the built ``.exe`` and add CMake
   POST_BUILD copy into ``plugins/$DirName/`` next to ``capture_daemon``.
4. Set ``runtime.path_prepend`` / ``requires.env`` for vendor DLLs.
"@
}

$map = @{
  PLUGIN_ID    = $PluginId
  DISPLAY_NAME = $DisplayName
  DIR_NAME     = $DirName
  MODULE_NAME  = $moduleName
  CLASS_NAME   = $className
  FAMILY       = $Family
  MODALITY     = $Modality
  SCHEMA_ID    = $SchemaId
  SCHEMA_REV   = $schemaRev
  SOURCE_ID    = $sourceId
  STREAM_ID    = $streamId
  ENABLE_ENV   = $enableEnv
  HW_CAP       = $hwCap
  LANG         = $Lang
  EXTRA_SECTION = $extra
}

$readme = Expand-Template (Join-Path $TplRoot 'README.md.tmpl') $map
Write-Utf8NoBom (Join-Path $PluginDir 'README.md') $readme

if ($Lang -eq 'python') {
  $py = Expand-Template (Join-Path $TplRoot 'python\worker.py.tmpl') $map
  Write-Utf8NoBom (Join-Path $PluginDir "$moduleName.py") $py

  $cmd = Expand-Template (Join-Path $TplRoot 'python\run_worker.cmd.tmpl') $map
  Write-Utf8NoBom (Join-Path $PluginDir 'run_worker.cmd') $cmd

  $test = Expand-Template (Join-Path $TplRoot 'python\test_plugin.py.tmpl') $map
  $testPath = Join-Path $Root "tests\protocol\test_${testSlug}_plugin.py"
  Write-Utf8NoBom $testPath $test
}

Write-Host ""
Write-Host "Created plugin scaffold:"
Write-Host "  $PluginDir"
if ($Lang -eq 'python') {
  Write-Host "  tests/protocol/test_${testSlug}_plugin.py"
  Write-Host ""
  Write-Host "Next:"
  Write-Host "  & `"`$env:LOCALAPPDATA\Programs\Python\Python312\python.exe`" -m pytest tests/protocol/test_${testSlug}_plugin.py -q"
  Write-Host "  # edit plugins/$DirName/$moduleName.py"
  Write-Host "  # paste docs/prompts/02_python_plugin.md into Cursor"
} else {
  Write-Host ""
  Write-Host "Next: copy workers/stub -> workers/$DirName, wire CMake,"
  Write-Host "      paste docs/prompts/03_cpp_plugin.md into Cursor"
}
Write-Host ""
