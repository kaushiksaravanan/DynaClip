$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host '==> Running smoke tests'
python .\smoke_test.py

Write-Host '==> Building with PyInstaller'
python -m PyInstaller .\DynaClip.spec --noconfirm --clean

$Exe = Join-Path $Root 'dist\DynaClip.exe'
if (-not (Test-Path $Exe)) {
    throw "Build failed: $Exe not found"
}

Write-Host "==> Build ready: $Exe"
