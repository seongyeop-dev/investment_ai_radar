param()

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path `
    -Parent `
    $PSScriptRoot

$ServerDirectory = Join-Path `
    $ProjectRoot `
    "server"

$WebDirectory = Join-Path `
    $ProjectRoot `
    "web"

$PythonCommand = Join-Path `
    $ServerDirectory `
    ".venv\Scripts\python.exe"

$NextCommand = Join-Path `
    $WebDirectory `
    "node_modules\.bin\next.cmd"

$SeedScript = Join-Path `
    $ServerDirectory `
    "scripts\seed_candidate_review_validation.py"

$ValidationDirectory = Join-Path `
    $ProjectRoot `
    ".local\data\candidate_review_validation"

$ValidationDatabase = Join-Path `
    $ValidationDirectory `
    "investment_ai_radar_0017_validation.db"

$ValidationManifest = Join-Path `
    $ValidationDirectory `
    "validation_manifest.json"

$ValidationDistDirectory = Join-Path `
    $WebDirectory `
    ".next-validation"

$BackupRoot = Join-Path `
    $ProjectRoot `
    ".local\backups\candidate_review_validation"

function Wait-ForPort {
    param(
        [Parameter(Mandatory)]
        [int]$Port,

        [int]$TimeoutSeconds = 90
    )

    $Deadline = (
        Get-Date
    ).AddSeconds(
        $TimeoutSeconds
    )

    while ((Get-Date) -lt $Deadline) {
        $Listener = Get-NetTCPConnection `
            -State Listen `
            -LocalPort $Port `
            -ErrorAction SilentlyContinue

        if ($Listener) {
            return
        }

        Start-Sleep -Milliseconds 500
    }

    throw "Port $Port did not start."
}

foreach ($RequiredPath in @(
    $PythonCommand,
    $NextCommand,
    $SeedScript
)) {
    if (-not (
        Test-Path -LiteralPath $RequiredPath
    )) {
        throw "Required path not found: $RequiredPath"
    }
}

foreach ($Port in @(3001, 8001)) {
    $Listener = Get-NetTCPConnection `
        -State Listen `
        -LocalPort $Port `
        -ErrorAction SilentlyContinue

    if ($Listener) {
        throw "Validation port is already occupied: $Port"
    }
}

New-Item `
    -ItemType Directory `
    -Path $ValidationDirectory `
    -Force |
    Out-Null

if (
    Test-Path -LiteralPath $ValidationDatabase
) {
    $Timestamp = Get-Date `
        -Format "yyyyMMdd_HHmmss"

    $BackupDirectory = Join-Path `
        $BackupRoot `
        $Timestamp

    New-Item `
        -ItemType Directory `
        -Path $BackupDirectory `
        -Force |
        Out-Null

    Move-Item `
        -LiteralPath $ValidationDatabase `
        -Destination (
            Join-Path `
                $BackupDirectory `
                "investment_ai_radar_0017_validation.db"
        ) `
        -Force

    if (
        Test-Path -LiteralPath $ValidationManifest
    ) {
        Move-Item `
            -LiteralPath $ValidationManifest `
            -Destination (
                Join-Path `
                    $BackupDirectory `
                    "validation_manifest.json"
            ) `
            -Force
    }

    Write-Host (
        "Previous validation database archived: " +
        $BackupDirectory
    )
}

if (
    Test-Path -LiteralPath $ValidationDistDirectory
) {
    Remove-Item `
        -LiteralPath $ValidationDistDirectory `
        -Recurse `
        -Force
}

$DatabasePathForUrl = (
    $ValidationDatabase -replace "\\", "/"
)

$DatabaseUrl = (
    "sqlite+pysqlite:///" +
    $DatabasePathForUrl
)

$PreviousDatabaseUrl = (
    $env:DATABASE_URL
)

try {
    $env:DATABASE_URL = $DatabaseUrl

    Push-Location $ServerDirectory

    try {
        & $PythonCommand `
            -m alembic `
            -c alembic.ini `
            upgrade `
            20260803_0017

        if ($LASTEXITCODE -ne 0) {
            throw "Validation migration failed."
        }
    }
    finally {
        Pop-Location
    }
}
finally {
    if ($null -eq $PreviousDatabaseUrl) {
        Remove-Item `
            Env:DATABASE_URL `
            -ErrorAction SilentlyContinue
    }
    else {
        $env:DATABASE_URL = (
            $PreviousDatabaseUrl
        )
    }
}

$SeedOutput = & $PythonCommand `
    $SeedScript `
    --database-path `
    $ValidationDatabase

if ($LASTEXITCODE -ne 0) {
    throw "Validation seed failed."
}

$Seed = (
    $SeedOutput |
    ConvertFrom-Json
)

$Seed |
    ConvertTo-Json -Depth 10 |
    Set-Content `
        -LiteralPath $ValidationManifest `
        -Encoding UTF8

$ApiCommand = @"
`$env:DATABASE_URL = '$DatabaseUrl'
Set-Location '$ServerDirectory'
& '$PythonCommand' -m uvicorn app.main:app --host 127.0.0.1 --port 8001
"@

$WebCommand = @"
`$env:NEXT_PUBLIC_API_BASE_URL = 'http://127.0.0.1:8001'
`$env:NEXT_DIST_DIR = '.next-validation'
Set-Location '$WebDirectory'
& '$NextCommand' dev -H 127.0.0.1 -p 3001
"@

Start-Process `
    -FilePath "powershell.exe" `
    -ArgumentList @(
        "-NoExit",
        "-Command",
        $ApiCommand
    ) `
    -WindowStyle Normal |
    Out-Null

Wait-ForPort `
    -Port 8001 `
    -TimeoutSeconds 90

Start-Process `
    -FilePath "powershell.exe" `
    -ArgumentList @(
        "-NoExit",
        "-Command",
        $WebCommand
    ) `
    -WindowStyle Normal |
    Out-Null

Wait-ForPort `
    -Port 3001 `
    -TimeoutSeconds 120

$ApiResponse = Invoke-WebRequest `
    -Uri "http://127.0.0.1:8001/openapi.json" `
    -UseBasicParsing `
    -TimeoutSec 15

$WebResponse = Invoke-WebRequest `
    -Uri "http://127.0.0.1:3001/sources" `
    -UseBasicParsing `
    -TimeoutSec 30

if ($ApiResponse.StatusCode -ne 200) {
    throw "Validation API did not return HTTP 200."
}

if ($WebResponse.StatusCode -ne 200) {
    throw "Validation Web did not return HTTP 200."
}

Write-Host ""
Write-Host "============================================================"
Write-Host "CANDIDATE REVIEW VALIDATION ENVIRONMENT"
Write-Host "============================================================"
Write-Host "Database  : $ValidationDatabase"
Write-Host "Revision  : $($Seed.revision)"
Write-Host "Candidate : $($Seed.candidateId)"
Write-Host "API       : http://127.0.0.1:8001"
Write-Host "Web       : http://127.0.0.1:3001/sources"
Write-Host "Dist      : $ValidationDistDirectory"
Write-Host "============================================================"
Write-Host ""
Write-Host "VALIDATION API HTTP 200 PASS"
Write-Host "VALIDATION WEB HTTP 200 PASS"
Write-Host "REAL DATABASE WRITES: 0"
Write-Host "VALIDATION DATABASE WRITES: 1 SEED"
Write-Host "CANDIDATE_REVIEW_VALIDATION_START_PASS"
