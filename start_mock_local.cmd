@echo off
rem Mock Systems API: simulated external systems (HRM, assets, facilities, ITSM, ERP...).
rem Uses EAS_MOCK_DATABASE_URL (role eas_mock_login) and EAS_MOCK_API_SECRET from .env.
rem See docs/TICH_HOP_HE_THONG_NGOAI.md. Must run alongside the backend and worker.
cd /d "%~dp0"
set "PY_EXE=.venv\Scripts\python.exe"
if not exist "%PY_EXE%" set "PY_EXE=python"
if not exist ".env" (echo Copy .env.example to .env and configure it first. & exit /b 2)
findstr /b "EAS_MOCK_DATABASE_URL=" .env >nul || (echo Missing EAS_MOCK_DATABASE_URL in .env - see README, muc "Chay toan bo du an". & exit /b 2)
set "EAS_SERVICE=mock"
"%PY_EXE%" manage.py runserver 127.0.0.1:8100 --noreload
