param(
    [string]$BaseUrl = "http://127.0.0.1:18080",
    [string]$ProjectRef = "emnusiybdkpibtqsplta"
)

$ErrorActionPreference = "Stop"
$randomBytes = New-Object byte[] 32
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($randomBytes) } finally { $rng.Dispose() }
$env:EAS_E2E_PASSWORD = ([Convert]::ToBase64String($randomBytes) -replace '[+/=]', 'X') + "aA1!"
$env:EAS_E2E_USERNAME = "demo_requester"
$env:EAS_E2E_EXTERNAL = "true"
$env:EAS_E2E_BASE_URL = $BaseUrl
$enabled = $false

try {
    docker exec -e EAS_E2E_PASSWORD eas-api-1 python manage.py configure_e2e_user enable --confirm-project $ProjectRef
    if ($LASTEXITCODE -ne 0) { throw "Could not enable the E2E fixture account." }
    $enabled = $true
    Push-Location (Join-Path $PSScriptRoot "..\web_client")
    try {
        npm run e2e
        if ($LASTEXITCODE -ne 0) { throw "Playwright E2E suite failed." }
    }
    finally {
        Pop-Location
    }
}
finally {
    if ($enabled) {
        docker exec eas-api-1 python manage.py configure_e2e_user disable --confirm-project $ProjectRef
        if ($LASTEXITCODE -ne 0) { Write-Error "CRITICAL: E2E account cleanup failed." }
    }
    Remove-Item Env:EAS_E2E_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:EAS_E2E_USERNAME -ErrorAction SilentlyContinue
    Remove-Item Env:EAS_E2E_EXTERNAL -ErrorAction SilentlyContinue
    Remove-Item Env:EAS_E2E_BASE_URL -ErrorAction SilentlyContinue
}
