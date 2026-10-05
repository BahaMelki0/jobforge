$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$jobforgeListener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($jobforgeListener) {
    Write-Host 'Port 8000 is already in use. If JobForge is running, open http://127.0.0.1:8000. No second scan worker was started.'
    return
}
# Start the local model service if it is not already running.
try {
    Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 | Out-Null
} catch {
    $jobforgeOllamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
    if ($jobforgeOllamaCommand) {
        $env:OLLAMA_NO_CLOUD = '1'
        $env:OLLAMA_FLASH_ATTENTION = '1'
        $env:OLLAMA_MAX_LOADED_MODELS = '1'
        New-Item -ItemType Directory -Path "$PSScriptRoot\runtime" -Force | Out-Null
        Start-Process -FilePath $jobforgeOllamaCommand.Source -ArgumentList 'serve' -WindowStyle Hidden -RedirectStandardOutput "$PSScriptRoot\runtime\ollama.log" -RedirectStandardError "$PSScriptRoot\runtime\ollama-error.log" | Out-Null
    }
}
Write-Host 'JobForge: http://127.0.0.1:8000 - Ctrl+C stops the app and its scan scheduler.'
& "$PSScriptRoot\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
