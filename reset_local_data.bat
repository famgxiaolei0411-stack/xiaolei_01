@echo off
setlocal

cd /d "%~dp0"

echo This will delete local database, uploaded files, exported files, and generated test projects.
set /p CONFIRM=Type RESET to continue: 
if not "%CONFIRM%"=="RESET" (
    echo Canceled.
    exit /b 0
)

if exist "aitest.db" del /f /q "aitest.db"
if exist "aitest.db-shm" del /f /q "aitest.db-shm"
if exist "aitest.db-wal" del /f /q "aitest.db-wal"

for %%D in (uploads outputs generated_tests allure-results allure-report .pytest_tmp .run_logs) do (
    if exist "%%D" (
        for /f "delims=" %%F in ('dir /a /b "%%D" 2^>nul') do (
            if /i not "%%F"==".gitkeep" (
                if exist "%%D\%%F\*" (
                    rmdir /s /q "%%D\%%F"
                ) else (
                    del /f /q "%%D\%%F"
                )
            )
        )
    )
)

echo Local data has been reset.
