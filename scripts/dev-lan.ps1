param(
    [string]$Address = "",
    [switch]$UseLocalDatabase,
    [switch]$UseRealDatabase,
    [switch]$ProductionWeb
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "lan-common.ps1")

$expectedDatabaseRevision = "20260803_0017"
$databaseValidator = Join-Path `
    $root `
    "server\scripts\validate_runtime_database.py"
$realDatabasePath = [IO.Path]::GetFullPath(
    (Join-Path $root ".local\data\investment_ai_radar.db")
)
$lanDataDirectory = [IO.Path]::GetFullPath(
    (Join-Path $root ".local\data\lan")
)
$lanDatabasePath = [IO.Path]::GetFullPath(
    (
        Join-Path `
            $lanDataDirectory `
            "investment_ai_radar_lan.db"
    )
)

function Test-SameDatabasePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Left,

        [Parameter(Mandatory = $true)]
        [string]$Right
    )

    return [string]::Equals(
        [IO.Path]::GetFullPath($Left),
        [IO.Path]::GetFullPath($Right),
        [StringComparison]::OrdinalIgnoreCase
    )
}

function Get-SqliteDatabasePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DatabaseUrl
    )

    foreach ($prefix in @(
        "sqlite+pysqlite:///",
        "sqlite:///"
    )) {
        if ($DatabaseUrl.StartsWith(
            $prefix,
            [StringComparison]::OrdinalIgnoreCase
        )) {
            $rawPath = $DatabaseUrl.Substring(
                $prefix.Length
            )
            $decodedPath = [Uri]::UnescapeDataString(
                $rawPath
            )

            if ($decodedPath -match "^/[A-Za-z]:/") {
                $decodedPath = $decodedPath.Substring(1)
            }

            return [IO.Path]::GetFullPath(
                $decodedPath.Replace("/", "\")
            )
        }
    }

    return $null
}

if ($UseLocalDatabase -and $UseRealDatabase) {
    throw (
        "-UseLocalDatabase and -UseRealDatabase " +
        "cannot be used together."
    )
}

if (Test-SameDatabasePath `
    -Left $lanDatabasePath `
    -Right $realDatabasePath
) {
    throw "LAN development database must differ from the real database."
}

$candidates = @(Get-PrivateIPv4Candidates)
if ($Address) {
    if (-not (Test-PrivateIPv4 -Address $Address) -or $Address -notin $candidates) {
        throw "현재 PC에서 사용 가능한 사설 IPv4가 아닙니다: $Address"
    }
} elseif ($candidates.Count -eq 1) {
    $Address = $candidates[0]
} elseif ($candidates.Count -gt 1) {
    Write-Output "사용 가능한 사설 IPv4:"
    $candidates | ForEach-Object { Write-Output "  $_" }
    throw "scripts\dev-lan.ps1 -Address <사설 IPv4>로 하나를 선택하세요."
} else {
    throw "사용 가능한 사설 IPv4를 찾지 못했습니다."
}

if (Get-NetTCPConnection -State Listen -LocalPort 3000 -ErrorAction SilentlyContinue) {
    throw "포트 3000이 이미 사용 중입니다. 다른 프로그램을 자동 종료하지 않습니다."
}
if (Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue) {
    throw "포트 8000이 이미 사용 중입니다. 다른 프로그램을 자동 종료하지 않습니다."
}

$python = Join-Path $root "server\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "server\.venv Python을 찾을 수 없습니다."
}
if (-not (
    Test-Path `
        -LiteralPath $databaseValidator `
        -PathType Leaf
)) {
    throw "Runtime database validator를 찾을 수 없습니다."
}

