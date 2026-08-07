param(
    [string]$Since,
    [ValidateRange(1, 366)][int]$Limit = 45,
    [switch]$DryRun,
    [switch]$Confirm
)

$arguments = @("-m", "app.cli", "sync-market-calendar", "--limit", "$Limit")
if ($Since) { $arguments += @("--since", $Since) }
if ($DryRun) { $arguments += "--dry-run" }
if ($Confirm) { $arguments += "--confirm" }
& "$PSScriptRoot\..\server\.venv\Scripts\python.exe" @arguments
exit $LASTEXITCODE
