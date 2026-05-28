import requests, feedparser

url = 'http://www.castlerock.ru/rockblog/rss/'
try:
    r = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
    r.encoding = 'windows-1251'
    feed = feedparser.parse(r.text)
    print(f'Castle Rock: {len(feed.entries)} entries')
    for entry in feed.entries[:5]:
        print(f'  - {entry.get("title", "")[:80]}')
except Exception as e:
    print(f'Error: {e}')

# Try more Russian feeds
feeds_to_try = [
    ('Varg Metall', 'http://vargmetall.ru/rss.xml'),
    ('Castle Rock HTTP', 'http://www.castlerock.ru/rockblog/rss/'),
    ('HeavyMusic', 'http://heavymusic.ru/rss.php'),
    ('Rocksound', 'https://rocksound.tv/feed/'),
    ('MetalKings', 'https://metalkings.org/rss/'),
]

for name, url in feeds_to_try:
    try:
        r = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        r.encoding = 'utf-8'
        feed = feedparser.parse(r.text)
        print(f'{name}: {len(feed.entries)} entries')
        for entry in feed.entries[:3]:
            print(f'  - {entry.get("title", "")[:70]}')
    except Exception as e:
        print(f'{name}: {type(e).__name__}')
    print()
