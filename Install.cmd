@echo off
rem ---------------------------------------------------------------------------
rem  Ireland Health Evidence -- one-click setup for Windows.
rem
rem  Double-click this file. It needs no administrator rights.
rem
rem  This exists so that a non-technical user never has to open a terminal or
rem  type anything: -ExecutionPolicy Bypass is scoped to this one child process,
rem  so it changes no machine setting and needs no elevation.
rem ---------------------------------------------------------------------------

title Ireland Health Evidence - Setup
cd /d "%~dp0"

if not exist "%~dp0scripts\install.ps1" (
    echo.
    echo   ERROR: scripts\install.ps1 is missing.
    echo.
    echo   This file has to stay inside the project folder. If you unzipped
    echo   only this one file, unzip the whole folder again and run it from
    echo   there.
    echo.
    pause
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1" %*
set EXITCODE=%ERRORLEVEL%

echo.
if %EXITCODE% NEQ 0 (
    echo   Setup did not finish. The error is above.
) else (
    echo   You can close this window.
)
echo.
pause
exit /b %EXITCODE%
