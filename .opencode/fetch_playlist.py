import urllib.request, re, json

url = 'https://music.yandex.ru/playlists/lk.22f3807d-640c-445c-999d-cdb20bd11599'
req = urllib.request.Request(url, headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
})
resp = urllib.request.urlopen(req, timeout=15)
html = resp.read().decode('utf-8', errors='replace')
print(f'HTML size: {len(html)}')

# Look for __NEXT_DATA__
matches = re.findall(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
if matches:
    print(f'Found __NEXT_DATA__ ({len(matches[0])} chars)')
    try:
        data = json.loads(matches[0])
        props = data.get('props', {}).get('pageProps', {})
        print('pageProps:', json.dumps(props, indent=2, ensure_ascii=False)[:5000])
    except Exception as e:
        print(f'JSON decode error: {e}')
        print(matches[0][:2000])
else:
    print('No __NEXT_DATA__ found')
    # Look for any JSON data in script tags
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    for i, script in enumerate(scripts):
        if 'track' in script.lower() or 'playlist' in script.lower():
            print(f'Script {i} has track/playlist data ({len(script)} chars)')
            print(script[:1000])
            break
    
    # Look for playlist keywords
    txt_file = r'C:\Users\La Vida Loca\.opencode\playlist_page.txt'
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'Full HTML saved to {txt_file}')
    
    # Search for key terms in saved file
    for keyword in ['трек', 'Мой плейлист', 'Любимые', 'плейлист', 'track']:
        idx = html.find(keyword)
        if idx >= 0:
            print(f'Found "{keyword}" at {idx}')
            print(html[max(0,idx-50):idx+200])
            break
