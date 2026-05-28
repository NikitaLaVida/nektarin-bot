$ErrorActionPreference = "Continue"
$ifAlias = "outline-tap0"

# First, check current state
Write-Output "=== Current state ==="
Write-Output "Adapter: $( (Get-NetAdapter -Name $ifAlias).Status )"
Write-Output "tun2socks running: $( (Get-Process -Name tun2socks -ErrorAction SilentlyContinue).Id )"
Write-Output "OutlineService running: $( (Get-Process -Name OutlineService -ErrorAction SilentlyContinue).Id )"

# Enable adapter
Write-Output "`n=== Enabling adapter ==="
Enable-NetAdapter -Name $ifAlias -Confirm:$false -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
Write-Output "Adapter: $( (Get-NetAdapter -Name $ifAlias).Status )"
Write-Output "tun2socks running: $( (Get-Process -Name tun2socks -ErrorAction SilentlyContinue).Id )"
$ip = (Get-NetIPAddress -InterfaceAlias $ifAlias -AddressFamily IPv4 -ErrorAction SilentlyContinue).IPAddress
Write-Output "Tunnel IP: $ip"

# Check OutlineService - maybe need to restart?
Write-Output "`n=== OutlineService status ==="
$svc = Get-Service -Name OutlineService
Write-Output "Service: $($svc.Status)"

Write-Output "`n=== Trying to restart OutlineService ==="
Restart-Service -Name OutlineService -Force
Write-Output "Restarted, waiting..."
Start-Sleep -Seconds 5

Write-Output "tun2socks now: $( (Get-Process -Name tun2socks -ErrorAction SilentlyContinue).Id )"
$ip = (Get-NetIPAddress -InterfaceAlias $ifAlias -AddressFamily IPv4 -ErrorAction SilentlyContinue).IPAddress
Write-Output "Tunnel IP after restart: $ip"

# Add routes
Remove-NetRoute -InterfaceAlias $ifAlias -DestinationPrefix "0.0.0.0/1" -Confirm:$false -ErrorAction SilentlyContinue
Remove-NetRoute -InterfaceAlias $ifAlias -DestinationPrefix "128.0.0.0/1" -Confirm:$false -ErrorAction SilentlyContinue
New-NetRoute -InterfaceAlias $ifAlias -DestinationPrefix "0.0.0.0/1" -NextHop "10.0.85.1" -RouteMetric 0 -ErrorAction SilentlyContinue
New-NetRoute -InterfaceAlias $ifAlias -DestinationPrefix "128.0.0.0/1" -NextHop "10.0.85.1" -RouteMetric 0 -ErrorAction SilentlyContinue
Write-Output "Routes added"

# Test Telegram
try {
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
    $r = [System.Net.HttpWebRequest]::Create("https://api.telegram.org")
    $r.Timeout = 8000
    $resp = $r.GetResponse()
    Write-Output "Telegram: $($resp.StatusCode)"
    $resp.Close()
} catch {
    Write-Output "Telegram NOT reachable: $_"
}

Write-Output "`n=== Done ==="
