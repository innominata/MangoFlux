@echo off
setlocal
set "ROOT=%~dp0"
set "APPDATA_DIR=%LOCALAPPDATA%\MangoFlux"
set "PY=%APPDATA_DIR%\python\python.exe"
if exist "%PY%" goto run
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%bootstrap.ps1"
if errorlevel 1 (echo Setup failed. Please see the message above. & pause & exit /b 1)
:run
start "" "%APPDATA_DIR%\python\pythonw.exe" "%ROOT%app.py"
