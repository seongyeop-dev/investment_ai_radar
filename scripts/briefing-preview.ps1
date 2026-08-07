$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "server\.venv\Scripts\python.exe"
Set-Location (Join-Path $root "server")
& $python -m app.cli briefing-preview
exit $LASTEXITCODE
