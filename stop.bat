@echo off
echo Stopping VyceScore Backend and Frontend...
echo.

:: Kill uvicorn (backend)
taskkill /f /im uvicorn.exe 2>nul
if %errorlevel%==0 (
    echo Backend (uvicorn) stopped.
) else (
    echo No backend (uvicorn) process found.
)

:: Kill Python processes running on port 8000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /f /pid %%a 2>nul
    echo Killed process on port 8000 (PID: %%a)
)

:: Kill node processes running on port 3000 (Vite dev server)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
    taskkill /f /pid %%a 2>nul
    echo Killed process on port 3000 (PID: %%a)
)

echo.
echo All VyceScore processes stopped.
pause
