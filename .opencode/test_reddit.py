import requests, json
r = requests.get('https://www.reddit.com/r/gaming/hot.json',
    params={'limit': 10}, timeout=8,
    headers={'User-Agent': 'GamingNewsBot/1.0'})
print('status:', r.status_code)
data = r.json()
posts = data.get('data', {}).get('children', [])
print('posts:', len(posts))
for p in posts:
    d = p['data']
    url = d.get('url', '')
    ext = url.split('.')[-1].lower() if '.' in url else ''
    print(f"  {d.get('title','')[:50]} | ext={ext} | url={url[:60]}")
