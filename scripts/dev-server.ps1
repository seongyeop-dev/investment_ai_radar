$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "server\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "server\.venv가 없습니다. py -V:3.12 -m venv server\.venv 후 의존성을 설치하세요."
}
Set-Location (Join-Path $root "server")
& $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
exit $LASTEXITCODE
