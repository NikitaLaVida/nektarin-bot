import requests, feedparser, re

url = 'https://metalkings.org/news/'
r = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
r.encoding = 'utf-8'
html = r.text

# Find RSS/feed links
feeds = re.findall(r'href=["\']([^"\']*(?:rss|feed|atom)[^"\']*)["\']', html, re.IGNORECASE)
print(f'Feeds found: {feeds}')

# Try some common RSS paths
rss_urls = [
    'https://metalkings.org/rss/',
    'https://metalkings.org/rss.xml',
    'https://metalkings.org/feed/',
    'https://metalkings.org/feed',
]

for u in rss_urls:
    try:
        rr = requests.get(u, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        if rr.status_code == 200:
            feed = feedparser.parse(rr.text)
            print(f'{u}: {len(feed.entries)} entries')
            if feed.entries:
                print(f'  First: {feed.entries[0].get("title", "")[:70]}')
    except Exception as e:
        print(f'{u}: {type(e).__name__}')

# Also check the page for article content
if not feeds:
    # Look for any post/article content
    titles = re.findall(r'<h[23][^>]*>(.*?)</h[23]>', html, re.DOTALL)
    print(f'\nPage titles (first 10):')
    for t in titles[:10]:
        t = re.sub(r'<[^>]+>', '', t).strip()
        if t:
            print(f'  - {t[:80]}')

    # Check for any article links
    links = re.findall(r'href=["\'](/news/[^"\']+)["\']', html)
    if links:
        print(f'\nNews links (first 5):')
        for l in links[:5]:
            print(f'  - {l}')
