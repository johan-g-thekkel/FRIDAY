param(
    [switch]$SkipOfflineSpeech,
    [switch]$SkipModelDownload,
    [switch]$InstallOllama
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$desktop = Join-Path $repoRoot "desktop_app"
$venv = Join-Path $repoRoot ".venv"
$venvPython = Join-Path $venv "Scripts\python.exe"

Write-Host ""
Write-Host "  FRIDAY // Windows local setup" -ForegroundColor Cyan
Write-Host "  Repository: $repoRoot"
Write-Host ""

if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
    throw "Flutter SDK was not found on PATH. Install Flutter and Windows desktop dependencies first: https://docs.flutter.dev/platform-integration/windows/setup"
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3.11+ was not found on PATH. Install Python and reopen PowerShell."
}

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating the project Python environment..."
    python -m venv $venv
}

Write-Host "Installing FRIDAY backend packages..."
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $repoRoot "requirements.txt")

if (-not $SkipOfflineSpeech) {
    Write-Host "Installing offline Whisper speech recognition..."
    & $venvPython -m pip install -r (Join-Path $repoRoot "requirements-voice.txt")
} else {
    Write-Host "Offline speech package skipped; the voice UI will show its setup state."
}

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    if ($InstallOllama -and (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host "Installing Ollama via Windows Package Manager..."
        winget install --id Ollama.Ollama --exact --accept-source-agreements --accept-package-agreements
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
    }
}

if (Get-Command ollama -ErrorAction SilentlyContinue) {
    $ollamaUrl = if ($env:OLLAMA_BASE_URL) { $env:OLLAMA_BASE_URL.TrimEnd("/") } else { "http://127.0.0.1:11434" }
    try {
        Invoke-RestMethod -Uri "$ollamaUrl/api/tags" -TimeoutSec 2 | Out-Null
    } catch {
        Write-Host "Starting Ollama server..."
        Start-Process -FilePath (Get-Command ollama).Source -ArgumentList "serve" -WindowStyle Hidden
        $ready = $false
        for ($i = 0; $i -lt 20; $i++) {
            Start-Sleep -Milliseconds 500
            try {
                Invoke-RestMethod -Uri "$ollamaUrl/api/tags" -TimeoutSec 2 | Out-Null
                $ready = $true
                break
            } catch {}
        }
        if (-not $ready) {
            Write-Warning "Ollama did not become reachable. Check the Ollama application and run setup again."
        }
    }

    if (-not $SkipModelDownload) {
        $model = if ($env:FRIDAY_OLLAMA_MODEL) { $env:FRIDAY_OLLAMA_MODEL } else { "qwen2.5:1.5b" }
        $tags = @()
        try {
            $tags = (Invoke-RestMethod -Uri "$ollamaUrl/api/tags" -TimeoutSec 4).models | ForEach-Object { $_.name }
        } catch {}
        if ($tags -notcontains $model) {
            Write-Host "Pulling starter model $model (download required once)..."
            ollama pull $model
        } else {
            Write-Host "Starter model $model is already installed."
        }
    }
} elseif (-not $SkipModelDownload) {
    Write-Warning "Ollama is not installed. Install it from https://ollama.com/download/windows, then run this script again. The Flutter app can open, but local model inference will not work until Ollama is available."
}

Push-Location $desktop
try {
    if (-not (Test-Path (Join-Path $desktop "windows\runner\main.cpp"))) {
        Write-Host "Generating the native Windows runner files..."
        flutter create --platforms=windows .
    }
    Write-Host "Resolving Flutter packages..."
    flutter pub get
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Next: .\scripts\run_friday_windows.ps1"
