@echo off
cd /d "%~dp0"
if not exist ".env.database" copy ".env.database.example" ".env.database" >nul
if not exist "ai_service\.env" copy "ai_service\.env.example" "ai_service\.env" >nul
if not exist ".env.worker" copy ".env.worker.example" ".env.worker" >nul
echo Local env files prepared, existing files kept.
echo Edit .env.database, ai_service\.env and optional .env.worker, using NEW secrets.
echo Python 3.12 Django; Python 3.11 AI; Node.js >= 22.12 Vite.
