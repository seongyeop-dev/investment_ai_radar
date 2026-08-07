param(
    [ValidateSet("OPENDART", "SEC_EDGAR")][string]$Provider = "OPENDART",
    [switch]$PortfolioOnly,
    [string]$Since,
    [string]$InstrumentId,
    [string]$PortfolioId,
    [string]$Symbol,
    [switch]$DryRun,
    [switch]$Confirm,
    [ValidateRange(1, 50)][int]$Limit = 30,
    [switch]$VerboseOutput
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "official-provider-common.ps1")
Initialize-OfficialProviderEnvironment
$arguments = @("-m", "app.cli", "sync-disclosures", "--provider", $Provider, "--limit", $Limit)
if ($PortfolioOnly) { $arguments += "--portfolio-only" }
if ($Since) { $arguments += @("--since", $Since) }
if ($InstrumentId) { $arguments += @("--instrument-id", $InstrumentId) }
if ($PortfolioId) { $arguments += @("--portfolio-id", $PortfolioId) }
if ($Symbol) { $arguments += @("--symbol", $Symbol) }
if ($DryRun) { $arguments += "--dry-run" }
if ($Confirm) { $arguments += "--confirm" }
if ($VerboseOutput) { $arguments += "--verbose" }
& $script:OfficialProviderPython @arguments
exit $LASTEXITCODE
