param(
    [string]$SubscriptionName = "Howard Marks",
    [int]$Limit = 3,
    [int]$TimeoutSeconds = 900,
    [int]$LockStaleSeconds = 1800,
    [int]$LogRetentionDays = 30
)

$ErrorActionPreference = "Stop"

$projectRoot = (
    Split-Path `
        -Path $PSScriptRoot `
        -Parent
)

$pythonPath = Join-Path `
    $projectRoot `
    "server\.venv\Scripts\python.exe"

$entryPath = Join-Path `
    $projectRoot `
    "server\scripts\reference_scheduled_run.py"

$databasePath = Join-Path `
    $projectRoot `
    ".local\data\investment_ai_radar.db"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Python executable not found: $pythonPath"
}

if (-not (Test-Path -LiteralPath $entryPath)) {
    throw "Scheduled entry script not found: $entryPath"
}

if (-not (Test-Path -LiteralPath $databasePath)) {
    throw "Database not found: $databasePath"
}

$previousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path `
    $projectRoot `
    "server"

try {
    Set-Location $projectRoot

    & $pythonPath `
        $entryPath `
        --project-root $projectRoot `
        --database-path $databasePath `
        --subscription-name $SubscriptionName `
        --limit $Limit `
        --timeout-seconds $TimeoutSeconds `
        --lock-stale-seconds $LockStaleSeconds `
        --log-retention-days $LogRetentionDays `
        --confirm-run

    $exitCode = $LASTEXITCODE
}
finally {
    if ($null -eq $previousPythonPath) {
        Remove-Item Env:PYTHONPATH `
            -ErrorAction SilentlyContinue
    }
    else {
        $env:PYTHONPATH = $previousPythonPath
    }
}

exit $exitCode
