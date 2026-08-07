function Initialize-OfficialProviderEnvironment {
    $script:OfficialProviderRoot = Split-Path -Parent $PSScriptRoot
    $script:OfficialProviderPython = Join-Path (
        $script:OfficialProviderRoot
    ) "server\.venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $script:OfficialProviderPython)) {
        throw "server .venv Python을 찾을 수 없습니다."
    }
    if ([string]::IsNullOrWhiteSpace($env:DATABASE_URL)) {
        $databasePath = Join-Path (
            $script:OfficialProviderRoot
        ) ".local\data\investment_ai_radar.db"
        if (Test-Path -LiteralPath $databasePath) {
            $normalized = [IO.Path]::GetFullPath($databasePath).Replace("\", "/")
            $env:DATABASE_URL = "sqlite+pysqlite:///$normalized"
        }
    }
    Set-Location (Join-Path $script:OfficialProviderRoot "server")
}
