# Backward-compatible entry point; the desktop app now uses the Flutter Windows setup.
$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "setup_friday_windows.ps1") @args
