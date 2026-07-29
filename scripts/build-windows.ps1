# Assemble Windows package + Inno Setup installer.
# Run from repo root:  powershell -File scripts/build-windows.ps1
param(
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

if (-not $Version) {
    $Version = (Get-Content -Raw (Join-Path $Root "VERSION")).Trim()
}
if (-not $Version) { $Version = "0.0.1" }

$Dist = Join-Path $Root "dist"
$Stage = Join-Path $Dist "windows-stage"
$AppDir = Join-Path $Stage "CloudMount"
$OutZip = Join-Path $Dist "CloudMount-$Version-windows.zip"
$OutSetup = Join-Path $Dist "CloudMount-$Version-windows-setup.exe"

Write-Host "Building CloudMount Windows v$Version"
if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
New-Item -ItemType Directory -Force -Path $AppDir | Out-Null

# App payload
$CopyDirs = @("bin", "core", "gui", "scripts", "docs")
foreach ($d in $CopyDirs) {
    $src = Join-Path $Root $d
    if (Test-Path $src) {
        Copy-Item -Recurse -Force $src (Join-Path $AppDir $d)
    }
}
foreach ($f in @("LICENSE", "README.md", "VERSION", "requirements-windows.txt")) {
    $src = Join-Path $Root $f
    if (Test-Path $src) { Copy-Item -Force $src (Join-Path $AppDir $f) }
}

# Strip junk
Get-ChildItem -Recurse -Directory -Filter "__pycache__" $AppDir | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Recurse -Filter "*.pyc" $AppDir | Remove-Item -Force -ErrorAction SilentlyContinue

# Root launchers (install root = AppDir)
@'
@echo off
setlocal
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
cd /d "%ROOT%"
set "PYTHONPATH=%ROOT%;%PYTHONPATH%"

where python >nul 2>&1
if errorlevel 1 (
  where py >nul 2>&1
  if errorlevel 1 (
    echo Python 3 not found. Install from https://www.python.org/downloads/ and enable "Add to PATH".
    start https://www.python.org/downloads/
    pause
    exit /b 1
  )
  set "PY=py -3"
) else (
  set "PY=python"
)

%PY% -c "import pystray, PIL" 2>nul
if errorlevel 1 (
  echo Installing tray dependencies...
  %PY% -m pip install --user -r "%ROOT%\requirements-windows.txt"
)

start "CloudMount" /B %PY% "%ROOT%\bin\cloudmount" tray
endlocal
'@ | Set-Content -Encoding ASCII (Join-Path $AppDir "CloudMount-Tray.bat")

@'
@echo off
setlocal
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
cd /d "%ROOT%"
set "PYTHONPATH=%ROOT%;%PYTHONPATH%"

where python >nul 2>&1
if errorlevel 1 (
  where py >nul 2>&1
  if errorlevel 1 (
    echo Python 3 not found. Install from https://www.python.org/downloads/
    start https://www.python.org/downloads/
    pause
    exit /b 1
  )
  set "PY=py -3"
) else (
  set "PY=python"
)

%PY% "%ROOT%\bin\cloudmount" gui
endlocal
'@ | Set-Content -Encoding ASCII (Join-Path $AppDir "CloudMount-UI.bat")

@'
@echo off
setlocal
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
cd /d "%ROOT%"
set "PYTHONPATH=%ROOT%;%PYTHONPATH%"

echo CloudMount first-run setup
echo.

where python >nul 2>&1
if errorlevel 1 (
  where py >nul 2>&1
  if errorlevel 1 (
    echo [!] Python 3 is required: https://www.python.org/downloads/
    start https://www.python.org/downloads/
    pause
    exit /b 1
  )
  set "PY=py -3"
) else (
  set "PY=python"
)

echo Installing Python deps (pystray, Pillow)...
%PY% -m pip install --user -r "%ROOT%\requirements-windows.txt"
if errorlevel 1 (
  echo pip install failed
  pause
  exit /b 1
)

echo.
echo Running CloudMount setup (downloads rclone)...
%PY% "%ROOT%\bin\cloudmount" setup
echo.
echo IMPORTANT: Install WinFsp for mounts: https://winfsp.dev/rel/
echo.
echo Starting system tray...
start "CloudMount" /B %PY% "%ROOT%\bin\cloudmount" tray
echo Done. Look for the CloudMount icon in the notification area.
pause
endlocal
'@ | Set-Content -Encoding ASCII (Join-Path $AppDir "First-Run-Setup.bat")

@'
CloudMount for Windows
======================

Requirements:
  1. Python 3.10+  https://www.python.org/downloads/  (enable Add to PATH)
  2. WinFsp        https://winfsp.dev/rel/

Quick start:
  1. Run First-Run-Setup.bat  (once)
  2. Or CloudMount-Tray.bat for the system tray (SwiftBar-style menu)
  3. CloudMount-UI.bat opens the browser UI

Docs: https://github.com/arthurtsang/CloudMount/blob/main/docs/WINDOWS.md
'@ | Set-Content -Encoding UTF8 (Join-Path $AppDir "README-Windows.txt")

# Zip portable package
if (Test-Path $OutZip) { Remove-Item -Force $OutZip }
Compress-Archive -Path $AppDir -DestinationPath $OutZip -Force
Write-Host "ZIP: $OutZip"

# Inno Setup compiler
$Iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $Iscc) {
    Write-Warning "Inno Setup not found — installer EXE skipped (zip still built)."
    Write-Host $OutZip
    exit 0
}

$Iss = Join-Path $Root "packaging\windows\CloudMount.iss"
if (-not (Test-Path $Iss)) {
    throw "Missing $Iss"
}

# Pass defines to ISCC
& $Iscc `
    "/DMyAppVersion=$Version" `
    "/DMyAppSource=$AppDir" `
    "/DMyOutputDir=$Dist" `
    "/DMyOutputBase=CloudMount-$Version-windows-setup" `
    $Iss

if (-not (Test-Path $OutSetup)) {
    # Inno may use OutputBaseFilename without path quirks
    $found = Get-ChildItem $Dist -Filter "CloudMount-*-windows-setup.exe" | Select-Object -First 1
    if ($found) {
        if ($found.FullName -ne $OutSetup) {
            Move-Item -Force $found.FullName $OutSetup
        }
    }
}

if (Test-Path $OutSetup) {
    Write-Host "SETUP: $OutSetup"
} else {
    Write-Warning "Setup EXE not produced"
}

Get-ChildItem $Dist -Filter "CloudMount-$Version-windows*" | Format-Table Name, Length
