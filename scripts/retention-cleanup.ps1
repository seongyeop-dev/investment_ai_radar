param([switch]$ConfirmCleanup)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "server\.venv\Scripts\python.exe"
Set-Location (Join-Path $root "server")
if (-not $ConfirmCleanup) {
    Write-Error "Retention cleanup requires -ConfirmCleanup."
    exit 2
}
& $python -m app.cli retention --confirm
exit $LASTEXITCODE
