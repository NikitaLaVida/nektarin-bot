$ErrorActionPreference = "Continue"
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

$bot = "C:\Users\La Vida Loca\.opencode\gaming_news_bot.py"
$python = "C:\Users\La Vida Loca\AppData\Local\Programs\Python\Python313\python.exe"
$log = "C:\Users\La Vida Loca\.opencode\bot_vpn.log"

try {
    Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Running bot..."
    & $python $bot 2>&1 | Out-File -FilePath $log -Encoding utf8
    Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Bot finished"
} catch {
    Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Bot error: $_"
    exit 1
}
