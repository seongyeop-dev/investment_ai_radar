[CmdletBinding()]
param(
    [ValidateSet("Real", "Validation", "All")]
    [string]$Environment
)

$ErrorActionPreference = "Stop"

if (
    [string]::IsNullOrWhiteSpace(
        $Environment
    )
) {
    throw (
        "Environment is required. " +
        "Use Real, Validation, or All."
    )
}

$ProjectRoot = (
    Resolve-Path (
        Join-Path $PSScriptRoot ".."
    )
).Path

$ports = @()

if (
    $Environment -eq "Real" -or
    $Environment -eq "All"
) {
    $ports += 3000
    $ports += 8000
}

if (
    $Environment -eq "Validation" -or
    $Environment -eq "All"
) {
    $ports += 3001
    $ports += 8001
}

foreach ($port in $ports) {
    $connections = @(
        Get-NetTCPConnection `
            -State Listen `
            -LocalPort $port `
            -ErrorAction SilentlyContinue
    )

    if ($connections.Count -eq 0) {
        Write-Host "Port $port is already stopped."
        continue
    }

    $processIds = @(
        $connections |
        Select-Object `
            -ExpandProperty OwningProcess `
            -Unique
    )

    foreach ($processId in $processIds) {
        $process = Get-CimInstance `
            Win32_Process `
            -Filter "ProcessId=$processId" `
            -ErrorAction SilentlyContinue

        if ($null -eq $process) {
            Write-Warning (
                "Process information was not found " +
                "for PID $processId."
            )
            continue
        }

        $identity = (
            "$($process.ExecutablePath) " +
            "$($process.CommandLine)"
        )

        $isRadarProcess = (
            $identity -like (
                "*$ProjectRoot*"
            )
        )

        if (-not $isRadarProcess) {
            Write-Warning (
                "Port $port belongs to an unverified " +
                "process and was not stopped. " +
                "PID=$processId, " +
                "Process=$($process.Name)"
            )
            continue
        }

        Write-Host (
            "Stopping port $port, " +
            "PID=$processId, " +
            "Process=$($process.Name)"
        )

        Stop-Process `
            -Id $processId `
            -Force
    }
}

Write-Host ""
Write-Host (
    "$Environment environment stop completed."
) -ForegroundColor Green
