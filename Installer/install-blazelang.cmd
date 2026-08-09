@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-BlazeLang.ps1"
if errorlevel 1 exit /b 1
echo BlazeLang installation completed.
