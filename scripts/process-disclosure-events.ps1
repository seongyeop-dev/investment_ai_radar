param(
    [switch]$DryRun,
    [switch]$Confirm
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "official-provider-common.ps1")
Initialize-OfficialProviderEnvironment
$arguments = @("-m", "app.cli", "process-disclosure-events")
if ($DryRun) { $arguments += "--dry-run" }
if ($Confirm) { $arguments += "--confirm" }
& $script:OfficialProviderPython @arguments
exit $LASTEXITCODE
