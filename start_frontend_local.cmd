@echo off
cd /d "%~dp0web_client"
if not exist "node_modules" (call npm ci || exit /b 1)
call npm run dev -- --host 127.0.0.1
