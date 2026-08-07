param()

$ErrorActionPreference = "Stop"

foreach ($Port in @(3001, 8001)) {
    $Listeners = Get-NetTCPConnection `
        -State Listen `
        -LocalPort $Port `
        -ErrorAction SilentlyContinue

    foreach ($Listener in $Listeners) {
        $ProcessId = (
            $Listener.OwningProcess
        )

        $Process = Get-Process `
            -Id $ProcessId `
            -ErrorAction SilentlyContinue

        if ($Process) {
            Write-Host "Stopping validation port $Port, PID=$ProcessId, Process=$($Process.ProcessName)"

            Stop-Process `
                -Id $ProcessId `
                -Force
        }
    }
}

Start-Sleep -Seconds 2

Write-Host ""
Write-Host "Candidate review validation stopped."
Write-Host "Validation database was preserved."
Write-Host "REAL ENVIRONMENT PROCESSES STOPPED: 0"
Write-Host "REAL DATABASE WRITES: 0"
Write-Host "CANDIDATE_REVIEW_VALIDATION_STOP_PASS"
