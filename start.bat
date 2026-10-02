@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [.venv not found]
    echo Run setup from README first:
    echo   py -3.12 -m venv .venv
    echo   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

if not exist ".env" (
    echo [.env not found]
    echo Run: copy .env.example .env
    echo Then fill HEEDS_EXE and HEEDS_PROJECT_PATH in .env
    echo Azure OpenAI settings are optional and only used for result summaries.
    echo.
    pause
    exit /b 1
)

echo Starting... Press Ctrl+C in this window to stop.
echo Browser: http://localhost:8000
echo.
".venv\Scripts\python.exe" run_app.py
set EXITCODE=%ERRORLEVEL%

echo.
if not "%EXITCODE%"=="0" (
    echo Exit code: %EXITCODE%
)
pause
exit /b %EXITCODE%
