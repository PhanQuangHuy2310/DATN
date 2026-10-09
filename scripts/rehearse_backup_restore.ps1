param(
    [Parameter(Mandatory = $true)]
    [string]$SourceDatabaseUrl,
    [string]$PostgresBin = "C:\Program Files\PostgreSQL\18\bin"
)

$ErrorActionPreference = "Stop"
$containerName = "eas-restore-rehearsal-$PID"
$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$workDir = Join-Path $tempRoot $containerName
$dumpPath = Join-Path $workDir "enterprise-approval.dump"
$match = [regex]::Match(
    $SourceDatabaseUrl,
    '^(?:postgres|postgresql)://([^:]+):(.+)@(\[[^\]]+\]|[^:/?]+)(?::(\d+))?/([^?]+)(?:\?.*)?$'
)
if (-not $match.Success) {
    throw "SourceDatabaseUrl must be a PostgreSQL URL containing username and password."
}
$sourceUser = [Uri]::UnescapeDataString($match.Groups[1].Value)
$sourcePassword = [Uri]::UnescapeDataString($match.Groups[2].Value)
$sourceHost = $match.Groups[3].Value.Trim('[', ']')
$sourcePort = if ($match.Groups[4].Success) { [int]$match.Groups[4].Value } else { 5432 }
$sourceDatabase = [Uri]::UnescapeDataString($match.Groups[5].Value)
$pgDump = Join-Path $PostgresBin "pg_dump.exe"
$pgRestore = Join-Path $PostgresBin "pg_restore.exe"
$psql = Join-Path $PostgresBin "psql.exe"
foreach ($tool in @($pgDump, $pgRestore, $psql)) {
    if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) { throw "Required PostgreSQL tool is missing: $tool" }
}

$schemas = @(
    "eas", "mock_assets", "mock_crm", "mock_facilities", "mock_finance",
    "mock_hr", "mock_it", "mock_procurement", "mock_travel"
)
$schemaArgs = @()
foreach ($schema in $schemas) { $schemaArgs += "--schema=$schema" }
$restorePasswordBytes = New-Object byte[] 32
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($restorePasswordBytes) } finally { $rng.Dispose() }
$restorePassword = [Convert]::ToBase64String($restorePasswordBytes)
$containerStarted = $false

try {
    New-Item -ItemType Directory -Path $workDir -ErrorAction Stop | Out-Null
    $env:PGPASSWORD = $sourcePassword
    $env:PGSSLMODE = "require"
    $dumpWatch = [Diagnostics.Stopwatch]::StartNew()
    & $pgDump -h $sourceHost -p $sourcePort -U $sourceUser -d $sourceDatabase `
        --format=custom --compress=9 --no-owner --no-acl @schemaArgs --file=$dumpPath
    if ($LASTEXITCODE -ne 0) { throw "pg_dump failed." }
    $dumpWatch.Stop()
    $dumpHash = (Get-FileHash -LiteralPath $dumpPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $dumpBytes = (Get-Item -LiteralPath $dumpPath).Length

    $env:POSTGRES_PASSWORD = $restorePassword
    $containerId = docker run -d --name $containerName -p 127.0.0.1::5432 -e POSTGRES_PASSWORD postgres:18-alpine
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($containerId)) { throw "Could not start restore database." }
    $containerStarted = $true
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        docker exec $containerName pg_isready -U postgres 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw "Restore database did not become ready." }
    $portText = docker port $containerName 5432/tcp
    $restorePort = [int](($portText -split ':')[-1])
    $env:PGPASSWORD = $restorePassword
    $env:PGSSLMODE = "disable"
    & $psql -h 127.0.0.1 -p $restorePort -U postgres -d postgres -X -v ON_ERROR_STOP=1 -c `
        "CREATE ROLE eas_api NOLOGIN; CREATE ROLE eas_worker NOLOGIN; CREATE ROLE eas_backup NOLOGIN; CREATE ROLE eas_privacy NOLOGIN;" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not create policy roles in the restore target." }
    $restoreWatch = [Diagnostics.Stopwatch]::StartNew()
    & $pgRestore -h 127.0.0.1 -p $restorePort -U postgres -d postgres --no-owner --no-acl --exit-on-error $dumpPath
    if ($LASTEXITCODE -ne 0) { throw "pg_restore failed." }
    $restoreWatch.Stop()

    $verificationSql = @"
SELECT json_build_object(
  'schemas', (SELECT count(*) FROM information_schema.schemata WHERE schema_name = ANY(ARRAY['eas','mock_assets','mock_crm','mock_facilities','mock_finance','mock_hr','mock_it','mock_procurement','mock_travel'])),
  'users', (SELECT count(*) FROM eas.app_user),
  'active_request_types', (
    SELECT count(*) FROM eas.request_type rt
    JOIN eas.config_release cr ON cr.id=rt.active_release_id AND cr.state='PUBLISHED'
    WHERE rt.is_active
  ),
  'asset_items', (SELECT count(*) FROM mock_assets.asset_catalog),
  'admin_audit_head_matches', (
    SELECT h.seq = e.seq AND h.last_hash = e.hash
    FROM eas.audit_head h
    JOIN LATERAL (SELECT seq,hash FROM eas.admin_event ORDER BY seq DESC LIMIT 1) e ON true
    WHERE h.scope_key='ADMIN'
  )
);
"@
    $verification = (& $psql -h 127.0.0.1 -p $restorePort -U postgres -d postgres -X -A -t -v ON_ERROR_STOP=1 -c $verificationSql).Trim()
    if ($LASTEXITCODE -ne 0) { throw "Post-restore verification query failed." }
    $result = $verification | ConvertFrom-Json
    if ($result.schemas -ne $schemas.Count -or -not $result.admin_audit_head_matches -or $result.users -lt 1 -or $result.active_request_types -lt 1 -or $result.asset_items -lt 1) {
        throw "Post-restore invariants failed: $verification"
    }

    [ordered]@{
        status = "PASS"
        dump_sha256 = $dumpHash
        dump_bytes = $dumpBytes
        dump_seconds = [Math]::Round($dumpWatch.Elapsed.TotalSeconds, 3)
        restore_seconds = [Math]::Round($restoreWatch.Elapsed.TotalSeconds, 3)
        verification = $result
    } | ConvertTo-Json -Depth 4
}
finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:PGSSLMODE -ErrorAction SilentlyContinue
    Remove-Item Env:POSTGRES_PASSWORD -ErrorAction SilentlyContinue
    if ($containerStarted) { docker rm -f $containerName 2>$null | Out-Null }
    if (Test-Path -LiteralPath $workDir) {
        $resolved = [IO.Path]::GetFullPath($workDir)
        if (-not $resolved.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or (Split-Path $resolved -Leaf) -ne $containerName) {
            throw "Refusing to remove an unexpected rehearsal path: $resolved"
        }
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
