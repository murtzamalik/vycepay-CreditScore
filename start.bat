@echo off
echo Starting VyceScore Backend and Frontend...
echo.

:: Start backend in a new window
start "VyceScore Backend" cmd /k "cd /d C:\Code\VyceScore\backend && .venv\Scripts\activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

:: Start frontend in a new window
start "VyceScore Frontend" cmd /k "cd /d C:\Code\VyceScore\frontend && npm run dev"

echo Backend starting on http://localhost:8000
echo Frontend starting on http://localhost:3000
echo.
echo Close the opened terminal windows to stop the services.
