@echo off
setlocal

cd /d "%~dp0"

set "VENV_PY=.venv\Scripts\python.exe"
set "PIP_MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple"
set "PIP_TIMEOUT=60"
set "PIP_RETRIES=5"

if not exist "requirements.txt" (
    echo requirements.txt not found.
    echo Please run this script from the AI Test Copilot project root.
    pause
    exit /b 1
)

if not exist "%VENV_PY%" (
    echo Creating local Python virtual environment...
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -m venv .venv
    ) else (
        where python >nul 2>nul
        if errorlevel 1 (
            echo Python was not found. Please install Python 3.11+ first.
            pause
            exit /b 1
        )
        python -m venv .venv
    )
)

echo Installing dependencies with Tsinghua mirror...
"%VENV_PY%" -m pip install --upgrade pip setuptools wheel -i %PIP_MIRROR% --timeout %PIP_TIMEOUT% --retries %PIP_RETRIES%
"%VENV_PY%" -m pip install -r requirements.txt -i %PIP_MIRROR% --timeout %PIP_TIMEOUT% --retries %PIP_RETRIES%

if errorlevel 1 (
    echo.
    echo Install failed. Please check your network, then run this script again.
    pause
    exit /b 1
)

echo.
echo Dependencies installed successfully.
echo Now you can run start.bat.
pause
