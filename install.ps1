#requires -Version 5.1
<#
.SYNOPSIS
  Install the Hermes Memory Manager plugin (backend + desktop UI) in one go.

.DESCRIPTION
  Copies:
    1. dashboard/  -> <hermes-agent>/plugins/hermes-memory-manager/dashboard/
       (bundled backend — shared by every profile, enabled by default)
    2. plugin.js   -> <hermes home>/desktop-plugins/hermes-memory-manager/
       (desktop UI for the default profile)
  Run from the extracted package folder (this script must sit next to
  dashboard/ and desktop-plugins/).

.PARAMETER HermesHome
  Hermes home directory. Auto-detected from %LOCALAPPDATA%\hermes (Windows)
  or ~/.hermes when omitted.

.PARAMETER AllProfiles
  Also install the desktop UI into every profiles\<name>\desktop-plugins\,
  so the plugin works after switching to a named profile in the app.

.EXAMPLE
  .\install.ps1
.EXAMPLE
  .\install.ps1 -AllProfiles
.EXAMPLE
  .\install.ps1 -HermesHome "D:\tools\hermes"
#>
[CmdletBinding()]
param(
  [string]$HermesHome,
  [switch]$AllProfiles
)

$ErrorActionPreference = 'Stop'
$Src = $PSScriptRoot

# ── 1. locate the Hermes home ───────────────────────────────────────────────
if (-not $HermesHome) {
  $candidates = @(
    (Join-Path $env:LOCALAPPDATA 'hermes'),
    (Join-Path $env:USERPROFILE '.hermes')
  ) | Where-Object { Test-Path (Join-Path $_ 'config.yaml') }
  $HermesHome = $candidates | Select-Object -First 1
}
if (-not $HermesHome -or -not (Test-Path (Join-Path $HermesHome 'config.yaml'))) {
  Write-Error "Hermes home not found. Re-run with -HermesHome <path>, e.g. .\install.ps1 -HermesHome '$env:LOCALAPPDATA\hermes'"
  exit 1
}
Write-Host "Hermes home  : $HermesHome"

# ── 2. locate the hermes-agent install (bundled plugins root) ───────────────
$AgentDir = Join-Path $HermesHome 'hermes-agent'
if (-not (Test-Path (Join-Path $AgentDir 'plugins'))) {
  # Fallback: resolve through the hermes CLI on PATH.
  $cmd = Get-Command hermes -ErrorAction SilentlyContinue
  if ($cmd) {
    $AgentDir = Split-Path -Parent (Split-Path -Parent $cmd.Source)
  }
}
if (-not (Test-Path (Join-Path $AgentDir 'plugins'))) {
  Write-Error "Could not find the hermes-agent install (no plugins\ dir under '$AgentDir'). Pass -HermesHome pointing at the Hermes home that contains it."
  exit 1
}
Write-Host "hermes-agent : $AgentDir"

# ── 3. copy the backend (bundled) ───────────────────────────────────────────
$Manifest = Join-Path $Src 'dashboard\manifest.json'
if (-not (Test-Path $Manifest)) {
  Write-Error "dashboard\manifest.json not found next to this script — run it from the extracted package."
  exit 1
}
$BackendDest = Join-Path $AgentDir 'plugins\hermes-memory-manager\dashboard'
New-Item -ItemType Directory -Force -Path $BackendDest | Out-Null
Copy-Item (Join-Path $Src 'dashboard\*') $BackendDest -Recurse -Force
Write-Host "[1/3] Backend -> $BackendDest"

# ── 4. copy the desktop UI (default profile) ────────────────────────────────
$UiFile = Join-Path $Src 'desktop-plugins\hermes-memory-manager\plugin.js'
if (-not (Test-Path $UiFile)) {
  Write-Error "desktop-plugins\hermes-memory-manager\plugin.js not found next to this script."
  exit 1
}
$UiDest = Join-Path $HermesHome 'desktop-plugins\hermes-memory-manager'
New-Item -ItemType Directory -Force -Path $UiDest | Out-Null
Copy-Item $UiFile (Join-Path $UiDest 'plugin.js') -Force
Write-Host "[2/3] Desktop UI (default profile) -> $UiDest"

# ── 5. optional: every named profile ────────────────────────────────────────
if ($AllProfiles) {
  $profilesDir = Join-Path $HermesHome 'profiles'
  if (Test-Path $profilesDir) {
    Get-ChildItem $profilesDir -Directory | ForEach-Object {
      $dest = Join-Path $_.FullName 'desktop-plugins\hermes-memory-manager'
      New-Item -ItemType Directory -Force -Path $dest | Out-Null
      Copy-Item $UiFile (Join-Path $dest 'plugin.js') -Force
      Write-Host "     Desktop UI ($($_.Name)) -> $dest"
    }
  } else {
    Write-Host '     (no profiles\ dir — nothing to do)'
  }
  Write-Host "[3/3] Named profiles done"
} else {
  Write-Host '[3/3] Skipped named profiles (re-run with -AllProfiles to install there too)'
}

Write-Host ''
Write-Host 'Installed. Next steps:'
Write-Host '  1. FULLY QUIT the Hermes desktop app and reopen it'
Write-Host '     (the backend caches plugins — a plain reload is not enough)'
Write-Host '  2. "Memory" should appear in the left sidebar'
