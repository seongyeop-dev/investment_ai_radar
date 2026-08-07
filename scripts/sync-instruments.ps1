param(
    [ValidateSet("OPENDART", "SEC_EDGAR")][string]$Provider = "OPENDART",
    [switch]$DryRun,
    [switch]$Confirm,
    [ValidateRange(1, 30)][int]$Limit = 3,
    [string]$PortfolioId,
    [string]$Symbol,
    [switch]$VerboseOutput
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "official-provider-common.ps1")
Initialize-OfficialProviderEnvironment
$arguments = @("-m", "app.cli", "sync-instruments", "--provider", $Provider, "--limit", $Limit)
if ($PortfolioId) { $arguments += @("--portfolio-id", $PortfolioId) }
if ($Symbol) { $arguments += @("--symbol", $Symbol) }
if ($DryRun) { $arguments += "--dry-run" }
if ($Confirm) { $arguments += "--confirm" }
if ($VerboseOutput) { $arguments += "--verbose" }
& $script:OfficialProviderPython @arguments
exit $LASTEXITCODE
