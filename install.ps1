param(
    [string]$Version = $env:CDX_VERSION,
    [string]$Prefix = $env:CDX_PREFIX
)

$ErrorActionPreference = "Stop"

$repo = "AlexAgo83/cdx-manager"

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "cdx install: missing required command: $Name"
    }
}

Require-Command python

if (-not $Prefix) {
    $Prefix = Join-Path $env:LOCALAPPDATA "cdx-manager"
}

$binDir = Join-Path $Prefix "bin"
$installRoot = Join-Path $Prefix "versions"

if (-not $Version) {
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/releases/latest"
    $Version = $release.tag_name
}

if ($Version.StartsWith("v")) {
    $tag = $Version
} else {
    $tag = "v$Version"
}

$tmpRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("cdx-install-" + [guid]::NewGuid().ToString("N"))
$archivePath = Join-Path $tmpRoot "cdx-manager.zip"
$extractRoot = Join-Path $tmpRoot "extract"
$targetDir = Join-Path $installRoot $tag.TrimStart("v")
$archiveUrl = "https://github.com/$repo/archive/refs/tags/$tag.zip"

New-Item -ItemType Directory -Force -Path $tmpRoot, $extractRoot, $binDir, $installRoot | Out-Null

try {
    Invoke-WebRequest -Uri $archiveUrl -OutFile $archivePath
    Expand-Archive -Path $archivePath -DestinationPath $extractRoot -Force

    $sourceDir = Get-ChildItem -Path $extractRoot -Directory | Select-Object -First 1
    if (-not $sourceDir) {
        throw "cdx install: failed to extract release archive"
    }

    if (Test-Path $targetDir) {
        Remove-Item -Recurse -Force $targetDir
    }
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    Copy-Item -Path (Join-Path $sourceDir.FullName "*") -Destination $targetDir -Recurse -Force

    $launcherPath = Join-Path $binDir "cdx.cmd"
    $launcher = @"
@echo off
set SCRIPT=%~dp0..\versions\${($tag.TrimStart("v"))}\bin\cdx
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 "%SCRIPT%" %*
  exit /b %ERRORLEVEL%
)
python "%SCRIPT%" %*
"@
    Set-Content -Path $launcherPath -Value $launcher -Encoding ascii

    Write-Host "Installed cdx $tag to $targetDir"
    Write-Host "Created launcher $launcherPath"
    if (-not (($env:PATH -split ";") -contains $binDir)) {
        Write-Warning "Add $binDir to PATH to run cdx from anywhere."
    }
} finally {
    if (Test-Path $tmpRoot) {
        Remove-Item -Recurse -Force $tmpRoot
    }
}
