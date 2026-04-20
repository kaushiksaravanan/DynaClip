$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Exe = Join-Path $Root 'dist\DynaClip.exe'
$Startup = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\DynaClip.cmd'

if (-not (Test-Path $Exe)) {
    Write-Error "Build not found: $Exe"
}

Write-Host "Installing startup launcher for $Exe"

$Content = "@echo off`r`nstart `"`" `"$Exe`"`r`n"
Set-Content -Path $Startup -Value $Content -Encoding UTF8

Write-Host "Startup launcher installed at $Startup"
