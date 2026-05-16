@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "ROOT=%cd%"
set "VENV_PY=%ROOT%\.venv\Scripts\python.exe"
set "SERVER=%ROOT%\server\web-interface.py"

if not exist "%VENV_PY%" (
  echo First-time setup required...
  call "%ROOT%\narRaters_installer.bat"
  if errorlevel 1 exit /b 1
)

if not exist "%SERVER%" (
  echo Missing server\web-interface.py in %ROOT%
  pause
  exit /b 1
)

"%VENV_PY%" -c "import flask" >nul 2>&1
if errorlevel 1 (
  echo Dependencies missing. Running installer...
  call "%ROOT%\narRaters_installer.bat"
  if errorlevel 1 exit /b 1
)

echo Starting narRaters at http://127.0.0.1:5000/pipeline-config
start "" "http://127.0.0.1:5000/pipeline-config"
cd /d "%ROOT%\server"
"%VENV_PY%" web-interface.py
pause
