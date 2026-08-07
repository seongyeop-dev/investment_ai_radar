$ErrorActionPreference = "Stop"

$Utf8Encoding = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = $Utf8Encoding
[Console]::OutputEncoding = $Utf8Encoding
$OutputEncoding = $Utf8Encoding

$root = Split-Path -Parent $PSScriptRoot
$target = Join-Path $root ".env.local"

function Read-YesNo {
    param([string]$Prompt)

    while ($true) {
        $answer = Read-Host "$Prompt [Y/N]"
        if ($null -eq $answer) {
            Write-Output "입력이 필요합니다. Y 또는 N으로 입력해 주세요."
            continue
        }
        $answer = $answer.Trim().ToUpperInvariant()
        if ($answer -in @("Y", "YES")) { return "Y" }
        if ($answer -in @("N", "NO")) { return "N" }
        Write-Output "Y 또는 N으로 입력해 주세요."
    }
}

function Read-RetryCancel {
    param([string]$Prompt)

    while ($true) {
        $answer = Read-Host "$Prompt [R/C]"
        if ($null -eq $answer) {
            Write-Output "R(재입력) 또는 C(취소)로 입력해 주세요."
            continue
        }
        $answer = $answer.Trim().ToUpperInvariant()
        if ($answer -in @("R", "RETRY")) { return "R" }
        if ($answer -in @("C", "CANCEL")) { return "C" }
        Write-Output "R(재입력) 또는 C(취소)로 입력해 주세요."
    }
}

function Read-SecretText {
    param([string]$Prompt)

    $secure = Read-Host $Prompt -AsSecureString
    $pointer = [IntPtr]::Zero
    try {
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    } finally {
        if ($pointer -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
        }
        if ($null -ne $secure) {
            $secure.Dispose()
        }
    }
}

function Read-OpenDartKey {
    while ($true) {
        $value = Read-SecretText "OpenDART 인증키 40자리를 입력하세요"
        if ($value -match "^[A-Za-z0-9]{40}$") {
            return $value
        }

        $value = $null
        Write-Warning "OpenDART 인증키는 영문·숫자 40자리여야 합니다. 입력값은 표시하지 않습니다."
        if ((Read-RetryCancel "인증키를 다시 입력하거나 설정을 취소하세요") -eq "C") {
            return $null
        }
    }
}

function Read-SecContact {
    $emailPattern = "^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

    while ($true) {
        $value = Read-Host "SEC User-Agent에 사용할 실제 연락 이메일"
        if ($null -ne $value) {
            $value = $value.Trim()
        }

        if ([string]::IsNullOrWhiteSpace($value)) {
            Write-Warning "SEC 연락 이메일은 비워 둘 수 없습니다."
        } elseif ($value -match '["''<>]') {
            Write-Warning "SEC 연락 이메일에는 따옴표나 꺾쇠괄호를 포함할 수 없습니다."
        } elseif ($value -match $emailPattern) {
            return $value
        } else {
            Write-Warning "SEC 연락 이메일 형식이 올바르지 않습니다. 이메일 전체는 표시하지 않습니다."
        }

        $value = $null
        if ((Read-RetryCancel "이메일을 다시 입력하거나 설정을 취소하세요") -eq "C") {
            return $null
        }
    }
}

function Set-EnvironmentLine {
    param(
        [Collections.Generic.List[string]]$Lines,
        [string]$Name,
        [string]$Value
    )

    $pattern = "^\s*" + [Regex]::Escape($Name) + "\s*="
    for ($index = 0; $index -lt $Lines.Count; $index++) {
        if ($Lines[$index] -match $pattern) {
            $Lines[$index] = "$Name=$Value"
            return
        }
    }
    $Lines.Add("$Name=$Value")
}

function Get-EnvironmentValue {
    param(
        [Collections.Generic.List[string]]$Lines,
        [string]$Name
    )

    $pattern = "^\s*" + [Regex]::Escape($Name) + "\s*=(.*)$"
    foreach ($line in $Lines) {
        if ($line -match $pattern) { return $Matches[1].Trim() }
    }
    return ""
}

function Mask-OpenDartKey {
    param([string]$Value)

    if ($Value.Length -ne 40) { return "SET (형식 확인 필요)" }
    return $Value.Substring(0, 4) + ("*" * 32) + $Value.Substring(36, 4)
}

function Mask-Contact {
    param([string]$Value)

    $at = $Value.IndexOf("@")
    if ($at -lt 1) { return "SET (형식 확인 필요)" }
    return $Value.Substring(0, 1) + "***" + $Value.Substring($at)
}

