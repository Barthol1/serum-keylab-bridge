<#
.SYNOPSIS
  Removes the Serum Bridge script from FL Studio's Hardware folder.
  Serum2Prefs.json is left as is; its backups (Serum2Prefs.json.bak-*) sit next to it.
#>
param(
    [string]$HardwareDir = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Image-Line\FL Studio\Settings\Hardware')
)
$ErrorActionPreference = 'Stop'
$Target = Join-Path $HardwareDir 'Serum Bridge KeyLab Essential mk3'
if (Test-Path $Target) {
    Remove-Item -Recurse -Force $Target
    Write-Host "Removed $Target"
} else {
    Write-Host "Nothing to remove at $Target"
}
Write-Host "In FL Studio, set the KeyLab's controller type back to Arturia's 'KeyLab Essential mk3' script."
