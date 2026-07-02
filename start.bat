@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

set "BACKEND_PORT=8000"
set "FRONTEND_PORT=8501"
set "BACKEND_URL=http://127.0.0.1:%BACKEND_PORT%"
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

if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo Created .env from .env.example
    echo Please edit .env and set your API key before generating test cases.
    echo.
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
    if errorlevel 1 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo Installing or checking dependencies...
"%VENV_PY%" -m pip install --upgrade pip setuptools wheel -i %PIP_MIRROR% --timeout %PIP_TIMEOUT% --retries %PIP_RETRIES%
"%VENV_PY%" -m pip install -r requirements.txt -i %PIP_MIRROR% --timeout %PIP_TIMEOUT% --retries %PIP_RETRIES%
if errorlevel 1 (
    echo.
    echo Tsinghua mirror install failed. Retrying with default PyPI...
    "%VENV_PY%" -m pip install -r requirements.txt --timeout %PIP_TIMEOUT% --retries %PIP_RETRIES%
    if errorlevel 1 (
        echo Dependency installation failed. Please check your network or pip mirror.
        pause
        exit /b 1
    )
)

powershell -NoProfile -Command "if ((Test-NetConnection -ComputerName 127.0.0.1 -Port %BACKEND_PORT% -InformationLevel Quiet)) { exit 1 }"
if errorlevel 1 (
    echo Port %BACKEND_PORT% is already in use. Please close the existing backend or edit BACKEND_PORT in start.bat.
    pause
    exit /b 1
)

powershell -NoProfile -Command "if ((Test-NetConnection -ComputerName 127.0.0.1 -Port %FRONTEND_PORT% -InformationLevel Quiet)) { exit 1 }"
if errorlevel 1 (
    echo Port %FRONTEND_PORT% is already in use. Please close the existing frontend or edit FRONTEND_PORT in start.bat.
    pause
    exit /b 1
)

echo Starting AI Test Copilot backend...
start "AI Test Copilot Backend" /D "%~dp0" "%CD%\%VENV_PY%" -m uvicorn backend.main:app --host 127.0.0.1 --port %BACKEND_PORT% --reload

powershell -NoProfile -Command "Start-Sleep -Seconds 3" >nul

echo Starting AI Test Copilot frontend...
start "AI Test Copilot Frontend" /D "%~dp0" "%CD%\%VENV_PY%" -m streamlit run frontend/app.py --server.address 127.0.0.1 --server.port %FRONTEND_PORT%

echo.
echo Backend:  %BACKEND_URL%
echo Frontend: http://127.0.0.1:%FRONTEND_PORT%
echo.
echo If generation fails, check .env and make sure DEEPSEEK_API_KEY or OPENAI_API_KEY is set.
echo You can close the backend/frontend command windows to stop the app.
pause
