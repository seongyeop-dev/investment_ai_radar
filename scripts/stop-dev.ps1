$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$statePath = Join-Path $root ".dev-lan-processes.json"
if (-not (Test-Path -LiteralPath $statePath)) {
    Write-Output "프로젝트에서 기록한 LAN 개발 프로세스가 없습니다."
    exit 0
}
$state = Get-Content -LiteralPath $statePath -Encoding utf8 | ConvertFrom-Json
foreach ($processId in @($state.serverPid, $state.webPid) | Where-Object { $_ }) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
    if (-not $process) { continue }
    if ($process.CommandLine -notlike "*$root*") {
        Write-Warning "PID $processId는 프로젝트 프로세스로 확인되지 않아 종료하지 않았습니다."
        continue
    }
    Stop-Process -Id $processId -ErrorAction Stop
    Write-Output "프로젝트 개발 프로세스 PID $processId 종료"
}
Start-Sleep -Milliseconds 500
foreach ($port in @(3000, 8000)) {
    $listeners = @(
        Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    )
    foreach ($listener in $listeners) {
        $process = Get-CimInstance Win32_Process `
            -Filter "ProcessId = $($listener.OwningProcess)" `
            -ErrorAction SilentlyContinue
        if (-not $process) { continue }
        if ($process.CommandLine -notlike "*$root*") {
            Write-Warning "포트 $port PID $($process.ProcessId)는 프로젝트 프로세스로 확인되지 않아 종료하지 않았습니다."
            continue
        }
        Stop-Process -Id $process.ProcessId -ErrorAction Stop
        Write-Output "프로젝트 포트 $port listener PID $($process.ProcessId) 종료"
    }
}
@{
    projectRoot = $root
    stoppedAt = (Get-Date).ToString("o")
    serverPid = $null
    webPid = $null
    webMode = $state.webMode
} | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding utf8
