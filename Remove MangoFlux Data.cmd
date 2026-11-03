@echo off
setlocal
set "TARGET=%LOCALAPPDATA%\MangoFlux"
echo This removes the MangoFlux private runtime, model, download cache, and last preview:
echo %TARGET%
echo Close MangoFlux before continuing.
choice /C YN /M "Remove these files"
if errorlevel 2 exit /b
if not exist "%TARGET%" exit /b
rmdir /s /q "%TARGET%"
if exist "%TARGET%" (echo Some files could not be removed. Close the app and try again. & pause & exit /b 1)
echo MangoFlux data removed.
pause
