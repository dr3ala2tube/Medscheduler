@echo off
setlocal
cd /d "%~dp0"

echo.
echo Launching MedScheduler on Windows...
echo.

set "PYTHON=py"
%PYTHON% -3.11 -c "import sys" >nul 2>&1 && set "PYTHON=py -3.11"
if errorlevel 1 (
  py -3 -c "import sys" >nul 2>&1 && set "PYTHON=py -3"
)
if errorlevel 1 (
  python -c "import sys" >nul 2>&1 && set "PYTHON=python"
)

%PYTHON% -c "import sys, tkinter" >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python with tkinter was not found.
  echo Install the official Windows Python from https://www.python.org/downloads/windows/
  pause
  exit /b 1
)

if not exist ".venv_win_run" (
  echo [INFO] Creating virtual environment...
  %PYTHON% -m venv .venv_win_run
  if errorlevel 1 goto :fail
)

set "VENV_PY=.venv_win_run\Scripts\python.exe"
set "VENV_PIP=.venv_win_run\Scripts\pip.exe"

%VENV_PY% -c "import openpyxl" >nul 2>&1
if errorlevel 1 (
  echo [INFO] Installing dependencies...
  %VENV_PY% -m pip install --upgrade pip
  %VENV_PIP% install openpyxl
  if errorlevel 1 goto :fail
)

%VENV_PY% medscheduler_refactored.py
exit /b %errorlevel%

:fail
echo.
echo Launch failed.
pause
exit /b 1
