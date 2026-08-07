param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("KRX", "NASDAQ")]
    [string]$Market,
    [Parameter(Mandatory = $true)]
    [ValidateSet("KRX_PRE_OPEN", "KRX_POST_CLOSE", "NASDAQ_PRE_OPEN", "NASDAQ_POST_CLOSE")]
    [string]$BriefingType,
    [string]$SessionDate,
    [switch]$DryRun,
    [switch]$VerboseOutput,
    [switch]$Confirm
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "server\.venv\Scripts\python.exe"
$arguments = @(
    "-m", "app.cli", "market-briefings",
    "--market", $Market,
    "--briefing-type", $BriefingType
)
if ($SessionDate) { $arguments += @("--session-date", $SessionDate) }
if ($DryRun -or -not $Confirm) { $arguments += "--dry-run" }
if ($VerboseOutput) { $arguments += "--verbose" }
if ($Confirm) { $arguments += "--confirm" }
Set-Location (Join-Path $root "server")
& $python @arguments
exit $LASTEXITCODE