$databaseMode = "CONFIGURED_DATABASE"
$databasePath = $null
$configuredDatabaseUrl = $env:DATABASE_URL
if ($UseLocalDatabase) {
    $projectPrefix = [IO.Path]::GetFullPath($root).TrimEnd(
        [IO.Path]::DirectorySeparatorChar
    ) + [IO.Path]::DirectorySeparatorChar
    if (-not $lanDataDirectory.StartsWith(
        $projectPrefix,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "LAN 데이터 경로가 프로젝트 밖을 가리킵니다."
    }
    if (-not (Test-Path -LiteralPath $lanDataDirectory)) {
        New-Item `
            -ItemType Directory `
            -Path $lanDataDirectory `
            -Force |
            Out-Null
    }
    $databasePath = $lanDatabasePath
    $databaseUrlPath = $databasePath.Replace("\", "/")
    $env:DATABASE_URL = "sqlite+pysqlite:///$databaseUrlPath"
    if ([string]::IsNullOrWhiteSpace($env:APP_ENV)) {
        $env:APP_ENV = "development"
    }
    $databaseMode = "LAN_DEVELOPMENT_SQLITE"
} elseif ($UseRealDatabase) {
    $databasePath = $realDatabasePath
    $databaseUrlPath = $databasePath.Replace("\", "/")
    $env:DATABASE_URL = "sqlite+pysqlite:///$databaseUrlPath"
    $databaseMode = "REAL_DATABASE_LAN"
} elseif ([string]::IsNullOrWhiteSpace($configuredDatabaseUrl)) {
    throw (
        "DATABASE_URL이 없습니다. LAN 개발 DB는 " +
        "-UseLocalDatabase 옵션으로 명시하세요."
    )
} else {
    $configuredDatabasePath = Get-SqliteDatabasePath `
        -DatabaseUrl $configuredDatabaseUrl.Trim()

    if (
        $null -ne $configuredDatabasePath -and
        (Test-SameDatabasePath `
            -Left $configuredDatabasePath `
            -Right $realDatabasePath
        )
    ) {
        throw (
            "The real database requires the explicit " +
            "-UseRealDatabase flag for LAN access."
        )
    }
}

if ($UseRealDatabase) {
    & $python `
        $databaseValidator `
        --database-path `
        $realDatabasePath `
        --expected-revision `
        $expectedDatabaseRevision

    if ($LASTEXITCODE -ne 0) {
        throw (
            "Real database LAN validation failed. " +
            "No API or Web process was started."
        )
    }

    $migrationRevision = $expectedDatabaseRevision
}
elseif ($UseLocalDatabase) {
    Push-Location (Join-Path $root "server")
    try {
        $previousErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $currentResult = @(& $python -m alembic current 2>&1)
        $currentExitCode = $LASTEXITCODE
        $upgradeResult = @(& $python -m alembic upgrade head 2>&1)
        $upgradeExitCode = $LASTEXITCODE
        $revisionResult = @(& $python -m alembic current 2>&1)
        $revisionExitCode = $LASTEXITCODE
        $ErrorActionPreference = $previousErrorActionPreference
        if ($currentExitCode -ne 0) {
            throw "Alembic current 확인에 실패했습니다."
        }
        if ($upgradeExitCode -ne 0) {
            throw "Alembic migration 적용에 실패했습니다."
        }
        if ($revisionExitCode -ne 0) {
            throw "Alembic 적용 결과 확인에 실패했습니다."
        }
        $migrationRevision = (
            $revisionResult |
                Where-Object { $_ -match "^[0-9_]+ \(head\)$" } |
                Select-Object -Last 1
        )
        if (-not $migrationRevision) {
            throw "Alembic head revision을 확인할 수 없습니다."
        }
    } finally {
        if ($previousErrorActionPreference) {
            $ErrorActionPreference = $previousErrorActionPreference
        }
        Pop-Location
    }
}

$npm = (Get-Command npm.cmd -ErrorAction Stop).Source
$origin = "http://${Address}:3000"
$env:ALLOWED_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000,$origin"
$env:NEXT_PUBLIC_API_BASE_URL = "http://${Address}:8000"
$env:MARKET_CALENDAR_ENABLED = if ([string]::IsNullOrWhiteSpace(
    $env:MARKET_CALENDAR_ENABLED
)) { "true" } else { $env:MARKET_CALENDAR_ENABLED }
$webMode = if ($ProductionWeb) { "PRODUCTION" } else { "DEVELOPMENT" }

if ($ProductionWeb) {
    Push-Location (Join-Path $root "web")
    try {
        $previousErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & $npm run build
        $buildExitCode = $LASTEXITCODE
        $ErrorActionPreference = $previousErrorActionPreference
        if ($buildExitCode -ne 0) {
            throw "Next.js production build에 실패해 LAN 서버를 시작하지 않습니다."
        }
    } finally {
        if ($previousErrorActionPreference) {
            $ErrorActionPreference = $previousErrorActionPreference
        }
        Pop-Location
    }
}

$server = Start-Process -FilePath $python `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000") `
    -WorkingDirectory (Join-Path $root "server") -PassThru -WindowStyle Hidden
$webArguments = if ($ProductionWeb) {
    @("run", "start", "--", "--hostname", "0.0.0.0", "--port", "3000")
} else {
    @("run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000")
}
$web = Start-Process -FilePath $npm `
    -ArgumentList $webArguments `
    -WorkingDirectory (Join-Path $root "web") -PassThru -WindowStyle Hidden

@{
    projectRoot = $root
    address = $Address
    serverPid = $server.Id
    webPid = $web.Id
    databaseMode = $databaseMode
    webMode = $webMode
    startedAt = (Get-Date).ToString("o")
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root ".dev-lan-processes.json") -Encoding utf8

if ($UseLocalDatabase -or $UseRealDatabase) {
    Write-Output "LAN database: READY"
    Write-Output "Database mode: $databaseMode"
    Write-Output "Migration: $migrationRevision"
    if ($UseLocalDatabase) {
        Write-Output (
            "LAN data file: " +
            ".local\data\lan\investment_ai_radar_lan.db"
        )
    } else {
        Write-Output "Real data file: .local\data\investment_ai_radar.db"
        Write-Output "Automatic migration: DISABLED"
    }
}
Write-Output "Web mode: $webMode"
Write-Output "핸드폰 접속: http://${Address}:3000/portfolio"
Write-Output "API: http://${Address}:8000/health"
Write-Output "같은 신뢰 가능한 Wi-Fi에서만 사용하세요."
Write-Output "방화벽·라우터 설정은 변경하지 않았으며 인터넷 외부 공개 방식이 아닙니다."
Write-Output "PC가 꺼지거나 개발 프로세스가 종료되면 접속할 수 없습니다."
