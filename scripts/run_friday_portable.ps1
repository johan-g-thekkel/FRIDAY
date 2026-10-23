param(
    [switch]$SkipSetup,
    [switch]$InstallOllama,
    [switch]$SkipOfflineSpeech,
    [switch]$SkipModelDownload
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPython = Join-Path $repoRoot ".venv\\Scripts\\python.exe"
$exe = Join-Path $repoRoot "desktop_app\\build\\windows\\x64\\runner\\Release\\friday_desktop.exe"
$setup = Join-Path $PSScriptRoot "setup_friday_windows.ps1"

if (-not (Test-Path $exe)) {
    throw "The prebuilt FRIDAY executable was not found at $exe. Download the FRIDAY Windows release package, or use scripts/run_friday_windows.ps1 from source."
}

if (-not $SkipSetup) {
    $setupArgs = @("-SkipFlutter")
    if ($InstallOllama) { $setupArgs += "-InstallOllama" }
    if ($SkipOfflineSpeech) { $setupArgs += "-SkipOfflineSpeech" }
    if ($SkipModelDownload) { $setupArgs += "-SkipModelDownload" }
    & $setup @setupArgs
}

if (-not (Test-Path $venvPython)) {
    throw "The Python sidecar environment is missing. Run scripts/run_friday_portable.ps1 once without -SkipSetup to install dependencies."
}

$env:FRIDAY_PROJECT_ROOT = $repoRoot
$env:FRIDAY_PYTHON = $venvPython
if (-not $env:OLLAMA_BASE_URL) { $env:OLLAMA_BASE_URL = "http://127.0.0.1:11434" }

Write-Host "Launching the native FRIDAY desktop assistant..."
& $exe
