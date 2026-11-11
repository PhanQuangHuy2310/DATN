@echo off
setlocal
cd /d "%~dp0.."
if not exist "web_client\package.json" (
  echo ERROR: Hay giai nen patch vao thu muc goc project DATN.
  exit /b 2
)
if not defined EAS_E2E_TEST_ENV (
  echo CHI THUC HIEN tren database/moi truong TEST, khong dung du lieu that.
  set /p EAS_E2E_TEST_ENV=Go YES de xac nhan dang dung moi truong TEST: 
)
if /I not "%EAS_E2E_TEST_ENV%"=="YES" exit /b 2
cd web_client
node e2e\trace_workflow_live.mjs
endlocal
