@echo off
chcp 65001 >nul
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0update_database.ps1"

if errorlevel 1 (
    echo.
    echo Database update failed.
)

echo.
pause
