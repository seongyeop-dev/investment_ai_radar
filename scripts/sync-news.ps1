param(
    [ValidateSet("RSS", "ATOM", "OFFICIAL_IR_FEED")][string]$Provider = "RSS",
    [string]$SourceId,
    [string]$InstrumentId,
    [switch]$PortfolioOnly,
    [string]$Since,
    [int]$Limit = 50,
    [switch]$DryRun,
    [switch]$VerboseOutput
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "server\.venv\Scripts\python.exe"
Set-Location (Join-Path $root "server")
$arguments = @("-m", "app.cli", "sync-news", "--provider", $Provider, "--limit", $Limit)
if ($SourceId) { $arguments += @("--source-id", $SourceId) }
if ($InstrumentId) { $arguments += @("--instrument-id", $InstrumentId) }
if ($PortfolioOnly) { $arguments += "--portfolio-only" }
if ($Since) { $arguments += @("--since", $Since) }
if ($DryRun) { $arguments += "--dry-run" }
if ($VerboseOutput) { $arguments += "--verbose" }
& $python @arguments
exit $LASTEXITCODE
