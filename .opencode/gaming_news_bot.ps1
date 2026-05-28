param(
    [string]$BotToken = "",
    [string]$ChannelID = "@NektarinGaming"
)

# === НАСТРОЙКИ ===
# 1. Получи токен у @BotFather в Telegram
# 2. Добавь бота в админы канала
# 3. Замени "ТВОЙ_ТОКЕН" на реальный токен

$DefaultToken = "ТВОЙ_ТОКЕН"  # ← ВСТАВЬ ТОКЕН СЮДА
if ($BotToken -eq "") { $BotToken = $DefaultToken }
if ($BotToken -eq "ТВОЙ_ТОКЕН") {
    Write-Host "❌ Ошибка: не указан токен бота."
    Write-Host "Напиши @BotFather в Telegram, создай бота и вставь токен в скрипт."
    exit 1
}

$RssFeeds = @(
    "https://www.igromania.ru/rss/news.xml",
    "https://www.goha.ru/rss/news"
)

$StateFile = "$env:USERPROFILE\.opencode\bot_state.json"
$MaxPosts = 3  # сколько постов за раз

# === ЗАГРУЗКА СОСТОЯНИЯ (какие новости уже постили) ===
$seen = @{}
if (Test-Path $StateFile) {
    try {
        $seen = Get-Content $StateFile -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
    } catch { $seen = @{} }
}

function Save-State {
    $seen | ConvertTo-Json -Compress | Set-Content $StateFile -Encoding UTF8
}

# === ПОЛУЧЕНИЕ RSS ===
function Get-RssItems {
    $allItems = @()
    foreach ($feed in $RssFeeds) {
        try {
            Write-Host "📡 Загрузка: $feed"
            $xml = [System.Xml.XmlDocument]::new()
            $xml.Load($feed)
            $items = $xml.rss.channel.item
            foreach ($item in $items) {
                $title = $item.title.'#cdata-section'
                if (-not $title) { $title = $item.title }
                $link = $item.link
                $desc = $item.description.'#cdata-section'
                if (-not $desc) { $desc = $item.description }
                $pubDate = $item.pubDate

                if ($title -and $link) {
                    $allItems += [PSCustomObject]@{
                        Title = $title.Trim()
                        Link  = $link.Trim()
                        Desc  = if ($desc) { ($desc -replace '<[^>]+>', '').Trim().Substring(0, [Math]::Min(($desc -replace '<[^>]+>', '').Trim().Length, 200)) } else { "" }
                        Date  = $pubDate
                        Source = if ($feed -match "igromania") { "🎮 Igromania" } else { "🕹️ GoHa" }
                    }
                }
            }
            Write-Host "  ✅ Загружено: $($items.Count) новостей"
        } catch {
            Write-Host "  ❌ Ошибка загрузки $feed : $_"
        }
    }
    return $allItems | Sort-Object Date -Descending
}

# === ОТПРАВКА В TELEGRAM ===
function Send-Telegram {
    param($Title, $Link, $Source)
    $msg = "$Source $Title`n🔗 $Link"

    $body = @{
        chat_id = $ChannelID
        text    = $msg
    } | ConvertTo-Json

    try {
        $url = "https://api.telegram.org/bot$BotToken/sendMessage"
        $response = Invoke-RestMethod -Uri $url -Method Post -Body $body -ContentType "application/json" -ErrorAction Stop
        Write-Host "  ✅ Отправлено: $Title"
        return $true
    } catch {
        Write-Host "  ❌ Ошибка отправки: $_"
        return $false
    }
}

# === ГЛАВНАЯ ===
Write-Host "=== 🎮 Gaming News Bot ==="
Write-Host "Канал: $ChannelID"
Write-Host ""

$news = Get-RssItems
Write-Host ""
Write-Host "Всего новостей: $($news.Count)"

$posted = 0
foreach ($item in $news) {
    $id = $item.Link -replace '[^a-zA-Z0-9]', ''
    if ($seen.ContainsKey($id)) { continue }

    if ($posted -ge $MaxPosts) { break }

    $ok = Send-Telegram -Title $item.Title -Link $item.Link -Source $item.Source
    if ($ok) {
        $seen[$id] = $true
        $posted++
        Start-Sleep -Seconds 2
    }
}

Save-State
Write-Host ""
Write-Host "✅ Отправлено новых новостей: $posted"
Write-Host "📊 Всего в истории: $($seen.Count)"
