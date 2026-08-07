[CmdletBinding()]
param(
    [ValidateSet("Real", "Validation", "All")]
    [string]$Environment = "All"
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

$ValidationDatabase = Join-Path `
    $ProjectRoot `
    ".local\data\subscription_create_validation\investment_ai_radar_0014_validation.db"

function Get-PortStatus {
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
        return [PSCustomObject]@{
            Port = $Port
            Listening = $false
            ProcessId = $null
            ProcessName = ""
            CommandLine = ""
        }
    }

    $process = Get-CimInstance `
        Win32_Process `
        -Filter "ProcessId=$($connection.OwningProcess)" `
        -ErrorAction SilentlyContinue

    return [PSCustomObject]@{
        Port = $Port
        Listening = $true
        ProcessId = $connection.OwningProcess
        ProcessName = $process.Name
        CommandLine = $process.CommandLine
    }
}

function Test-WebEndpoint {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Uri
    )

    try {
        $response = Invoke-WebRequest `
            -Uri $Uri `
            -Method Get `
            -UseBasicParsing `
            -TimeoutSec 5

        return "HTTP $($response.StatusCode)"
    }
    catch {
        return "OFFLINE"
    }
}

function Get-ApiSummary {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port
    )

    $sourceBase = (
        "http://127.0.0.1:{0}/api/v1/" +
        "analyst-references/subscriptions/" +
        "source-management"
    ) -f $Port

    $sourceUri = (
        "{0}?limit=100&offset=0" -f
        $sourceBase
    )

    $subscriptionUri = (
        "http://127.0.0.1:{0}/api/v1/" +
        "analyst-references/subscriptions" +
        "?limit=100&offset=0"
    ) -f $Port

    $referenceUri = (
        "http://127.0.0.1:{0}/api/v1/" +
        "analyst-references?limit=100&offset=0"
    ) -f $Port

    try {
        $sources = Invoke-RestMethod `
            -Method Get `
            -Uri $sourceUri `
            -TimeoutSec 5

        $subscriptions = Invoke-RestMethod `
            -Method Get `
            -Uri $subscriptionUri `
            -TimeoutSec 5

        $references = Invoke-RestMethod `
            -Method Get `
            -Uri $referenceUri `
            -TimeoutSec 5

        return [PSCustomObject]@{
            Online = $true
            Sources = $sources.total
            Subscriptions = $subscriptions.total
            References = $references.total
            Error = ""
        }
    }
    catch {
        return [PSCustomObject]@{
            Online = $false
            Sources = $null
            Subscriptions = $null
            References = $null
            Error = $_.Exception.Message
        }
    }
}

function Show-Environment {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [string]$DatabasePath,

        [Parameter(Mandatory = $true)]
        [int]$ApiPort,

        [Parameter(Mandatory = $true)]
        [int]$WebPort
    )

    $apiPortStatus = Get-PortStatus `
        -Port $ApiPort

    $webPortStatus = Get-PortStatus `
        -Port $WebPort

    $apiSummary = Get-ApiSummary `
        -Port $ApiPort

    $webStatus = Test-WebEndpoint `
        -Uri (
            "http://127.0.0.1:{0}/sources" -f
            $WebPort
        )

    Write-Host ""
    Write-Host ("=" * 80)
    Write-Host "$Name ENVIRONMENT"
    Write-Host ("=" * 80)
    Write-Host "Database path       : $DatabasePath"
    Write-Host "Database exists     : $(Test-Path -LiteralPath $DatabasePath)"
    Write-Host "API port            : $ApiPort"
    Write-Host "API listening       : $($apiPortStatus.Listening)"
    Write-Host "API PID             : $($apiPortStatus.ProcessId)"
    Write-Host "API process         : $($apiPortStatus.ProcessName)"
    Write-Host "Web port            : $WebPort"
    Write-Host "Web listening       : $($webPortStatus.Listening)"
    Write-Host "Web PID             : $($webPortStatus.ProcessId)"
    Write-Host "Web process         : $($webPortStatus.ProcessName)"
    Write-Host "Web response        : $webStatus"
    Write-Host "API response        : $($apiSummary.Online)"

    if ($apiSummary.Online) {
        Write-Host "Official sources    : $($apiSummary.Sources)"
        Write-Host "Subscriptions       : $($apiSummary.Subscriptions)"
        Write-Host "Analyst references  : $($apiSummary.References)"
    }
    else {
        Write-Host "API error           : $($apiSummary.Error)"
    }

    Write-Host ("=" * 80)
}

if (
    $Environment -eq "Real" -or
    $Environment -eq "All"
) {
    Show-Environment `
        -Name "REAL" `
        -DatabasePath $RealDatabase `
        -ApiPort 8000 `
        -WebPort 3000
}

if (
    $Environment -eq "Validation" -or
    $Environment -eq "All"
) {
    Show-Environment `
        -Name "VALIDATION" `
        -DatabasePath $ValidationDatabase `
        -ApiPort 8001 `
        -WebPort 3001
}

Write-Host ""
Write-Host "DATABASE WRITES: 0"
