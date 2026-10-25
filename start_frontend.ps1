param([switch]$Install)
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot 'web_client')
if ($Install -or !(Test-Path node_modules)) {
    npm ci
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
npm run dev -- --host 127.0.0.1
