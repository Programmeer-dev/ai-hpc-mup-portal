@echo off
REM AI-HPC Gateway MUP Asistent - Run Script
echo ===========================================
echo    AI-HPC Gateway - MUP Asistent
echo ===========================================
echo.
echo Pokrecem Streamlit aplikaciju...
echo.

cd /d "%~dp0"

REM Pokusaj da aktiviras virtualni environment iz glavnog foldera
if exist "..\..\..\.venv\Scripts\activate.bat" (
    echo Aktiviram virtualni environment...
    call "..\..\..\.venv\Scripts\activate.bat"
)

REM Pokusaj sa python komandom
python -m streamlit run app.py

if errorlevel 1 (
    echo.
    echo [ERROR] Aplikacija se nije pokrenula uspjesno.
    echo Provjerite da li imate instalirane sve pakete:
    echo    pip install -r requirements.txt
    echo.
    echo Pritisnite bilo koji taster za izlaz...
    pause
) else (
    echo.
    echo Aplikacija je pokrenuta!
    echo Otvori browser na: http://localhost:8501
    echo.
    echo Pritisnite Ctrl+C da zaustavite aplikaciju
    pause
)
