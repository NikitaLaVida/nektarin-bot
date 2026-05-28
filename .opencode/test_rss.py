import urllib.request, feedparser, ssl

ssl._create_default_https_context = ssl._create_unverified_context

feeds = {
    'Castle Rock': 'https://www.castlerock.ru/rockblog/feed/',
    'Varg Metall': 'http://vargmetall.ru/rss.xml',
    'HeavyMusic': 'http://heavymusic.ru/rss.xml',
}

for name, url in feeds.items():
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=10)
        content = resp.read().decode('utf-8', errors='replace')
        f = feedparser.parse(content)
        entries = f.entries[:5]
        print(f'{name}: {len(f.entries)} entries')
        for e in entries:
            title = e.get('title', '?')
            print(f'  - {title[:80]}')
    except Exception as e:
        print(f'{name}: {type(e).__name__}: {e}')
    print()
