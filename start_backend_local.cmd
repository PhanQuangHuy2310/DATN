@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Install backend: py -3.12 -m venv .venv ^& .venv\Scripts\python.exe -m pip install -r api_core\requirements.txt & exit /b 2)
if not exist ".env" (echo Copy .env.example to .env and configure it first. & exit /b 2)
".venv\Scripts\python.exe" connect_database.py
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000
