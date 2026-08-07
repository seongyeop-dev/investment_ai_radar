param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$PythonCommand = "",
    [int]$ApiPort = 8011,
    [int]$WebPort = 3011,
    [switch]$SkipWeb,
    [switch]$Confirm
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function ConvertTo-SingleQuotedLiteral {
    param([Parameter(Mandatory)][string]$Value)
    return $Value.Replace("'", "''")
}

function Assert-PortAvailable {
    param([Parameter(Mandatory)][int]$Port)

    try {
        $listeners = @(
            Get-NetTCPConnection `
                -State Listen `
                -LocalPort $Port `
                -ErrorAction SilentlyContinue
        )
    }
    catch {
        $listeners = @()
    }

    if ($listeners.Count -gt 0) {
        throw "Port $Port is already in use."
    }
}

function Wait-LocalHttp {
    param(
        [Parameter(Mandatory)][string]$Uri,
        [int]$TimeoutSeconds = 45
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)

    do {
        try {
            $response = Invoke-WebRequest `
                -Uri $Uri `
                -UseBasicParsing `
                -TimeoutSec 3 `
                -ErrorAction Stop

            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return
            }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }
    while ((Get-Date) -lt $deadline)

    throw "Timed out waiting for $Uri"
}

if (-not $Confirm) {
    throw "Recording session start requires -Confirm."
}

$ProjectRoot = [System.IO.Path]::GetFullPath($ProjectRoot)

if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) {
    throw "Project root was not found: $ProjectRoot"
}

$serverRoot = Join-Path $ProjectRoot "server"
$webRoot = Join-Path $ProjectRoot "web"
$seedPath = Join-Path $serverRoot "scripts\seed_recording_session.py"
$runtimeRoot = Join-Path $ProjectRoot ".local\recording_session"
$databasePath = Join-Path $runtimeRoot "recording_session.db"
$manifestPath = Join-Path $runtimeRoot "processes.json"
$apiLauncherPath = Join-Path $runtimeRoot "run_api.ps1"
$webLauncherPath = Join-Path $runtimeRoot "run_web.ps1"

if ([string]::IsNullOrWhiteSpace($PythonCommand)) {
    $PythonCommand = Join-Path $serverRoot ".venv\Scripts\python.exe"
}

if (-not (Test-Path -LiteralPath $PythonCommand -PathType Leaf)) {
    throw @"
Python environment was not found:
$PythonCommand

Create server\.venv for this public copy or pass:
-PythonCommand "C:\path\to\python.exe"
"@
}

if (-not (Test-Path -LiteralPath $seedPath -PathType Leaf)) {
    throw "Recording session seed script was not found: $seedPath"
}

if (-not $SkipWeb) {
    if (-not (Test-Path -LiteralPath (Join-Path $webRoot "node_modules") -PathType Container)) {
        throw "web\node_modules was not found. Run npm ci in the public copy first."
    }

    $npmCommand = (Get-Command npm.cmd -ErrorAction Stop).Source
}

if (Test-Path -LiteralPath $manifestPath -PathType Leaf) {
    $existing = Get-Content `
        -LiteralPath $manifestPath `
        -Raw `
        -Encoding UTF8 |
        ConvertFrom-Json

    $running = @()

    foreach ($pidValue in @($existing.apiPid, $existing.webPid)) {
        if ($null -eq $pidValue) {
            continue
        }

        $process = Get-Process `
            -Id ([int]$pidValue) `
            -ErrorAction SilentlyContinue

        if ($null -ne $process) {
            $running += $process.Id
        }
    }

    if ($running.Count -gt 0) {
        throw "Recording session processes are already running: $($running -join ', ')"
    }
}

Assert-PortAvailable -Port $ApiPort

if (-not $SkipWeb) {
    Assert-PortAvailable -Port $WebPort
}

New-Item `
    -ItemType Directory `
    -Path $runtimeRoot `
    -Force |
Out-Null

$databaseUrlPath = $databasePath.Replace("\", "/")
$databaseUrl = "sqlite:///$databaseUrlPath"
$utf8 = New-Object System.Text.UTF8Encoding($false)

$previousDatabaseUrl = $env:DATABASE_URL

try {
    $env:DATABASE_URL = $databaseUrl

    Push-Location -LiteralPath $serverRoot
    try {
        & $PythonCommand `
            -m alembic `
            -c alembic.ini `
            upgrade head

        if ($LASTEXITCODE -ne 0) {
            throw "Alembic migration failed."
        }

        & $PythonCommand `
            "scripts\seed_recording_session.py" `
            --database-url $databaseUrl `
            --expected-demo-root $runtimeRoot `
            --confirm

        if ($LASTEXITCODE -ne 0) {
            throw "Recording session seed failed."
        }
    }
    finally {
        Pop-Location
    }
}
finally {
    if ($null -eq $previousDatabaseUrl) {
        Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
    }
    else {
        $env:DATABASE_URL = $previousDatabaseUrl
    }
}

