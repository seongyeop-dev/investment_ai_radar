param(
    [Parameter(Mandatory = $true)]
    [ValidateSet(
        "Validate",
        "Install",
        "Status",
        "RunNow",
        "Remove"
    )]
    [string]$Action,

    [string]$DailyAt,

    [string]$TaskName = (
        "InvestmentAIRadar-ReferenceScheduler"
    ),

    [int]$ExecutionTimeLimitMinutes = 30,

    [switch]$ConfirmRemoval
)

$ErrorActionPreference = "Stop"

$projectRoot = (
    Split-Path `
        -Path $PSScriptRoot `
        -Parent
)

$runnerPath = Join-Path `
    $projectRoot `
    "scripts\run_reference_scheduler.ps1"

$pythonPath = Join-Path `
    $projectRoot `
    "server\.venv\Scripts\python.exe"

$databasePath = Join-Path `
    $projectRoot `
    ".local\data\investment_ai_radar.db"

$taskDescription = @"
INVESTMENT_AI_RADAR 참고자료 수집 스케줄러 작업입니다.
중복 실행 잠금과 데이터베이스 경로를 확인한 뒤
설정된 참고자료 수집 작업을 실행합니다.
"@.Trim()


function Assert-ProjectPrerequisites {
    if (
        -not (
            Test-Path `
                -LiteralPath $runnerPath `
                -PathType Leaf
        )
    ) {
        throw (
            "Scheduler runner was not found: " +
            $runnerPath
        )
    }

    if (
        -not (
            Test-Path `
                -LiteralPath $pythonPath `
                -PathType Leaf
        )
    ) {
        throw (
            "Python executable was not found: " +
            $pythonPath
        )
    }

    if (
        -not (
            Test-Path `
                -LiteralPath $databasePath `
                -PathType Leaf
        )
    ) {
        throw (
            "Database was not found: " +
            $databasePath
        )
    }

    $scheduledTaskCommand = Get-Command `
        -Name "Get-ScheduledTask" `
        -ErrorAction SilentlyContinue

    if ($null -eq $scheduledTaskCommand) {
        throw (
            "The Windows ScheduledTasks module " +
            "is not available."
        )
    }
}


function ConvertTo-DailyTriggerTime {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    if (
        $Value -notmatch (
            "^(?:[01]\d|2[0-3]):[0-5]\d$"
        )
    ) {
        throw (
            "DailyAt must use 24-hour HH:mm format. " +
            "Example: 09:30"
        )
    }

    $parsedTime = [TimeSpan]::ParseExact(
        $Value,
        "hh\:mm",
        [Globalization.CultureInfo]::InvariantCulture
    )

    return [DateTime]::Today.Add(
        $parsedTime
    )
}


function Get-ReferenceScheduledTask {
    return Get-ScheduledTask `
        -TaskName $TaskName `
        -ErrorAction SilentlyContinue
}


