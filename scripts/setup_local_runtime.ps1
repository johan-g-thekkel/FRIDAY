$ErrorActionPreference = "Stop"

$model = if ($env:FRIDAY_OLLAMA_MODEL) { $env:FRIDAY_OLLAMA_MODEL } else { "qwen2.5:1.5b" }

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Ollama is not installed. Install it from https://ollama.com/download/windows, then reopen PowerShell." -ForegroundColor Yellow
    exit 1
}

$baseUrl = if ($env:OLLAMA_BASE_URL) { $env:OLLAMA_BASE_URL.TrimEnd("/") } else { "http://127.0.0.1:11434" }
try {
    Invoke-RestMethod -Uri "$baseUrl/api/tags" -TimeoutSec 2 | Out-Null
} catch {
    Write-Host "Starting Ollama server..."
    Start-Process -FilePath (Get-Command ollama).Source -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
    Invoke-RestMethod -Uri "$baseUrl/api/tags" -TimeoutSec 10 | Out-Null
}

Write-Host "Downloading local model $model..."
ollama pull $model
python -m pip install -r requirements.txt
python -m pip install -r requirements-voice.txt

Write-Host ""
Write-Host "Model setup finished. Start FRIDAY with:"
Write-Host "python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload"
Write-Host "Then open http://127.0.0.1:8000"
