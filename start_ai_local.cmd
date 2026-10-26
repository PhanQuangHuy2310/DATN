@echo off
cd /d "%~dp0ai_service"
if not exist ".venv-ai\Scripts\python.exe" (echo Install AI: py -3.11 -m venv .venv-ai then install requirements-local.txt & exit /b 2)
if not exist ".env" (echo Run setup_local.cmd and set same INTERNAL_API_SECRET as Django. & exit /b 2)
".venv-ai\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8001 --reload
