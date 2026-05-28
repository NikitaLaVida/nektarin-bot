import re, json

with open(r'C:\Users\La Vida Loca\.opencode\playlist_page.txt', 'r', encoding='utf-8') as f:
    html = f.read()

# Find __STATE_SNAPSHOT__
matches = re.findall(r'window\.__STATE_SNAPSHOT__\s*=\s*window\.__STATE_SNAPSHOT__\s*\|\|\s*\[\]\)\.push\(({.*})\);', html, re.DOTALL)
if not matches:
    # Try simpler pattern
    matches = re.findall(r'__STATE_SNAPSHOT__.*?push\(({.*?})\);', html, re.DOTALL)

if matches:
    data = json.loads(matches[0])
    print(f'State snapshot keys: {list(data.keys())}')
    
    # Look for playlist data in the snapshot
    if 'playlist' in data:
        print('Found playlist:', json.dumps(data['playlist'], indent=2, ensure_ascii=False)[:2000])
    
    # Look for tracks anywhere
    for key, val in data.items():
        if isinstance(val, dict):
            if 'tracks' in val or 'trackIds' in val or 'playlist' in val:
                print(f'Key {key} has tracks: {json.dumps(val, indent=2, ensure_ascii=False)[:2000]}')
            for subkey, subval in val.items():
                if subkey == 'tracks' and isinstance(subval, list):
                    print(f'Found tracks in {key}.{subkey}: {len(subval)} tracks')
                    for t in subval[:5]:
                        title = t.get('title', 'N/A')
                        artists = ', '.join(a['name'] for a in t.get('artists', []))
                        print(f'  {title} - {artists}')
                    print('...')
    
    # Print all top-level keys and their types
    for key, val in data.items():
        if isinstance(val, dict):
            subkeys = list(val.keys())[:5]
            print(f'{key}: dict with keys {subkeys}')
        elif isinstance(val, list):
            print(f'{key}: list with {len(val)} items')
        else:
            print(f'{key}: {type(val).__name__} = {str(val)[:100]}')
else:
    print('Could not find __STATE_SNAPSHOT__')
    # Look for any JSON data in script tags
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    for i, script in enumerate(scripts):
        if 'track' in script.lower() or 'playlist' in script.lower():
            print(f'Script {i}: first 500 chars')
            print(script[:500])
            print('---')
