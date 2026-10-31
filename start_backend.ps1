param([switch]$Install)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if ($Install) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & .\.venv\Scripts\python.exe -m pip install -r api_core/requirements.txt
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
if (!(Test-Path .venv/Scripts/python.exe)) { throw 'Run: .\start_backend.ps1 -Install' }
if (!(Test-Path .env)) { throw 'Copy .env.example to .env; configure Supabase and secrets.' }
& .\.venv\Scripts\python.exe connect_database.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& .\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
