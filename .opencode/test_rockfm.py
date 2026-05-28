import urllib.request, re, ssl

ssl._create_default_https_context = ssl._create_unverified_context

url = 'https://www.rockfm.ru/'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
resp = urllib.request.urlopen(req, timeout=10)
html = resp.read().decode('utf-8', errors='replace')

feeds = re.findall(r'href=["\'](/?[^"\']*(?:rss|feed|atom)[^"\']*)["\']', html, re.IGNORECASE)
for u in feeds:
    print(f'Feed URL: {u}')

if not feeds:
    print('No RSS feeds found on ROCK FM')
    print(f'HTML size: {len(html)}')
    # Check if they have JSON API or other
    api = re.findall(r'href=["\'](/?api[^"\']*)["\']', html, re.IGNORECASE)
    for u in api:
        print(f'API: {u}')
