param(
    [switch]$SkipSetup,
    [switch]$Release
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$desktop = Join-Path $repoRoot "desktop_app"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
    throw "Flutter SDK was not found on PATH. Follow https://docs.flutter.dev/platform-integration/windows/setup"
}

if (-not $SkipSetup) {
    & (Join-Path $PSScriptRoot "setup_friday_windows.ps1")
}

if (-not (Test-Path $venvPython)) {
    throw "The project Python environment is missing. Run .\scripts\setup_friday_windows.ps1 first."
}

$env:FRIDAY_PROJECT_ROOT = $repoRoot
$env:FRIDAY_PYTHON = $venvPython
if (-not $env:OLLAMA_BASE_URL) { $env:OLLAMA_BASE_URL = "http://127.0.0.1:11434" }

Push-Location $desktop
try {
    if ($Release) {
        flutter build windows --release
        Write-Host "Build output: $desktop\build\windows\x64\runner\Release"
    } else {
        flutter run -d windows
    }
} finally {
    Pop-Location
}
