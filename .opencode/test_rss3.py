import urllib.request, feedparser, ssl

ssl._create_default_https_context = ssl._create_unverified_context

feeds = {
    'Castle Rock RSS': 'https://www.castlerock.ru/rockblog/rss/',
    'Castle Rock HTTP': 'http://www.castlerock.ru/rockblog/rss/',
    'Altwall': 'https://altwall.net/rss.xml',
    'Rocksound': 'https://rocksound.tv/feed/',
    'Ultimate Guitar': 'https://www.ultimate-guitar.com/rss/news',
    'NME': 'https://www.nme.com/music/feed',
    'Rock Cult': 'https://rockcult.ru/feed/',
}

for name, url in feeds.items():
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=15)
        content = resp.read().decode('utf-8', errors='replace')
        f = feedparser.parse(content)
        print(f'{name}: {len(f.entries)} entries')
        for e in f.entries[:3]:
            print(f'  - {e.get("title", "?")[:80]}')
    except Exception as e:
        print(f'{name}: {type(e).__name__}: {e}')
    print()
