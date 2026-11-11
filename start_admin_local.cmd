@echo off
cd /d "%~dp0web_admin"
if not exist "node_modules" (call npm install || exit /b 1)
call npm run dev