$escapedServerRoot = ConvertTo-SingleQuotedLiteral -Value $serverRoot
$escapedPython = ConvertTo-SingleQuotedLiteral -Value $PythonCommand
$escapedDatabaseUrl = ConvertTo-SingleQuotedLiteral -Value $databaseUrl
$allowedOrigins = (
    "http://127.0.0.1:$WebPort,http://localhost:$WebPort"
)
$escapedAllowedOrigins = ConvertTo-SingleQuotedLiteral -Value $allowedOrigins

$apiLauncher = @"
`$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath '$escapedServerRoot'
`$env:DATABASE_URL = '$escapedDatabaseUrl'
`$env:APP_ENV = 'development'
`$env:EMAIL_ENABLED = 'false'
`$env:NEWS_SYNC_ENABLED = 'false'
`$env:NEWS_FEED_SYNC_ENABLED = 'false'
`$env:OPENDART_ENABLED = 'false'
`$env:SEC_EDGAR_ENABLED = 'false'
`$env:UPBIT_PUBLIC_MARKET_ENABLED = 'false'
`$env:BINANCE_PUBLIC_MARKET_ENABLED = 'false'
`$env:OFFICIAL_DISCLOSURE_SYNC_ENABLED = 'false'
`$env:AI_AUTOMATION_ENABLED = 'false'
`$env:ALLOWED_ORIGINS = '$escapedAllowedOrigins'
& '$escapedPython' -m uvicorn app.main:app --host 127.0.0.1 --port $ApiPort
"@

[System.IO.File]::WriteAllText(
    $apiLauncherPath,
    $apiLauncher,
    $utf8
)

$apiProcess = $null
$webProcess = $null

try {
    $apiProcess = Start-Process `
        -FilePath "powershell.exe" `
        -ArgumentList @(
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            $apiLauncherPath
        ) `
        -PassThru `
        -WindowStyle Minimized

    Wait-LocalHttp `
        -Uri "http://127.0.0.1:$ApiPort/openapi.json" `
        -TimeoutSeconds 45

    if (-not $SkipWeb) {
        $escapedWebRoot = ConvertTo-SingleQuotedLiteral -Value $webRoot
        $escapedNpm = ConvertTo-SingleQuotedLiteral -Value $npmCommand
        $apiBaseUrl = "http://127.0.0.1:$ApiPort"
        $escapedApiBaseUrl = ConvertTo-SingleQuotedLiteral -Value $apiBaseUrl

        $webLauncher = @"
`$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath '$escapedWebRoot'
`$env:NEXT_PUBLIC_API_BASE_URL = '$escapedApiBaseUrl'
& '$escapedNpm' run dev -- --hostname 127.0.0.1 --port $WebPort
"@

        [System.IO.File]::WriteAllText(
            $webLauncherPath,
            $webLauncher,
            $utf8
        )

        $webProcess = Start-Process `
            -FilePath "powershell.exe" `
            -ArgumentList @(
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                $webLauncherPath
            ) `
            -PassThru `
            -WindowStyle Minimized

        Wait-LocalHttp `
            -Uri "http://127.0.0.1:$WebPort/dashboard" `
            -TimeoutSeconds 60
    }

    $manifest = [ordered]@{
        startedAt = (Get-Date).ToString("o")
        projectRoot = $ProjectRoot
        databasePath = $databasePath
        databaseUrl = $databaseUrl
        apiPid = $apiProcess.Id
        apiPort = $ApiPort
        apiUrl = "http://127.0.0.1:$ApiPort"
        webPid = if ($null -ne $webProcess) {
            $webProcess.Id
        }
        else {
            $null
        }
        webPort = if (-not $SkipWeb) {
            $WebPort
        }
        else {
            $null
        }
        webUrl = if (-not $SkipWeb) {
            "http://127.0.0.1:$WebPort"
        }
        else {
            $null
        }
        liveProvidersEnabled = $false
    }

    [System.IO.File]::WriteAllText(
        $manifestPath,
        ($manifest | ConvertTo-Json -Depth 5),
        $utf8
    )
}
catch {
    foreach ($process in @($webProcess, $apiProcess)) {
        if ($null -eq $process) {
            continue
        }

        Stop-Process `
            -Id $process.Id `
            -Force `
            -ErrorAction SilentlyContinue
    }

    Remove-Item `
        -LiteralPath $manifestPath `
        -Force `
        -ErrorAction SilentlyContinue

    throw
}

Write-Host ""
Write-Host "============================================================"
Write-Host "RECORDING SESSION STARTED"
Write-Host "============================================================"
Write-Host "Database: $databasePath"
Write-Host "API: http://127.0.0.1:$ApiPort"
Write-Host "API PID: $($apiProcess.Id)"

if ($null -ne $webProcess) {
    Write-Host "Web: http://127.0.0.1:$WebPort"
    Write-Host "Web PID: $($webProcess.Id)"
}
else {
    Write-Host "Web: skipped"
}

Write-Host "Live providers enabled: NO"
Write-Host "Actual investment database accessed: NO"
Write-Host ""
Write-Host "Stop command:"
Write-Host ".\scripts\stop_recording_session.ps1"
