Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "              STARTING STUDIORA WEB APPLICATION" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$ScriptDir\backend"

$PythonExe = ".\venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    Write-Host "[ERROR] Virtual environment not found at backend\venv!" -ForegroundColor Red
    exit 1
}

Write-Host "Starting Studiora server at http://127.0.0.1:8000 ..." -ForegroundColor Green
Write-Host "Open your browser at: http://localhost:8000" -ForegroundColor Yellow
Write-Host "Press Ctrl+C in this terminal to stop the server.`n" -ForegroundColor Gray

& $PythonExe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