function Write-TaskStatus {
    $task = Get-ReferenceScheduledTask

    Write-Host ""
    Write-Host (
        "=" * 78
    )
    Write-Host (
        "REFERENCE SCHEDULER TASK STATUS"
    )
    Write-Host (
        "=" * 78
    )
    Write-Host "Task name: $TaskName"
    Write-Host "Project root: $projectRoot"
    Write-Host "Runner: $runnerPath"
    Write-Host "Database: $databasePath"

    if ($null -eq $task) {
        Write-Host "Registered: False"
        Write-Host "Result: TASK NOT REGISTERED"
        Write-Host (
            "=" * 78
        )

        return
    }

    $taskInfo = Get-ScheduledTaskInfo `
        -TaskName $TaskName

    $dailyTrigger = @(
        $task.Triggers |
        Where-Object {
            $_.CimClass.CimClassName -eq (
                "MSFT_TaskDailyTrigger"
            )
        }
    ) |
    Select-Object -First 1

    Write-Host "Registered: True"
    Write-Host "State: $($task.State)"
    Write-Host (
        "Enabled: " +
        [string]$task.Settings.Enabled
    )
    Write-Host (
        "Last run time: " +
        [string]$taskInfo.LastRunTime
    )
    Write-Host (
        "Last result: " +
        [string]$taskInfo.LastTaskResult
    )
    Write-Host (
        "Next run time: " +
        [string]$taskInfo.NextRunTime
    )

    if ($null -ne $dailyTrigger) {
        Write-Host (
            "Trigger start: " +
            [string]$dailyTrigger.StartBoundary
        )
    }

    Write-Host (
        "Multiple instances: " +
        [string]$task.Settings.MultipleInstances
    )
    Write-Host (
        "Execution time limit: " +
        [string]$task.Settings.ExecutionTimeLimit
    )
    Write-Host "Result: TASK STATUS PASS"
    Write-Host (
        "=" * 78
    )
}


Assert-ProjectPrerequisites


switch ($Action) {
    "Validate" {
        if ($DailyAt) {
            $validatedTime = (
                ConvertTo-DailyTriggerTime `
                    -Value $DailyAt
            )

            Write-Host (
                "Validated daily time: " +
                $validatedTime.ToString("HH:mm")
            )
        }

        Write-Host ""
        Write-Host (
            "=" * 78
        )
        Write-Host (
            "REFERENCE SCHEDULER TASK VALIDATION"
        )
        Write-Host (
            "=" * 78
        )
        Write-Host "Project root: $projectRoot"
        Write-Host "Runner exists: True"
        Write-Host "Python exists: True"
        Write-Host "Database exists: True"
        Write-Host "ScheduledTasks module: True"
        Write-Host "Task writes: 0"
        Write-Host "Result: TASK VALIDATION PASS"
        Write-Host (
            "=" * 78
        )
    }

    "Install" {
        if (-not $DailyAt) {
            throw (
                "-DailyAt is required when " +
                "-Action Install is used."
            )
        }

        if ($ExecutionTimeLimitMinutes -lt 5) {
            throw (
                "ExecutionTimeLimitMinutes must be " +
                "at least 5."
            )
        }

        $triggerTime = (
            ConvertTo-DailyTriggerTime `
                -Value $DailyAt
        )

        $arguments = (
            '-NoProfile ' +
            '-NonInteractive ' +
            '-ExecutionPolicy Bypass ' +
            '-File "' +
            $runnerPath +
            '"'
        )

        $taskAction = New-ScheduledTaskAction `
            -Execute "powershell.exe" `
            -Argument $arguments `
            -WorkingDirectory $projectRoot

        $taskTrigger = New-ScheduledTaskTrigger `
            -Daily `
            -At $triggerTime

        $currentUser = (
            [Security.Principal.WindowsIdentity]::GetCurrent().Name
        )

        $taskPrincipal = New-ScheduledTaskPrincipal `
            -UserId $currentUser `
            -LogonType Interactive `
            -RunLevel Limited

        $taskSettings = New-ScheduledTaskSettingsSet `
            -StartWhenAvailable `
            -MultipleInstances IgnoreNew `
            -ExecutionTimeLimit (
                New-TimeSpan `
                    -Minutes $ExecutionTimeLimitMinutes
            ) `
            -AllowStartIfOnBatteries `
            -DontStopIfGoingOnBatteries

        Register-ScheduledTask `
            -TaskName $TaskName `
            -Description $taskDescription `
            -Action $taskAction `
            -Trigger $taskTrigger `
            -Principal $taskPrincipal `
            -Settings $taskSettings `
            -Force |
        Out-Null

        Write-Host ""
        Write-Host (
            "Task registration completed."
        )
        Write-Host (
            "Daily time: " +
            $triggerTime.ToString("HH:mm")
        )
        Write-Host (
            "Logon mode: Interactive " +
            "(runs while this user is logged on)"
        )

        Write-TaskStatus
    }

    "Status" {
        Write-TaskStatus
    }

    "RunNow" {
        $task = Get-ReferenceScheduledTask

        if ($null -eq $task) {
            throw (
                "Scheduled task is not registered: " +
                $TaskName
            )
        }

        Start-ScheduledTask `
            -TaskName $TaskName

        Write-Host ""
        Write-Host (
            "Scheduled task start requested: " +
            $TaskName
        )
        Write-Host (
            "Use -Action Status to inspect " +
            "the state and result."
        )
    }

    "Remove" {
        if (-not $ConfirmRemoval) {
            throw (
                "-ConfirmRemoval is required when " +
                "-Action Remove is used."
            )
        }

        $task = Get-ReferenceScheduledTask

        if ($null -eq $task) {
            Write-Host (
                "Scheduled task is already absent: " +
                $TaskName
            )

            return
        }

        Unregister-ScheduledTask `
            -TaskName $TaskName `
            -Confirm:$false

        Write-Host (
            "Scheduled task removed: " +
            $TaskName
        )
    }
}
