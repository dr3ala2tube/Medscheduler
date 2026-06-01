@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo MedScheduler - Windows Build Script
echo.

REM 1) Find Python
set "PYTHON=py"
%PYTHON% -3.11 -c "import sys" >nul 2>&1 && set "PYTHON=py -3.11"
if errorlevel 1 (
  py -3 -c "import sys" >nul 2>&1 && set "PYTHON=py -3"
)
if errorlevel 1 (
  python -c "import sys" >nul 2>&1 && set "PYTHON=python"
)

%PYTHON% -c "import sys, tkinter; print(sys.version)" >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python with tkinter was not found.
  echo Install the official Windows Python from https://www.python.org/downloads/windows/
  echo Make sure 'tcl/tk and IDLE' is selected during installation.
  pause
  exit /b 1
)

echo [OK] Python detected.

REM 2) Create venv
if not exist ".venv_win_build" (
  echo [INFO] Creating virtual environment...
  %PYTHON% -m venv .venv_win_build
  if errorlevel 1 goto :fail
)

set "VENV_PY=.venv_win_build\Scripts\python.exe"
set "VENV_PIP=.venv_win_build\Scripts\pip.exe"

REM 3) Install dependencies
 echo [INFO] Upgrading pip...
%VENV_PY% -m pip install --upgrade pip
if errorlevel 1 goto :fail

echo [INFO] Installing build dependencies...
%VENV_PIP% install -r requirements.txt
if errorlevel 1 goto :fail

REM 4) Clean previous build
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM 5) Build
 echo [INFO] Running PyInstaller...
%VENV_PY% -m PyInstaller --noconfirm --clean MedScheduler_windows.spec
if errorlevel 1 goto :fail

if exist "dist\MedScheduler\MedScheduler.exe" (
  echo.
  echo [OK] Build complete:
  echo     %CD%\dist\MedScheduler\MedScheduler.exe
  explorer "%CD%\dist\MedScheduler"
  exit /b 0
)

if exist "dist\MedScheduler.exe" (
  echo.
  echo [OK] Build complete:
  echo     %CD%\dist\MedScheduler.exe
  explorer "%CD%\dist"
  exit /b 0
)

echo ERROR: Build finished but the EXE was not found.
pause
exit /b 1

:fail
echo.
echo Build failed.
pause
exit /b 1
