param(
    [string]$PortfolioId,
    [string]$Symbol,
    [ValidateRange(1, 30)][int]$Limit = 30,
    [switch]$DryRun,
    [switch]$Confirm
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "official-provider-common.ps1")
Initialize-OfficialProviderEnvironment
$arguments = @(
    "-m", "app.cli", "refresh-decision-reviews",
    "--limit", $Limit
)
if ($PortfolioId) { $arguments += @("--portfolio-id", $PortfolioId) }
if ($Symbol) { $arguments += @("--symbol", $Symbol) }
if ($DryRun) { $arguments += "--dry-run" }
if ($Confirm) { $arguments += "--confirm" }
& $script:OfficialProviderPython @arguments
exit $LASTEXITCODE
