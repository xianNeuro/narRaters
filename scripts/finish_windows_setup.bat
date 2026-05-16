@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."
set "ROOT=%cd%"

title narRaters setup

set "PYEXE="
py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 set "PYEXE=py -3"
if not defined PYEXE (
  python3 --version >nul 2>&1
  if not errorlevel 1 set "PYEXE=python3"
)
if not defined PYEXE (
  python --version >nul 2>&1
  if not errorlevel 1 set "PYEXE=python"
)

if not defined PYEXE (
  echo Python 3 was not found.
  echo Install from https://www.python.org/downloads/ and enable "Add python.exe to PATH".
  exit /b 1
)

set "VENV_PY=%ROOT%\.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
  echo Creating virtual environment .venv\
  %PYEXE% -m venv "%ROOT%\.venv"
  if errorlevel 1 (
    echo Failed to create .venv
    exit /b 1
  )
)

echo Upgrading pip...
"%VENV_PY%" -m pip install -U pip wheel
if errorlevel 1 exit /b 1

echo Installing narRaters into .venv...
"%VENV_PY%" -m pip install -e "%ROOT%"
if errorlevel 1 exit /b 1

echo.
echo Setup complete.
exit /b 0
