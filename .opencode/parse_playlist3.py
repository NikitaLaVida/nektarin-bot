import re, json

with open(r'C:\Users\La Vida Loca\.opencode\playlist_page.txt', 'r', encoding='utf-8') as f:
    html = f.read()

# Find push() calls and extract the JSON
pattern = r'__STATE_SNAPSHOT__.*?push\(({.*?})\);'
matches = re.findall(pattern, html, re.DOTALL)

if matches:
    data = json.loads(matches[0])
    print(f'=== Keys with track data ===')
    
    # Check favoriteTracks
    ft = data.get('favoriteTracks', {})
    print(f'\nfavoriteTracks type: {type(ft).__name__}')
    print(f'favoriteTracks content: {json.dumps(ft, indent=2, ensure_ascii=False)[:2000]}')
    
    # Check playlist
    pl = data.get('playlist', {})
    print(f'\nplaylist type: {type(pl).__name__}')
    print(f'playlist keys: {list(pl.keys())[:20] if isinstance(pl, dict) else pl}')
    print(f'playlist content: {json.dumps(pl, indent=2, ensure_ascii=False)[:3000]}')
    
    # Check library
    lib = data.get('library', {})
    print(f'\nlibrary type: {type(lib).__name__}')
    print(f'library: {json.dumps(lib, indent=2, ensure_ascii=False)[:2000]}')
    
    # Check myMusic
    mm = data.get('myMusic', {})
    print(f'\nmyMusic type: {type(mm).__name__}')
    print(f'myMusic: {json.dumps(mm, indent=2, ensure_ascii=False)[:2000]}')
else:
    print('No matches')
