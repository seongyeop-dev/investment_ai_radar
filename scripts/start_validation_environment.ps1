[CmdletBinding()]
param(
    [ValidateSet("Launch", "Api", "Web")]
    [string]$Role = "Launch",

    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$ProjectRoot = (
    Resolve-Path (
        Join-Path $PSScriptRoot ".."
    )
).Path

$ValidationDatabase = Join-Path `
    $ProjectRoot `
    ".local\data\subscription_create_validation\investment_ai_radar_0014_validation.db"

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

if (
    -not (
        Test-Path `
            -LiteralPath $ValidationDatabase
    )
) {
    throw (
        "Validation database was not found: " +
        $ValidationDatabase
    )
}

Assert-CommandAvailable -Name "uv"
Assert-CommandAvailable -Name "npm"

if ($Role -eq "Launch") {
    Assert-PortFree -Port 8001
    Assert-PortFree -Port 3001

    Write-Host ("=" * 80)
    Write-Host "INVESTMENT AI RADAR - VALIDATION ENVIRONMENT"
    Write-Host ("=" * 80)
    Write-Host "Database : $ValidationDatabase"
    Write-Host "API      : http://127.0.0.1:8001"
    Write-Host "Web      : http://127.0.0.1:3001"
    Write-Host ("=" * 80)

    if ($CheckOnly) {
        Write-Host "Result: VALIDATION ENVIRONMENT CHECK PASS" `
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
        -Port 8001 `
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

    Start-Process `
        -FilePath "powershell.exe" `
        -ArgumentList $webArguments `
        -WindowStyle Normal | Out-Null

    Write-Host ""
    Write-Host "Validation environment launch requested." `
        -ForegroundColor Green
    Write-Host "Open http://127.0.0.1:3001"
    return
}

Set-Location $ProjectRoot

if ($Role -eq "Api") {
    $Host.UI.RawUI.WindowTitle = (
        "INVESTMENT AI RADAR - VALIDATION API 8001"
    )

    $databaseUri = (
        "sqlite+pysqlite:///" +
        $ValidationDatabase.Replace("\", "/")
    )

    $env:DATABASE_URL = $databaseUri

    Write-Host ("=" * 80)
    Write-Host "VALIDATION API"
    Write-Host ("=" * 80)
    Write-Host "Database : $ValidationDatabase"
    Write-Host "API      : http://127.0.0.1:8001"
    Write-Host ("=" * 80)

    uv run --project server `
        --no-sync `
        uvicorn app.main:app `
        --app-dir server `
        --host 127.0.0.1 `
        --port 8001

    exit $LASTEXITCODE
}

if ($Role -eq "Web") {
    $Host.UI.RawUI.WindowTitle = (
        "INVESTMENT AI RADAR - VALIDATION WEB 3001"
    )

    $env:NEXT_PUBLIC_API_BASE_URL = (
        "http://127.0.0.1:8001"
    )

    Write-Host ("=" * 80)
    Write-Host "VALIDATION WEB"
    Write-Host ("=" * 80)
    Write-Host "API : $env:NEXT_PUBLIC_API_BASE_URL"
    Write-Host "Web : http://127.0.0.1:3001"
    Write-Host ("=" * 80)

    Push-Location (
        Join-Path $ProjectRoot "web"
    )

    try {
        & ".\node_modules\.bin\next.cmd" dev `
            -H 127.0.0.1 `
            -p 3001
    }
    finally {
        Pop-Location
    }

    exit $LASTEXITCODE
}
