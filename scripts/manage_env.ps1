[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("init", "validate", "status", "validate-templates")]
    [string]$Action = "status"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$CanonicalEnv = Join-Path $ProjectRoot ".env"
$CanonicalTemplate = Join-Path $ProjectRoot ".env.example"
$Validator = Join-Path $PSScriptRoot "validate_env.py"

function Get-PythonCommand {
    $VirtualEnvironmentPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $VirtualEnvironmentPython) {
        return $VirtualEnvironmentPython
    }
    $Command = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $Command) {
        throw "Python was not found. Install Python 3.12+ or create .venv first."
    }
    return $Command.Source
}

function Invoke-Validation {
    param(
        [Parameter(Mandatory = $true)][string]$File,
        [Parameter(Mandatory = $true)][string]$Profile,
        [switch]$AllowPlaceholders
    )

    $Arguments = @($Validator, "--file", $File, "--profile", $Profile)
    if ($AllowPlaceholders) {
        $Arguments += "--allow-placeholders"
    }
    & (Get-PythonCommand) @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Environment validation failed. No secret values were printed."
    }
}

Push-Location $ProjectRoot
try {
    switch ($Action) {
        "init" {
            if (Test-Path -LiteralPath $CanonicalEnv) {
                Write-Host ".env already exists; refusing to overwrite local credentials."
                exit 0
            }
            Copy-Item -LiteralPath $CanonicalTemplate -Destination $CanonicalEnv
            Write-Host "Created .env from .env.example. Replace placeholders, then run:"
            Write-Host "  .\scripts\manage_env.ps1 validate"
        }
        "validate" {
            if (-not (Test-Path -LiteralPath $CanonicalEnv)) {
                throw ".env does not exist. Run '.\scripts\manage_env.ps1 init' first."
            }
            Invoke-Validation -File $CanonicalEnv -Profile "compose"
        }
        "validate-templates" {
            Invoke-Validation -File $CanonicalTemplate -Profile "compose" -AllowPlaceholders
            Invoke-Validation -File "api_core/.env.example" -Profile "api" -AllowPlaceholders
            Invoke-Validation -File "api_core/.env.worker.example" -Profile "worker" -AllowPlaceholders
            Invoke-Validation -File "web_client/.env.example" -Profile "web" -AllowPlaceholders
            Invoke-Validation -File "web_admin/.env.example" -Profile "web" -AllowPlaceholders
        }
        "status" {
            Write-Host "Canonical Compose environment: .env"
            Write-Host "Template:                     .env.example"
            Write-Host "Secret values:                hidden"
            if (Test-Path -LiteralPath $CanonicalEnv) {
                Write-Host "Local .env:                   present (ignored by Git)"
                try {
                    Invoke-Validation -File $CanonicalEnv -Profile "compose"
                }
                catch {
                    Write-Warning "Local .env is present but not ready. Run validate after replacing placeholders."
                    exit 1
                }
            }
            else {
                Write-Warning "Local .env is missing. Run '.\scripts\manage_env.ps1 init'."
                exit 1
            }
        }
    }
}
finally {
    Pop-Location
}
