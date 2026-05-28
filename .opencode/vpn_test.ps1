$ErrorActionPreference = "Continue"

$tun2socks = "C:\Program Files (x86)\Bebra\resources\app.asar.unpacked\client\output\build\windows\tun2socks.exe"
$store = "$env:APPDATA\Outline\connection_store"

# Read transport config from connection_store
$json = Get-Content $store -Raw | ConvertFrom-Json
$transport = $json.config.transport

Write-Output "Transport prefix: $($transport.Substring(0, 80))..."

# Try starting tun2socks with the transport
Write-Output "Starting tun2socks..."
$proc = Start-Process -FilePath $tun2socks -ArgumentList "-tunName outline-tap0", "-tunAddr 10.0.85.2", "-tunGw 10.0.85.1", "-tunMask 255.255.255.0", "-transport `"$transport`"", "-logLevel debug" -NoNewWindow -PassThru
Write-Output "PID: $($proc.Id)"

Start-Sleep -Seconds 5

Write-Output "Adapter status: $( (Get-NetAdapter -Name 'outline-tap0' -ErrorAction SilentlyContinue).Status )"
Write-Output "tun2socks running: $( (Get-Process -Name tun2socks -ErrorAction SilentlyContinue).Id )"

Write-Output "Done"
