[CmdletBinding()]
param(
    [ValidateSet("Launch", "Api", "Web")]
    [string]$Role = "Launch",

    [switch]$SkipBuild,

    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$ProjectRoot = (
    Resolve-Path (
        Join-Path $PSScriptRoot ".."
    )
).Path

$RealDatabase = Join-Path `
    $ProjectRoot `
    ".local\data\investment_ai_radar.db"

$PythonCommand = Join-Path `
    $ProjectRoot `
    "server\.venv\Scripts\python.exe"

$DatabaseValidator = Join-Path `
    $ProjectRoot `
    "server\scripts\validate_runtime_database.py"

$ExpectedDatabaseRevision = "20260803_0017"

$WebDirectory = Join-Path `
    $ProjectRoot `
    "web"

$NextCommand = Join-Path `
    $WebDirectory `
    "node_modules\.bin\next.cmd"

function Test-PortListening {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port
    )

    return $null -ne (
        Get-NetTCPConnection `
            -State Listen `
            -LocalPort $Port `
            -ErrorAction SilentlyContinue |
        Select-Object -First 1
    )
}

function Assert-PortFree {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port
    )

    $connection = (
        Get-NetTCPConnection `
            -State Listen `
            -LocalPort $Port `
            -ErrorAction SilentlyContinue |
        Select-Object -First 1
    )

    if ($null -eq $connection) {
        return
    }

    $process = Get-CimInstance `
        Win32_Process `
        -Filter "ProcessId=$($connection.OwningProcess)" `
        -ErrorAction SilentlyContinue

    throw (
        "Port $Port is already in use. " +
        "PID=$($connection.OwningProcess), " +
        "Process=$($process.Name)"
    )
}

function Wait-ForPort {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port,

        [int]$TimeoutSeconds = 30
    )

    $deadline = (
        Get-Date
    ).AddSeconds($TimeoutSeconds)

    while ((Get-Date) -lt $deadline) {
        if (Test-PortListening -Port $Port) {
            return
        }

        Start-Sleep -Milliseconds 500
    }

    throw (
        "Port $Port did not start within " +
        "$TimeoutSeconds seconds."
    )
}

function Assert-CommandAvailable {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if (
        $null -eq (
            Get-Command $Name `
                -ErrorAction SilentlyContinue
        )
    ) {
        throw "Required command was not found: $Name"
    }
}

if (-not (Test-Path -LiteralPath $RealDatabase)) {
    throw "Real database was not found: $RealDatabase"
}

foreach ($RequiredPath in @(
    $PythonCommand,
    $DatabaseValidator
)) {
    if (-not (
        Test-Path `
            -LiteralPath $RequiredPath `
            -PathType Leaf
    )) {
        throw "Required path was not found: $RequiredPath"
    }
}

& $PythonCommand `
    $DatabaseValidator `
    --database-path `
    $RealDatabase `
    --expected-revision `
    $ExpectedDatabaseRevision

if ($LASTEXITCODE -ne 0) {
    throw (
        "Real database validation failed. " +
        "Required revision: $ExpectedDatabaseRevision"
    )
}

Assert-CommandAvailable -Name "uv"

if (-not (Test-Path -LiteralPath $NextCommand)) {
    throw "Next.js command was not found: $NextCommand"
}

if ($Role -eq "Launch") {
    Assert-PortFree -Port 8000
    Assert-PortFree -Port 3000

    Write-Host ("=" * 80)
    Write-Host "INVESTMENT AI RADAR - REAL ENVIRONMENT"
    Write-Host ("=" * 80)
    Write-Host "Database : $RealDatabase"
    Write-Host "API      : http://127.0.0.1:8000"
    Write-Host "Web      : http://localhost:3000"
    Write-Host ("=" * 80)

    if ($CheckOnly) {
        Write-Host "Result: REAL ENVIRONMENT CHECK PASS" `
            -ForegroundColor Green
        return
    }

    $apiArguments = @(
        "-NoExit",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $PSCommandPath,
        "-Role",
        "Api"
    )

    Start-Process `
        -FilePath "powershell.exe" `
        -ArgumentList $apiArguments `
        -WindowStyle Normal | Out-Null

    Wait-ForPort `
        -Port 8000 `
        -TimeoutSeconds 30

    $webArguments = @(
        "-NoExit",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $PSCommandPath,
        "-Role",
        "Web"
    )

    if ($SkipBuild) {
        $webArguments += "-SkipBuild"
    }

    Start-Process `
        -FilePath "powershell.exe" `
        -ArgumentList $webArguments `
        -WindowStyle Normal | Out-Null

    Wait-ForPort `
        -Port 3000 `
        -TimeoutSeconds 90

    Write-Host ""
    Write-Host "Real environment launch requested." `
        -ForegroundColor Green
    Write-Host "Keep both API and Web windows open."
    return
}

Set-Location $ProjectRoot

if ($Role -eq "Api") {
    $Host.UI.RawUI.WindowTitle = (
        "INVESTMENT AI RADAR - REAL API 8000"
    )

    $databaseUri = (
        "sqlite+pysqlite:///" +
        $RealDatabase.Replace("\", "/")
    )

    $env:DATABASE_URL = $databaseUri

    Write-Host ("=" * 80)
    Write-Host "REAL API"
    Write-Host ("=" * 80)
    Write-Host "Database : $RealDatabase"
    Write-Host "API      : http://127.0.0.1:8000"
    Write-Host ("=" * 80)

    uv run --project server `
        --no-sync `
        uvicorn app.main:app `
        --app-dir server `
        --host 127.0.0.1 `
        --port 8000

    exit $LASTEXITCODE
}

if ($Role -eq "Web") {
    $Host.UI.RawUI.WindowTitle = (
        "INVESTMENT AI RADAR - REAL WEB 3000"
    )

    $env:NEXT_PUBLIC_API_BASE_URL = (
        "http://127.0.0.1:8000"
    )

    Write-Host ("=" * 80)
    Write-Host "REAL WEB"
    Write-Host ("=" * 80)
    Write-Host "API : $env:NEXT_PUBLIC_API_BASE_URL"
    Write-Host "Web : http://localhost:3000"
    Write-Host ("=" * 80)

    Push-Location $WebDirectory

    try {
        if (-not $SkipBuild) {
            & $NextCommand build

            if ($LASTEXITCODE -ne 0) {
                throw "Web production build failed."
            }
        }

        & $NextCommand start `
            -H 127.0.0.1 `
            -p 3000

        $webExitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }

    exit $webExitCode
}
