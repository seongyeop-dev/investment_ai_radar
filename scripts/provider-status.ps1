$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "official-provider-common.ps1")
Initialize-OfficialProviderEnvironment
& $script:OfficialProviderPython -m app.cli provider-status
exit $LASTEXITCODE
