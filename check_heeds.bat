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
    echo Then fill HEEDS_EXE and HEEDS_PROJECT_PATH
    echo.
    pause
    exit /b 1
)

echo Checking names against HEEDS. Analysis is not run.
echo.
".venv\Scripts\python.exe" check_heeds_project.py %*
set EXITCODE=%ERRORLEVEL%

echo.
if not "%EXITCODE%"=="0" (
    echo Check failed.
) else (
    echo Check passed.
)
pause
exit /b %EXITCODE%
