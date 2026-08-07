$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $PSScriptRoot "sync-news.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File $script -DryRun
exit $LASTEXITCODE
