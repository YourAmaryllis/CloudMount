@echo off
REM System tray launcher for CloudMount (Windows)
setlocal
set "ROOT=%~dp0.."
cd /d "%ROOT%"
set "PYTHONPATH=%ROOT%;%PYTHONPATH%"

where python >nul 2>&1
if errorlevel 1 (
  where py >nul 2>&1
  if errorlevel 1 (
    echo Python not found. Install Python 3 from https://www.python.org/downloads/
    pause
    exit /b 1
  )
  py -3 -c "import pystray, PIL" 2>nul
  if errorlevel 1 (
    echo Installing tray dependencies...
    py -3 -m pip install --user pystray Pillow
  )
  start "CloudMount" /B py -3 "%ROOT%\bin\cloudmount" tray
  exit /b 0
)

python -c "import pystray, PIL" 2>nul
if errorlevel 1 (
  echo Installing tray dependencies...
  python -m pip install --user pystray Pillow
)
start "CloudMount" /B python "%ROOT%\bin\cloudmount" tray
endlocal
