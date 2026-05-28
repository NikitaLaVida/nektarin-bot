$ErrorActionPreference = "Continue"
$outline = "C:\Program Files (x86)\Bebra\OutlineService.exe"
$proxyIp = "51.146.245.78"
$gwIfIndex = (Get-NetRoute -DestinationPrefix "0.0.0.0/0" | Where-Object { $_.InterfaceAlias -ne "outline-tap0" } | Select-Object -First 1).ifIndex
Write-Output "Gateway ifIndex: $gwIfIndex"

# Current state
Write-Output "=== Before ==="
Get-NetAdapter -Name "outline-tap0" -ErrorAction SilentlyContinue | Select-Object Name, Status
Get-Process -Name tun2socks -ErrorAction SilentlyContinue | Select-Object Name, Id
Get-NetRoute -InterfaceAlias "outline-tap0" -ErrorAction SilentlyContinue | Format-Table DestinationPrefix, NextHop

# Enable adapter first (in case it's disabled)
Write-Output "`nEnabling adapter..."
Enable-NetAdapter -Name "outline-tap0" -Confirm:$false -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Turn ON
Write-Output "`n=== OutlineService on $proxyIp ==="
& $outline on $proxyIp
Write-Output "Exit code: $LASTEXITCODE"
Start-Sleep -Seconds 5

Write-Output "`n=== After ==="
Get-NetAdapter -Name "outline-tap0" -ErrorAction SilentlyContinue | Select-Object Name, Status
Get-Process -Name tun2socks -ErrorAction SilentlyContinue | Select-Object Name, Id
Get-NetIPAddress -InterfaceAlias "outline-tap0" -AddressFamily IPv4 -ErrorAction SilentlyContinue | Select-Object IPAddress
Get-NetRoute -InterfaceAlias "outline-tap0" -ErrorAction SilentlyContinue | Format-Table DestinationPrefix, NextHop, RouteMetric

# Test connectivity
try {
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
    $r = [System.Net.HttpWebRequest]::Create("https://api.telegram.org")
    $r.Timeout = 8000
    $resp = $r.GetResponse()
    Write-Output "`nTelegram: $($resp.StatusCode)"
    $resp.Close()
} catch {
    Write-Output "`nTelegram: FAILED - $_"
}
