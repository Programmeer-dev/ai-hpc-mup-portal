@echo off
REM AI-HPC Gateway MUP Asistent - Run Script
echo ===========================================
echo    AI-HPC Gateway - MUP Asistent
echo ===========================================
echo.

cd /d "%~dp0"

REM Pokusaj da pronadjes venv - prvo u UIT projekat folderu, pa lokalno
set VENV_PATH=
if exist "..\.venv\Scripts\activate.bat" (
    set VENV_PATH=..\.venv
    echo [INFO] Pronadjen venv u UIT projekat folderu
) else if exist ".venv\Scripts\activate.bat" (
    set VENV_PATH=.venv
    echo [INFO] Pronadjen lokalni venv
) else (
    echo [WARNING] Virtualni environment nije pronadjen, koristim globalni Python...
)

REM Ako postoji venv, aktiviraj ga
if defined VENV_PATH (
    echo [INFO] Aktiviram virtualni environment...
    call "%VENV_PATH%\Scripts\activate.bat"
)

REM Provjeri pip i upgrade
python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python nije instaliran ili nije u PATH!
    pause
    exit /b 1
)

REM Provjeri da li je streamlit instaliran
python -c "import streamlit" 2>nul
if errorlevel 1 (
    echo [INFO] Instaliram dependencies iz requirements.txt...
    pip install --upgrade pip
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Instalacija nije uspjela!
        pause
        exit /b 1
    )
)

echo.
echo [INFO] Pokrecem Streamlit aplikaciju...
echo.

REM Pokreni Streamlit
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
