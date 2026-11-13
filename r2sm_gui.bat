@echo off
setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"

:: 1. Try Windows py launcher targeting Python 3.9+
for %%V in (3.14 3.13 3.12 3.11 3.10 3.9 3) do (
    py -%%V -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        start "" pyw -%%V "%SCRIPT_DIR%main.py" %*
        exit /b 0
    )
)

:: 2. Fall back to system pythonw / python if >= 3.9
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    start "" pythonw "%SCRIPT_DIR%main.py" %*
    exit /b 0
)

:: 3. Python is older than 3.9 or not in PATH; run main.py directly to show version dialog
python "%SCRIPT_DIR%main.py" %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo =======================================================================
    echo  ERROR: Python 3.9 or newer is required to run RDR2 Shader Tool.
    echo  Please install Python 3.9+ from https://www.python.org/downloads/
    echo =======================================================================
    echo.
    pause
)
