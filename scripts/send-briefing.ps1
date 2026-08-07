param(
    [string]$BriefingId = "",
    [switch]$Confirm,
    [switch]$DryRun
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "server\.venv\Scripts\python.exe"
$arguments = @("-m", "app.cli", "send-briefing")
if ($BriefingId) { $arguments += @("--briefing-id", $BriefingId) }
if ($Confirm) { $arguments += "--confirm" }
if ($DryRun) { $arguments += "--dry-run" }
Set-Location (Join-Path $root "server")
& $python @arguments
exit $LASTEXITCODE
