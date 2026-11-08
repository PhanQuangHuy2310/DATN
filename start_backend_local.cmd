@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Install backend: py -3.12 -m venv .venv ^& .venv\Scripts\python.exe -m pip install -r api_core\requirements.txt & exit /b 2)
if not exist ".env" (echo Copy .env.example to .env and configure it first. & exit /b 2)
REM Fail early with an actionable Redis error instead of repeating API 503s.
".venv\Scripts\python.exe" -m scripts.check_cache_local
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" connect_database.py
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000
