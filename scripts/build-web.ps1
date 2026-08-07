$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $root "web")
& npm run lint
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& npm run build
exit $LASTEXITCODE
