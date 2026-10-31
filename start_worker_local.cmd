@echo off
cd /d "%~dp0"
if not exist ".env" (echo Configure .env first. & exit /b 2)
".venv\Scripts\python.exe" run_worker_local.py %*
