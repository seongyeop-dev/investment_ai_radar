param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = [System.IO.Path]::GetFullPath($ProjectRoot)
$runtimeRoot = Join-Path $ProjectRoot ".local\portfolio_validation"
$manifestPath = Join-Path $runtimeRoot "processes.json"
$apiLauncherPath = Join-Path $runtimeRoot "run_api.ps1"
$webLauncherPath = Join-Path $runtimeRoot "run_web.ps1"

if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    Write-Host "Portfolio validation manifest was not found."
    Write-Host "No process was stopped."
    exit 0
}

$manifest = Get-Content `
    -LiteralPath $manifestPath `
    -Raw `
    -Encoding UTF8 |
    ConvertFrom-Json

$stopped = @()
$notRunning = @()

foreach ($entry in @(
    [pscustomobject]@{
        Name = "Web"
        Pid = $manifest.webPid
    },
    [pscustomobject]@{
        Name = "API"
        Pid = $manifest.apiPid
    }
)) {
    if ($null -eq $entry.Pid) {
        continue
    }

    $process = Get-Process `
        -Id ([int]$entry.Pid) `
        -ErrorAction SilentlyContinue

    if ($null -eq $process) {
        $notRunning += "$($entry.Name):$($entry.Pid)"
        continue
    }

    Stop-Process `
        -Id $process.Id `
        -Force `
        -ErrorAction Stop

    $stopped += "$($entry.Name):$($process.Id)"
}

Remove-Item `
    -LiteralPath $manifestPath `
    -Force `
    -ErrorAction Stop

foreach ($path in @($apiLauncherPath, $webLauncherPath)) {
    Remove-Item `
        -LiteralPath $path `
        -Force `
        -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "============================================================"
Write-Host "PORTFOLIO VALIDATION STOPPED"
Write-Host "============================================================"
Write-Host "Stopped: $(if ($stopped.Count -gt 0) { $stopped -join ', ' } else { 'none' })"
Write-Host "Already stopped: $(if ($notRunning.Count -gt 0) { $notRunning -join ', ' } else { 'none' })"
Write-Host "Validation database preserved: $($manifest.databasePath)"
Write-Host "Actual investment database accessed: NO"