function Set-PrivateFileAcl {
    param([string]$Path)

    $acl = [Security.AccessControl.FileSecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $rule = [Security.AccessControl.FileSystemAccessRule]::new(
        $identity,
        [Security.AccessControl.FileSystemRights]::FullControl,
        [Security.AccessControl.AccessControlType]::Allow
    )
    $acl.SetAccessRule($rule)
    Set-Acl -LiteralPath $Path -AclObject $acl
}

function Write-EnvironmentFileAtomically {
    param(
        [string]$Path,
        [string]$Content
    )

    $directory = Split-Path -Parent $Path
    $temporaryPath = Join-Path $directory (
        ".official-provider-config-" + [Guid]::NewGuid().ToString("N") + ".tmp"
    )
    $backupPath = Join-Path $directory (
        ".official-provider-backup-" + [Guid]::NewGuid().ToString("N") + ".tmp"
    )
    try {
        $utf8NoBom = [Text.UTF8Encoding]::new($false)
        [IO.File]::WriteAllText($temporaryPath, $Content, $utf8NoBom)
        Set-PrivateFileAcl -Path $temporaryPath

        if ([IO.File]::Exists($Path)) {
            [IO.File]::Replace($temporaryPath, $Path, $backupPath)
        } else {
            [IO.File]::Move($temporaryPath, $Path)
        }
    } finally {
        try {
            if ([IO.File]::Exists($temporaryPath)) {
                [IO.File]::Delete($temporaryPath)
            }
        } finally {
            if ([IO.File]::Exists($backupPath)) {
                [IO.File]::Delete($backupPath)
            }
        }
    }
}

function Invoke-OfficialProviderConfiguration {
    $lines = [Collections.Generic.List[string]]::new()
    $openDartKey = $null
    $secContact = $null
    $content = $null

    try {
        if (Test-Path -LiteralPath $target) {
            foreach ($line in Get-Content -LiteralPath $target -Encoding utf8) {
                $lines.Add($line)
            }
        } else {
            $lines.Add("# Investment AI Radar server-only local settings")
        }

        $existingOpenDartKey = Get-EnvironmentValue -Lines $lines -Name "OPENDART_API_KEY"
        $existingSecContact = Get-EnvironmentValue -Lines $lines -Name "SEC_USER_AGENT_CONTACT"

        $openDartEnabled = (
            Read-YesNo "OpenDART 공식 공시 Provider를 활성화할까요?"
        ) -eq "Y"
        if ($openDartEnabled) {
            $openDartKey = Read-OpenDartKey
            if ($null -eq $openDartKey) {
                Write-Output "설정을 취소했습니다. 파일은 변경되지 않았습니다. [CANCELLED]"
                return
            }
        } else {
            $openDartKey = $existingOpenDartKey
        }

        $secEnabled = (
            Read-YesNo "SEC EDGAR 공개 조회 Provider를 활성화할까요?"
        ) -eq "Y"
        if ($secEnabled) {
            $secContact = Read-SecContact
            if ($null -eq $secContact) {
                Write-Output "설정을 취소했습니다. 파일은 변경되지 않았습니다. [CANCELLED]"
                return
            }
        } else {
            $secContact = $existingSecContact
        }

        $officialEnabled = (
            Read-YesNo "공식 공시 자동 동기화를 활성화할까요?"
        ) -eq "Y"

        Set-EnvironmentLine $lines "OPENDART_ENABLED" $openDartEnabled.ToString().ToLowerInvariant()
        if ($openDartEnabled) {
            Set-EnvironmentLine $lines "OPENDART_API_KEY" $openDartKey
        }
        Set-EnvironmentLine $lines "SEC_EDGAR_ENABLED" $secEnabled.ToString().ToLowerInvariant()
        Set-EnvironmentLine $lines "SEC_USER_AGENT_APP_NAME" "InvestmentAIRadar"
        if ($secEnabled) {
            Set-EnvironmentLine $lines "SEC_USER_AGENT_CONTACT" $secContact
        }
        Set-EnvironmentLine $lines "OFFICIAL_DISCLOSURE_SYNC_ENABLED" $officialEnabled.ToString().ToLowerInvariant()

        Write-Output ""
        Write-Output "저장 Preview [PREVIEW]"
        Write-Output ("OpenDART: " + $(if ($openDartEnabled) { "ENABLED" } else { "DISABLED" }))
        Write-Output ("OpenDART Key: " + $(if ($openDartKey) { Mask-OpenDartKey $openDartKey } else { "NOT_SET" }))
        Write-Output ("SEC: " + $(if ($secEnabled) { "ENABLED" } else { "DISABLED" }))
        Write-Output ("SEC Contact: " + $(if ($secContact) { Mask-Contact $secContact } else { "NOT_SET" }))
        Write-Output ("Official sync: " + $(if ($officialEnabled) { "ENABLED" } else { "DISABLED" }))

        if ((Read-YesNo "이 설정을 로컬 Secret 파일에 저장할까요?") -ne "Y") {
            Write-Output "저장하지 않았습니다. 파일은 변경되지 않았습니다. [CANCELLED]"
            return
        }

        $content = ($lines -join [Environment]::NewLine) + [Environment]::NewLine
        Write-EnvironmentFileAtomically -Path $target -Content $content
        Write-Output "저장 완료: .env.local [CONFIGURED]"
    } finally {
        $openDartKey = $null
        $secContact = $null
        $existingOpenDartKey = $null
        $existingSecContact = $null
        $content = $null
    }
}

try {
    Invoke-OfficialProviderConfiguration
} catch {
    Write-Error "공식 Provider 설정을 저장하지 못했습니다. 기존 파일은 유지되며 입력값은 출력되지 않습니다. [FAILED]"
    exit 1
}
