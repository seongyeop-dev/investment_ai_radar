param(
    [ValidateSet("UPBIT", "BINANCE")][string]$Provider,
    [switch]$DryRun,
    [switch]$Confirm
)

$arguments = @("-m", "app.cli", "sync-public-quotes")
if ($Provider) { $arguments += @("--provider", $Provider) }
if ($DryRun) { $arguments += "--dry-run" }
if ($Confirm) { $arguments += "--confirm" }
& "$PSScriptRoot\..\server\.venv\Scripts\python.exe" @arguments
exit $LASTEXITCODE
