@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Backend venv missing. & exit /b 2)
".venv\Scripts\python.exe" check_eas_connections_local.py %*
exit /b %ERRORLEVEL%
