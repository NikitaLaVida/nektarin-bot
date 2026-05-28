import feedparser, ssl

ssl._create_default_https_context = ssl._create_unverified_context

artists = ["slipknot", "green day", "hollywood undead", "korn", "disturbed", 
           "linkin park", "shinedown", "limp bizkit", "metallica", "rammstein", 
           "papa roach", "evanescence", "avenged sevenfold", "five finger death punch",
           "system of a down", "bring me the horizon", "three days grace",
           "breaking benjamin", "stone sour", "bad omens", "godsmack",
           "i prevail", "motionless in white", "architects"]

feeds_to_test = [
    ('Rock Cult', 'https://rockcult.ru/feed/'),
    ('RockGig', 'https://rockgig.net/rss'),
    ('NME Russia', 'https://www.nme.com/rss/music'),
]

for name, url in feeds_to_test:
    try:
        feed = feedparser.parse(url)
        print(f'{name}: {len(feed.entries)} entries')
        for entry in feed.entries[:20]:
            title = entry.get("title", "")
            desc = entry.get("description", "") or ""
            combined = (title + " " + desc).lower()
            matched = [a for a in artists if a in combined]
            if matched:
                print(f'  MATCH [{", ".join(matched)}]: {title[:60]}')
    except Exception as e:
        print(f'{name}: {type(e).__name__}: {e}')
    print()
