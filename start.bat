@echo off
setlocal

cd /d "%~dp0"

set BACKEND_PORT=8000
set FRONTEND_PORT=8501
set BACKEND_URL=http://127.0.0.1:%BACKEND_PORT%

if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo Created .env from .env.example
    echo Please edit .env and set your API key before generating test cases.
)

powershell -NoProfile -Command "if ((Test-NetConnection -ComputerName 127.0.0.1 -Port %BACKEND_PORT% -InformationLevel Quiet)) { exit 1 }"
if errorlevel 1 (
    echo Port %BACKEND_PORT% is already in use. Please close the existing backend or edit BACKEND_PORT in start.bat.
    exit /b 1
)

powershell -NoProfile -Command "if ((Test-NetConnection -ComputerName 127.0.0.1 -Port %FRONTEND_PORT% -InformationLevel Quiet)) { exit 1 }"
if errorlevel 1 (
    echo Port %FRONTEND_PORT% is already in use. Please close the existing frontend or edit FRONTEND_PORT in start.bat.
    exit /b 1
)

echo Starting AI Test Copilot backend...
start "AI Test Copilot Backend" /D "%~dp0" cmd /k uvicorn backend.main:app --host 127.0.0.1 --port %BACKEND_PORT% --reload

powershell -NoProfile -Command "Start-Sleep -Seconds 3" >nul

echo Starting AI Test Copilot frontend...
start "AI Test Copilot Frontend" /D "%~dp0" cmd /k "set BACKEND_URL=%BACKEND_URL%&& streamlit run frontend/app.py --server.address 127.0.0.1 --server.port %FRONTEND_PORT%"

echo.
echo Backend:  %BACKEND_URL%
echo Frontend: http://127.0.0.1:%FRONTEND_PORT%
echo.
echo If generation fails, check .env and make sure DEEPSEEK_API_KEY or OPENAI_API_KEY is set.
