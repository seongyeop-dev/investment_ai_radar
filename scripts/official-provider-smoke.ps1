param(
    [Parameter(Mandatory)]
    [ValidateSet("OPENDART", "SEC_EDGAR")]
    [string]$Provider,
    [switch]$DryRun,
    [switch]$Confirm
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "official-provider-common.ps1")
Initialize-OfficialProviderEnvironment
$arguments = @(
    "-m", "app.cli", "official-disclosure-smoke",
    "--provider", $Provider,
    "--limit", "1"
)
if ($DryRun) { $arguments += "--dry-run" }
if ($Confirm) { $arguments += "--confirm" }
& $script:OfficialProviderPython @arguments
exit $LASTEXITCODE
