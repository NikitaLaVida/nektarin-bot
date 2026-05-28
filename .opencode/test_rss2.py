import urllib.request, feedparser, ssl, re

ssl._create_default_https_context = ssl._create_unverified_context

# Find Castle Rock feed
url = 'https://www.castlerock.ru/rockblog/novosti-roka/'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
resp = urllib.request.urlopen(req, timeout=10)
html = resp.read().decode('utf-8', errors='replace')

feeds = re.findall(r'<link[^>]*application/rss[^>]*>', html)
for f in feeds:
    print(f'RSS link: {f}')

feed_urls = re.findall(r'href=["\']([^"\']*(?:rss|feed|atom)[^"\']*)["\']', html, re.IGNORECASE)
for u in feed_urls[:10]:
    print(f'Potential feed: {u}')

# Try different feed URLs
test_feeds = [
    ('Castle Rock /feed', 'https://www.castlerock.ru/feed/'),
    ('Castle Rock /rss', 'https://www.castlerock.ru/rss/'),
    ('Castle Rock ?feed=rss', 'https://www.castlerock.ru/?feed=rss'),
]

for name, url in test_feeds:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=10)
        content = resp.read().decode('utf-8', errors='replace')
        f = feedparser.parse(content)
        print(f'{name}: {len(f.entries)} entries')
        for e in f.entries[:3]:
            print(f'  - {e.get("title", "?")[:80]}')
    except Exception as e:
        print(f'{name}: {type(e).__name__}: {e}')
