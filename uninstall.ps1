$ErrorActionPreference = 'Stop'

$Startup = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\DynaClip.cmd'

if (Test-Path $Startup) {
    Remove-Item $Startup -Force
    Write-Host "Removed startup launcher: $Startup"
} else {
    Write-Host 'No startup launcher found.'
}
