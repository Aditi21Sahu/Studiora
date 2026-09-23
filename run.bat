@echo off
echo ========================================================
echo               STARTING STUDIORA WEB APPLICATION
echo ========================================================
echo.

cd /d "%~dp0backend"

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found at backend\venv!
    pause
    exit /b 1
)

echo Starting Studiora server at http://127.0.0.1:8000 ...
echo Open your browser at: http://localhost:8000
echo Press Ctrl+C in this terminal to stop the server.
echo.

.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
