param(
    [switch]$ConfirmSend,
    [switch]$DryRun
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "server\.venv\Scripts\python.exe"
$arguments = @("-m", "app.cli", "radar-cycle")
if ($ConfirmSend) { $arguments += "--confirm-send" }
if ($DryRun -or -not $ConfirmSend) { $arguments += "--dry-run" }
Set-Location (Join-Path $root "server")
& $python @arguments
exit $LASTEXITCODE
