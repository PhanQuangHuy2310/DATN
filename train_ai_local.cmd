@echo off
rem Huan luyen lai AI cua EAS. Tham so: xem scripts\train_ai.ps1 (vd: -Only nlp, -RebuildPublicData, -CheckOnly)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\train_ai.ps1" %*
exit /b %ERRORLEVEL%
