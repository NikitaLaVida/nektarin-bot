import feedparser, ssl

ssl._create_default_https_context = ssl._create_unverified_context

# More Russian rock/metal feeds to test
feeds = {
    'Castle Rock HTTP (rss2)': 'http://www.castlerock.ru/rockblog/rss2/',
    'RockArchive': 'https://rockarchive.ru/rss/',
    'AltPal': 'https://altpal.ru/feed/',
    'Musecube': 'https://musecube.org/feed/',
}

for name, url in feeds.items():
    try:
        feed = feedparser.parse(url)
        print(f'{name}: {len(feed.entries)} entries')
        for entry in feed.entries[:3]:
            title = entry.get("title", "")
            print(f'  - {title[:80]}')
    except Exception as e:
        print(f'{name}: {type(e).__name__}: {e}')
    print()
