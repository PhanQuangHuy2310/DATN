param([switch]$Install)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if ($Install) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & .\.venv\Scripts\python.exe -m pip install -r api_core/requirements.txt
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
if (!(Test-Path .venv/Scripts/python.exe)) { throw 'Run: .\start_backend.ps1 -Install' }
if (!(Test-Path .env.database)) {
    Copy-Item .env.database.example .env.database
    Write-Host 'Created .env.database. Fill database credentials and run this script again.'
    exit 1
}
& .\.venv\Scripts\python.exe connect_database.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& .\.venv\Scripts\python.exe connect_database.py --runserver
