@echo off
cd /d "%~dp0"
if not exist ".env" copy ".env.example" ".env" >nul
echo Edit the single .env at the repository root before starting any service.
echo The .env is server-only. Never add secrets to VITE_ variables.
