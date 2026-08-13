[CmdletBinding()]
param(
  [Parameter(Mandatory, Position = 0)]
  [ValidateSet('load', 'unload')]
  [string]$Action
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$binary = Join-Path $root 'tray\target\release\cdx-tray.exe'
$wrapper = Join-Path $root 'tray\target\release\cdx-tray-cdx.cmd'

function Invoke-DevPython([string]$code) {
  & node (Join-Path $root 'bin\python-runner.js') -c $code
  if ($LASTEXITCODE) { throw 'CDX Python helper failed.' }
}

function Stop-Companion {
  Invoke-DevPython 'from src.tray_restart import stop_running_companion; r=stop_running_companion(); assert not r["was_running"] or r["stopped"], r'
}

function RunningPid {
  $pid = & node (Join-Path $root 'bin\python-runner.js') -c 'from src.tray_instance import companion_instance; print(companion_instance().get("pid") or "")'
  if ($LASTEXITCODE) { throw 'Could not read the tray instance lock.' }
  return "$pid".Trim()
}

if ($Action -eq 'load') {
  & cargo build --release --manifest-path (Join-Path $root 'tray\Cargo.toml')
  if ($LASTEXITCODE -or -not (Test-Path $binary)) { throw 'Development tray build failed.' }
  @"
@echo off
node "$root\bin\cdx.js" %*
"@ | Set-Content -NoNewline -Encoding ascii $wrapper
  Stop-Companion
  $env:CDX_TRAY_CDX = $wrapper
  Start-Process -FilePath $binary
  Start-Sleep -Seconds 1
  $pid = RunningPid
  if (-not $pid) { throw 'Development tray did not register as running.' }
  $command = (Get-CimInstance Win32_Process -Filter "ProcessId = $pid").CommandLine
  if ($command -notlike "*$binary*") { throw "Expected development companion, got: $command" }
  Write-Output "Development tray loaded: $binary"
  exit 0
}

Stop-Companion
& node (Join-Path $root 'bin\cdx.js') tray launch
if ($LASTEXITCODE) { throw 'Could not restore the installed tray companion.' }
Start-Sleep -Seconds 1
$pid = RunningPid
if (-not $pid) { throw 'Installed tray did not register as running.' }
Write-Output 'Installed tray restored.'
