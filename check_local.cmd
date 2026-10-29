@echo off
cd /d "%~dp0"
set "PY_EXE=.venv\Scripts\python.exe"
if not exist "%PY_EXE%" set "PY_EXE=python"
"%PY_EXE%" check_eas_connections_local.py %*
exit /b %ERRORLEVEL%
