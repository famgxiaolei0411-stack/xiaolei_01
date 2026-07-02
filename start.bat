@echo off
setlocal

cd /d "%~dp0"

where py >nul 2>nul
if not errorlevel 1 (
    py -3 start.py
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python was not found. Please install Python 3.11+ first.
        pause
        exit /b 1
    )
    python start.py
)

if errorlevel 1 (
    echo.
    echo Startup failed. Run doctor.py for diagnostics.
    pause
    exit /b 1
)
