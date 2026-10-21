$ErrorActionPreference = "Stop"
$model = if ($env:FRIDAY_OLLAMA_MODEL) { $env:FRIDAY_OLLAMA_MODEL } else { "qwen2.5:3b" }
$baseUrl = if ($env:OLLAMA_BASE_URL) { $env:OLLAMA_HOST.TrimEnd("/") } else { "http://127.0.0.1:11434" }

Write-Host "FRIDAY local AI setup" -ForegroundColor Cyan
Write-Host "Model: $model"
Write-Host "Ollama: $baseUrl"

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
  Write-Host "Ollama CLI was not found. Install it from https://ollama.com/download, then reopen PowerShell." -ForegroundColor Yellow
  exit 1
}
try {
  Invoke-RestMethod -Uri "$baseUrl/api/tags" -TimeoutSec 3 | Out-Null
} catch {
  Write-Host "Ollama is installed but not reachable. Start the Ollama app/service and rerun this script." -ForegroundColor Yellow
  exit 1
}
Write-Host "Pulling model; this requires internet and disk space. The downloaded model can run offline later." -ForegroundColor Yellow
ollama pull $model
if ($LASTEXITCODE -ne 0) { throw "ollama pull failed with exit code $LASTEXITCODE" }

Write-Host ""
Write-Host "Model ready. In the FRIDAY repository run:" -ForegroundColor Green
Write-Host "  python -m pip install -r requirements.txt"
Write-Host "  python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"
Write-Host "Then open http://127.0.0.1:8000/static/local-ai.html"
Write-Host "This script does not install coding agents or enable shell execution."
