<#
.SYNOPSIS
  Installs the Serum Bridge script for the Arturia KeyLab Essential mk3 in FL Studio.

.DESCRIPTION
  1. Copies "Serum Bridge KeyLab Essential mk3" into FL Studio's user Hardware folder.
     An existing serum_bridge_config.py is kept.
  2. Sets Serum 2's preset-stepping CCs in Serum2Prefs.json (a backup is made first),
     so Serum steps presets on the CCs the bridge sends.

  Close FL Studio (and any other host running Serum 2) first: Serum rewrites its
  prefs file when it closes and would undo step 2.

.PARAMETER HardwareDir
  FL Studio's user Hardware folder. Default: Documents\Image-Line\FL Studio\Settings\Hardware

.PARAMETER SkipSerumPrefs
  Don't touch Serum2Prefs.json (set the CCs yourself in Serum's preferences).

.PARAMETER Force
  Edit Serum2Prefs.json even if FL Studio seems to be running.
#>
param(
    [string]$HardwareDir = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Image-Line\FL Studio\Settings\Hardware'),
    [switch]$SkipSerumPrefs,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$ScriptName = 'Serum Bridge KeyLab Essential mk3'
$Source = Join-Path $PSScriptRoot "src\$ScriptName"
$Target = Join-Path $HardwareDir $ScriptName
$ArturiaDir = Join-Path $HardwareDir 'Arturia KeyLab Essential mk3'

function Write-Step($text) { Write-Host "==> $text" -ForegroundColor Cyan }
function Write-Warn($text) { Write-Host "    ! $text" -ForegroundColor Yellow }
function Write-Ok($text) { Write-Host "    $text" -ForegroundColor Green }

# ---------------------------------------------------------------- 1. files ----
Write-Step "Installing the script into $HardwareDir"
if (-not (Test-Path $HardwareDir)) {
    throw "FL Studio Hardware folder not found: $HardwareDir`nStart FL Studio once, or pass -HardwareDir <path>."
}
if (-not (Test-Path (Join-Path $ArturiaDir 'device_KLEss3.py'))) {
    Write-Warn "Arturia's KeyLab Essential mk3 script was not found in $ArturiaDir."
    Write-Warn "FL Studio puts it there itself; start FL once with the KeyLab connected."
    Write-Warn "Until then the bridge runs Serum browsing only (or set ARTURIA_DIR in serum_bridge_config.py)."
}
New-Item -ItemType Directory -Force -Path $Target | Out-Null
Copy-Item -Force (Join-Path $Source 'device_SerumBridge.py') $Target
$ConfigTarget = Join-Path $Target 'serum_bridge_config.py'
if (Test-Path $ConfigTarget) {
    Write-Ok "Kept your existing serum_bridge_config.py"
} else {
    Copy-Item (Join-Path $Source 'serum_bridge_config.py') $Target
}
Write-Ok "Installed to $Target"

# ---------------------------------------------------------- 2. Serum prefs ----
function Get-ConfigCC($name, $default) {
    $m = Select-String -Path $ConfigTarget -Pattern "^\s*$name\s*=\s*(\d+)" | Select-Object -First 1
    if ($m) { return [int]$m.Matches[0].Groups[1].Value }
    return $default
}
$NextCC = Get-ConfigCC 'PRESET_NEXT_CC' 14
$PrevCC = Get-ConfigCC 'PRESET_PREV_CC' 15

$Prefs = Join-Path $env:APPDATA 'Xfer\Serum 2\Serum2Prefs.json'
$ManualHint = "In Serum 2's preferences enable 'CC for rockers' and set Preset + = CC $NextCC, Preset - = CC $PrevCC."

if ($SkipSerumPrefs) {
    Write-Step "Skipping Serum2Prefs.json (-SkipSerumPrefs)"
    Write-Warn $ManualHint
} elseif (-not (Test-Path $Prefs)) {
    Write-Step "Serum 2 prefs not found at $Prefs"
    Write-Warn "Open Serum 2 once so it creates them, then run this installer again, or:"
    Write-Warn $ManualHint
} else {
    Write-Step "Setting Serum 2 preset CCs (next = CC $NextCC, prev = CC $PrevCC)"
    $running = Get-Process -Name 'FL64', 'FL', 'FL Studio' -ErrorAction SilentlyContinue
    if ($running -and -not $Force) {
        Write-Warn "FL Studio is running. Serum would overwrite its prefs when it closes."
        Write-Warn "Close FL Studio and run the installer again (the script files are already installed)."
        Write-Warn "Or use -Force if Serum isn't loaded in any open project."
        exit 1
    }
    $text = [IO.File]::ReadAllText($Prefs)
    $wanted = [ordered]@{
        'Enable CCForRockers'  = 1
        'CCForRocker Preset +' = $NextCC
        'CCForRocker Preset -' = $PrevCC
    }
    $missing = @()
    foreach ($key in $wanted.Keys) {
        $pattern = '("' + [regex]::Escape($key) + '"\s*:\s*)-?\d+'
        if ([regex]::IsMatch($text, $pattern)) {
            $text = [regex]::Replace($text, $pattern, '${1}' + $wanted[$key])
        } else {
            $missing += $key
        }
    }
    if ($missing.Count -gt 0) {
        Write-Warn ("Serum2Prefs.json has no " + ($missing -join ', ') + " entry (different Serum version?).")
        Write-Warn $ManualHint
    } else {
        $backup = "$Prefs.bak-" + (Get-Date -Format 'yyyyMMdd-HHmmss')
        Copy-Item $Prefs $backup
        [IO.File]::WriteAllText($Prefs, $text, (New-Object Text.UTF8Encoding $false))
        Write-Ok "Updated $Prefs (backup: $backup)"
    }
}

# ---------------------------------------------------------- 3. next steps ----
Write-Host ""
Write-Step "Finish the setup in FL Studio"
$SerumPort = Get-ConfigCC 'SERUM_PORT' 100
Write-Host "  1. Options > MIDI settings: select the KeyLab's DAW port (input and output) and"
Write-Host "     set Controller type to 'KeyLab Essential mk3 + Serum 2 Bridge' instead of"
Write-Host "     Arturia's script."
Write-Host "  2. Open Serum 2, click the gear (wrapper settings) at the top left of its window,"
Write-Host "     and set MIDI > Input port to $SerumPort (the bridge's Serum port, NOT the KeyLab's"
Write-Host "     port). Do this per Serum instance, or save it in a template/project."
Write-Host "  3. Focus Serum's window and turn the main encoder, or press context buttons 3 / 4."
