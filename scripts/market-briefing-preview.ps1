param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("KRX", "NASDAQ")]
    [string]$Market,
    [Parameter(Mandatory = $true)]
    [ValidateSet("KRX_PRE_OPEN", "KRX_POST_CLOSE", "NASDAQ_PRE_OPEN", "NASDAQ_POST_CLOSE")]
    [string]$BriefingType,
    [string]$SessionDate,
    [switch]$VerboseOutput
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "server\.venv\Scripts\python.exe"
$arguments = @(
    "-m", "app.cli", "market-briefing-preview",
    "--market", $Market,
    "--briefing-type", $BriefingType,
    "--dry-run"
)
if ($SessionDate) { $arguments += @("--session-date", $SessionDate) }
if ($VerboseOutput) { $arguments += "--verbose" }
Set-Location (Join-Path $root "server")
& $python @arguments
exit $LASTEXITCODE
