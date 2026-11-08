@echo off
cd /d "%~dp0"
if not exist ".env" (echo Copy .env.example to .env and configure it first. & exit /b 2)
if not exist "ai_service\.venv-ai\Scripts\python.exe" (echo Create ai_service\.venv-ai and install ai_service\requirements-local.txt & exit /b 2)
set "PYTHONPATH=%CD%"
cd ai_service
REM Catch invalid .env bool/int fields before uvicorn starts a child process.
".venv-ai\Scripts\python.exe" check_config_local.py
if errorlevel 1 exit /b 1
".venv-ai\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8001 --reload
