@echo off
setlocal

cd /d "%~dp0"

set VENV_PATH=
if exist "..\.venv\Scripts\activate.bat" (
    set VENV_PATH=..\.venv
) else if exist ".venv\Scripts\activate.bat" (
    set VENV_PATH=.venv
)

if defined VENV_PATH (
    call "%VENV_PATH%\Scripts\activate.bat"
)

python smoke_test.py
set EXIT_CODE=%ERRORLEVEL%

if %EXIT_CODE% EQU 0 (
    echo.
    echo [OK] Full smoke test passed.
) else (
    echo.
    echo [ERROR] Full smoke test failed.
)

exit /b %EXIT_CODE%
