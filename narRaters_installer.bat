@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title narRaters setup

set "PYEXE="
py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 set "PYEXE=py -3"

if not defined PYEXE (
  python --version >nul 2>&1
  if not errorlevel 1 set "PYEXE=python"
)

if not defined PYEXE (
  msg * "Python 3 was not found. Install from https://www.python.org/downloads/ (enable Add python.exe to PATH), then double-click narRaters_installer.bat again."
  exit /b 1
)

echo Installing narRaters in:
echo   %cd%
echo   (creates .venv\ if needed)
echo.

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment .venv\
  %PYEXE% -m venv .venv
  if errorlevel 1 (
    echo Failed to create .venv
    pause
    exit /b 1
  )
)

.venv\Scripts\python.exe -m pip install -U pip wheel
.venv\Scripts\python.exe -m pip install -e "%cd%"
if errorlevel 1 (
  echo.
  echo Install failed. See messages above.
  pause
  exit /b 1
)

echo.
echo Done. To start the app:  .venv\Scripts\narraters serve
echo Or see README for START_HERE.
echo.
pause
exit /b 0
