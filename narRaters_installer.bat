@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title narRaters setup

echo ==========================================
echo narRaters setup (Windows)
echo ==========================================
echo Project folder:
echo   %cd%
echo.

call "%~dp0scripts\finish_windows_setup.bat"
if errorlevel 1 (
  echo.
  echo Install failed. See messages above.
  pause
  exit /b 1
)

echo.
echo To open narRaters, double-click:  narRaters_launch.bat
echo Or run:  .venv\Scripts\narraters serve
echo.
set /p OPEN="Open narRaters now? [Y/n] "
if /i "%OPEN%"=="n" goto :done
if /i "%OPEN%"=="N" goto :done
call "%~dp0narRaters_launch.bat"
goto :eof

:done
pause
exit /b 0
