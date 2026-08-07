function Test-PrivateIPv4 {
    param([Parameter(Mandatory = $true)][string]$Address)
    $parsed = $null
    if (-not [System.Net.IPAddress]::TryParse($Address, [ref]$parsed)) {
        return $false
    }
    $bytes = $parsed.GetAddressBytes()
    if ($bytes.Length -ne 4) { return $false }
    if ($bytes[0] -eq 127) { return $false }
    if ($bytes[0] -eq 169 -and $bytes[1] -eq 254) { return $false }
    if ($bytes[0] -eq 10) { return $true }
    if ($bytes[0] -eq 192 -and $bytes[1] -eq 168) { return $true }
    if ($bytes[0] -eq 172 -and $bytes[1] -ge 16 -and $bytes[1] -le 31) {
        return $true
    }
    return $false
}

function Get-PrivateIPv4Candidates {
    return @(
        Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object {
                $_.AddressState -eq "Preferred" -and
                (Test-PrivateIPv4 -Address $_.IPAddress)
            } |
            Select-Object -ExpandProperty IPAddress -Unique
    )
}
