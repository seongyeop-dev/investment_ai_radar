param()

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path `
    -Parent `
    $PSScriptRoot

$ServerDirectory = Join-Path `
    $ProjectRoot `
    "server"

$PythonCommand = Join-Path `
    $ServerDirectory `
    ".venv\Scripts\python.exe"

$ValidationDatabase = Join-Path `
    $ProjectRoot `
    ".local\data\candidate_review_validation\investment_ai_radar_0017_validation.db"

$LogDirectory = Join-Path `
    $ProjectRoot `
    ".local\logs\candidate_review_validation_api"

$StandardOutputLog = Join-Path `
    $LogDirectory `
    "stdout.log"

$StandardErrorLog = Join-Path `
    $LogDirectory `
    "stderr.log"

if (-not (
    Test-Path `
        -LiteralPath $PythonCommand `
        -PathType Leaf
)) {
    throw "Validation Python was not found."
}

if (-not (
    Test-Path `
        -LiteralPath $ValidationDatabase `
        -PathType Leaf
)) {
    throw "Validation database was not found."
}

New-Item `
    -ItemType Directory `
    -Path $LogDirectory `
    -Force |
    Out-Null

foreach ($LogPath in @(
    $StandardOutputLog,
    $StandardErrorLog
)) {
    if (Test-Path -LiteralPath $LogPath) {
        Remove-Item `
            -LiteralPath $LogPath `
            -Force
    }
}

$OldListener = Get-NetTCPConnection `
    -State Listen `
    -LocalPort 8001 `
    -ErrorAction SilentlyContinue |
    Select-Object -First 1

$OldPid = $null

if ($null -ne $OldListener) {
    $OldPid = [int]$OldListener.OwningProcess

    Write-Host "Stopping validation API PID=$OldPid"

    Stop-Process `
        -Id $OldPid `
        -Force

    $StopDeadline = (
        Get-Date
    ).AddSeconds(20)

    do {
        Start-Sleep -Milliseconds 500

        $RemainingListener = (
            Get-NetTCPConnection `
                -State Listen `
                -LocalPort 8001 `
                -ErrorAction SilentlyContinue
        )
    }
    until (
        -not $RemainingListener -or
        (Get-Date) -ge $StopDeadline
    )

    if ($RemainingListener) {
        throw "Old validation API did not stop."
    }
}

$DatabasePathForUrl = (
    $ValidationDatabase -replace "\\", "/"
)

$DatabaseUrl = (
    "sqlite+pysqlite:///" +
    $DatabasePathForUrl
)

$PreviousDatabaseUrl = $env:DATABASE_URL

try {
    $env:DATABASE_URL = $DatabaseUrl

    $Arguments = @(
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8001"
    )

    $Process = Start-Process `
        -FilePath $PythonCommand `
        -ArgumentList $Arguments `
        -WorkingDirectory $ServerDirectory `
        -RedirectStandardOutput $StandardOutputLog `
        -RedirectStandardError $StandardErrorLog `
        -WindowStyle Hidden `
        -PassThru
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

$StartDeadline = (
    Get-Date
).AddSeconds(90)

$NewListener = $null

do {
    Start-Sleep -Milliseconds 500

    $NewListener = (
        Get-NetTCPConnection `
            -State Listen `
            -LocalPort 8001 `
            -ErrorAction SilentlyContinue |
        Select-Object -First 1
    )

    $Process.Refresh()

    if ($Process.HasExited) {
        Write-Host ""
        Write-Host "VALIDATION API STDERR:"
        Get-Content `
            -LiteralPath $StandardErrorLog `
            -ErrorAction SilentlyContinue

        throw (
            "Validation API exited with code " +
            $Process.ExitCode
        )
    }
}
until (
    $null -ne $NewListener -or
    (Get-Date) -ge $StartDeadline
)

if ($null -eq $NewListener) {
    throw "Validation API port 8001 did not start."
}

$NewPid = [int]$NewListener.OwningProcess

$OpenApiResponse = Invoke-WebRequest `
    -Uri "http://127.0.0.1:8001/openapi.json" `
    -UseBasicParsing `
    -TimeoutSec 15

if ($OpenApiResponse.StatusCode -ne 200) {
    throw "Validation API did not return HTTP 200."
}

Write-Host ""
Write-Host "OLD API PID: $OldPid"
Write-Host "NEW API PID: $NewPid"
Write-Host "DATABASE: $ValidationDatabase"
Write-Host "STDOUT LOG: $StandardOutputLog"
Write-Host "STDERR LOG: $StandardErrorLog"
Write-Host "VALIDATION API HTTP 200 PASS"
Write-Host "VALIDATION DATABASE RECREATED: 0"
Write-Host "VALIDATION SEED EXECUTED: 0"
Write-Host "REAL DATABASE WRITES: 0"
Write-Host "VALIDATION_API_DIRECT_RESTART_PASS"
