$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "server\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "server\.venv가 없습니다."
}
Set-Location (Join-Path $root "server")
& $python -m ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python -m pytest
exit $LASTEXITCODE
