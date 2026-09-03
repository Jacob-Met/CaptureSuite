# Stops running capture binaries before a build.
#
# A live capture_daemon holds capture_worker_camera.exe open, so the linker
# fails with LNK1168 and the whole build has to be repeated. Filtering happens
# here rather than in a hooks.json matcher so the condition stays readable and
# testable.

$ErrorActionPreference = 'SilentlyContinue'

function Write-Decision {
    param([hashtable]$Decision)
    [Console]::Out.Write((ConvertTo-Json $Decision -Compress))
    exit 0
}

$raw = [Console]::In.ReadToEnd()
$command = ''
try {
    $command = (ConvertFrom-Json $raw).command
} catch {
    Write-Decision @{ permission = 'allow' }
}

if ($command -notmatch 'cmake\s+--build|(^|\s)ninja(\s|$)') {
    Write-Decision @{ permission = 'allow' }
}

$targets = @('capture_daemon', 'capture_worker_camera', 'capture_worker_stub')
$running = Get-Process -Name $targets -ErrorAction SilentlyContinue
if (-not $running) {
    Write-Decision @{ permission = 'allow' }
}

$names = ($running | Select-Object -ExpandProperty ProcessName -Unique) -join ', '
$running | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 300

Write-Decision @{
    permission    = 'allow'
    user_message  = "Stopped $names before building so the linker can replace the binaries."
    agent_message = "A hook stopped these running capture processes before the build: $names. Restart the daemon if the next step needs it."
}
