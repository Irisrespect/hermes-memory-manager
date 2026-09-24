#requires -Version 5.1
<#
.SYNOPSIS
  Install the Hermes Memory Manager plugin (backend + desktop UI) in one go.

.DESCRIPTION
  Copies:
    1. dashboard/  -> <hermes home>/plugins/hermes-memory-manager/dashboard/
       (user backend — survives Hermes updates; hermes-agent/plugins/ would be
       wiped by the ZIP-fallback updater)
    2. desktop/plugin.js -> <hermes home>/desktop-plugins/hermes-memory-manager/
       (desktop UI for the default profile)
  Then enables the backend via `hermes plugins enable` (safe: CLI-owned
  config write, no manual YAML editing).
  Run from the extracted package folder (this script must sit next to
  dashboard/ and desktop/).

.PARAMETER HermesHome
  Hermes home directory. Auto-detected from %LOCALAPPDATA%\hermes (Windows)
  or ~/.hermes when omitted.

.PARAMETER AllProfiles
  Also install the desktop UI into every profiles\<name>\desktop-plugins\,
  so the plugin works after switching to a named profile in the app.
  (Each named profile whose backend serves the app also needs the plugin in
  its own plugins.enabled — the script handles that too.)

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

# ── 2. copy the backend (user location — survives updates) ──────────────────
$Manifest = Join-Path $Src 'dashboard\manifest.json'
if (-not (Test-Path $Manifest)) {
  Write-Error "dashboard\manifest.json not found next to this script — run it from the extracted package."
  exit 1
}
$BackendDest = Join-Path $HermesHome 'plugins\hermes-memory-manager\dashboard'
New-Item -ItemType Directory -Force -Path $BackendDest | Out-Null
Copy-Item (Join-Path $Src 'dashboard\*') $BackendDest -Recurse -Force
Write-Host "[1/4] Backend -> $BackendDest"

# ── 3. copy the desktop UI (default profile) ────────────────────────────────
$UiFile = Join-Path $Src 'desktop\plugin.js'
if (-not (Test-Path $UiFile)) {
  Write-Error "desktop\plugin.js not found next to this script."
  exit 1
}
$UiDest = Join-Path $HermesHome 'desktop-plugins\hermes-memory-manager'
New-Item -ItemType Directory -Force -Path $UiDest | Out-Null
Copy-Item $UiFile (Join-Path $UiDest 'plugin.js') -Force
Write-Host "[2/4] Desktop UI (default profile) -> $UiDest"

# ── 4. optional: every named profile ────────────────────────────────────────
$ProfileHomes = @($HermesHome)
if ($AllProfiles) {
  $profilesDir = Join-Path $HermesHome 'profiles'
  if (Test-Path $profilesDir) {
    Get-ChildItem $profilesDir -Directory | ForEach-Object {
      $dest = Join-Path $_.FullName 'desktop-plugins\hermes-memory-manager'
      New-Item -ItemType Directory -Force -Path $dest | Out-Null
      Copy-Item $UiFile (Join-Path $dest 'plugin.js') -Force
      Write-Host "     Desktop UI ($($_.Name)) -> $dest"
      $ProfileHomes += $_.FullName
    }
  } else {
    Write-Host '     (no profiles\ dir — nothing to do)'
  }
  Write-Host "[3/4] Named profiles done"
} else {
  Write-Host '[3/4] Skipped named profiles (re-run with -AllProfiles to install there too)'
}

# ── 5. enable the backend in every touched profile ──────────────────────────
# The plugin API gate checks the *serving* profile's plugins.enabled, so each
# profile home that got the UI needs the backend enabled too.
# NOTE: `hermes plugins enable` resolves names only under the CURRENT
# HERMES_HOME's plugins/ dir, so it fails for named profiles (the plugin
# lives in the hermes root). Enable via a minimal YAML append instead:
# exactly one list item under plugins.enabled, comments/structure untouched.
$EnableScript = @'
import sys, io
home, pid = sys.argv[1], sys.argv[2]
cfg = home + '/config.yaml'
lines = io.open(cfg, encoding='utf-8').read().splitlines(keepends=True)
nl = '\r\n' if any(l.endswith('\r\n') for l in lines) else '\n'
if any(l.strip() == '- ' + pid for l in lines):
    print('already enabled')
else:
    out = []
    done = False
    i = 0
    while i < len(lines):
        l = lines[i]
        out.append(l)
        if (not done and l.rstrip('\r\n') == '  enabled:'
                and i > 0 and lines[i-1].rstrip('\r\n') == 'plugins:'):
            j = i + 1
            while j < len(lines) and lines[j].strip().startswith('- '):
                out.append(lines[j])
                j += 1
            out.append('    - ' + pid + nl)
            out.extend(lines[j:])
            done = True
            break
        i += 1
    if not done:
        if out and not out[-1].endswith(('\n', '\r')):
            out[-1] = out[-1] + nl
        out.append('plugins:' + nl + '  enabled:' + nl + '    - ' + pid + nl)
    io.open(cfg + '.bak-install', 'w', encoding='utf-8', newline='').writelines(lines)
    io.open(cfg, 'w', encoding='utf-8', newline='').writelines(out)
    print('enabled (backup: config.yaml.bak-install)')
'@
foreach ($home in $ProfileHomes) {
  $cfg = Join-Path $home 'config.yaml'
  $py = Get-Command python -ErrorAction SilentlyContinue
  if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
  if ($py) {
    $out = & $py.Source -c $EnableScript "$home" 'hermes-memory-manager' 2>&1
    Write-Host "     enable [$home]: $out"
  } else {
    Write-Warning "no python found — enable manually: add 'hermes-memory-manager' under plugins.enabled in $cfg"
  }
}
Write-Host "[4/4] Backend enabled"

Write-Host ''
Write-Host 'Installed. Next steps:'
Write-Host '  1. FULLY QUIT the Hermes desktop app and reopen it'
Write-Host '     (the backend caches plugins — a plain reload is not enough)'
Write-Host '  2. "Memory" should appear in the left sidebar'
