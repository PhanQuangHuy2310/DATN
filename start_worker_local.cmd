@echo off
cd /d "%~dp0"
if not exist ".env.worker" (echo Run setup_local.cmd and configure .env.worker & exit /b 2)
".venv\Scripts\python.exe" run_worker_local.py %*
