$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
& (Join-Path $root "scripts\test-server.ps1")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& (Join-Path $root "scripts\build-web.ps1")
exit $LASTEXITCODE
