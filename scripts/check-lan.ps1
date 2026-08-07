param([string]$Address = "")
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "lan-common.ps1")
$candidates = @(Get-PrivateIPv4Candidates)
if (-not $Address -and $candidates.Count -eq 1) { $Address = $candidates[0] }
if (-not $Address) {
    Write-Output ("사설 IPv4 후보: " + ($candidates -join ", "))
    throw "-Address로 확인할 사설 IPv4를 지정하세요."
}
if (-not (Test-PrivateIPv4 -Address $Address)) {
    throw "사설 IPv4가 아닙니다."
}
$origin = "http://${Address}:3000"
$webListener = @(Get-NetTCPConnection -State Listen -LocalPort 3000 -ErrorAction SilentlyContinue)
$apiListener = @(Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue)
$webOk = $false
$apiOk = $false
$corsOk = $false
try {
    $webOk = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 -Uri "$origin/portfolio").StatusCode -eq 200
} catch {}
try {
    $response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 `
        -Headers @{ Origin = $origin } -Uri "http://${Address}:8000/health"
    $apiOk = $response.StatusCode -eq 200
    $corsOk = $response.Headers["Access-Control-Allow-Origin"] -eq $origin
} catch {}
Write-Output "Private IPv4: $Address"
Write-Output "Web listener: $($webListener.Count -gt 0), health: $webOk"
Write-Output "API listener: $($apiListener.Count -gt 0), health: $apiOk"
Write-Output "Exact LAN CORS origin: $corsOk (wildcard 사용 안 함)"
Write-Output "핸드폰 접속: $origin/portfolio"
