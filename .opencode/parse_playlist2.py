import re, json

with open(r'C:\Users\La Vida Loca\.opencode\playlist_page.txt', 'r', encoding='utf-8') as f:
    html = f.read()

# Find push() calls and extract the JSON
pattern = r'__STATE_SNAPSHOT__.*?push\(({.*?})\);'
matches = re.findall(pattern, html, re.DOTALL)

if matches:
    for idx, match_str in enumerate(matches):
        try:
            data = json.loads(match_str)
            print(f'=== Match {idx} ===')
            
            # Recursively search for playlist/track data
            def find_tracks(obj, path=''):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if k == 'tracks' and isinstance(v, list) and len(v) > 0:
                            print(f'Tracks at {path}.{k}:')
                            for t in v[:10]:
                                title = t.get('title', '?')
                                artists = ', '.join(a.get('name', '?') for a in t.get('artists', []))
                                print(f'  {title} - {artists}')
                            if len(v) > 10:
                                print(f'  ... and {len(v)-10} more')
                            return
                        find_tracks(v, f'{path}.{k}')
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        find_tracks(item, f'{path}[{i}]')
            
            find_tracks(data)
            print(f'Top keys: {list(data.keys())}')
            
        except json.JSONDecodeError as e:
            print(f'Match {idx}: JSON error: {e}')
else:
    print('No matches found')
    # Try a simpler approach - find all script tags with push()
    for part in re.split(r'</script>', html):
        if 'push(' in part:
            start = part.find('push(') + 5
            depth = 0
            for i in range(start, len(part)):
                c = part[i]
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        json_str = part[start:i+1]
                        try:
                            data = json.loads(json_str)
                            print(f'Found JSON with keys: {list(data.keys())[:10]}')
                            print(json.dumps(list(data.keys()), ensure_ascii=False)[:500])
                            
                            # Look for playlist/track data
                            def find_tracks(obj, path='', depth=0):
                                if depth > 5: return
                                if isinstance(obj, dict):
                                    if 'tracks' in obj:
                                        tracks = obj['tracks']
                                        if isinstance(tracks, list) and len(tracks) > 0:
                                            print(f'Tracks at {path}: {len(tracks)} tracks')
                                            for t in tracks[:5]:
                                                title = t.get('title', '?')
                                                artists = ', '.join(a.get('name', '?') for a in t.get('artists', []))
                                                print(f'  {title} - {artists}')
                                    for k, v in obj.items():
                                        find_tracks(v, f'{path}.{k}', depth+1)
                                elif isinstance(obj, list):
                                    for i, item in enumerate(obj[:3]):
                                        find_tracks(item, f'{path}[{i}]', depth+1)
                            
                            find_tracks(data)
                            break
                        except json.JSONDecodeError:
                            pass
