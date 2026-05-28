import feedparser, ssl

ssl._create_default_https_context = ssl._create_unverified_context

feeds = {
    'HeavyMusic': 'http://heavymusic.ru/rss.php',
    'VargMetall': 'http://vargmetall.ru/rss.xml',
}

for name, url in feeds.items():
    try:
        feed = feedparser.parse(url)
        print(f'{name}: {len(feed.entries)} entries')
        for entry in feed.entries[:5]:
            title = entry.get("title", "")
            desc = entry.get("description", "") or ""
            print(f'  - {title[:80]}')
            # Check if any of user's bands appear
            artists = ["slipknot", "green day", "hollywood", "korn", "disturbed", "linkin park",
                       "shinedown", "limp bizkit", "metallica", "rammstein", "papa roach",
                       "bringing me the horizon", "evanescence", "avenged sevenfold"]
            combined = (title + " " + desc).lower()
            for a in artists:
                if a in combined:
                    print(f'    MATCH: {a}')
    except Exception as e:
        print(f'{name}: {type(e).__name__}: {e}')
    print()
