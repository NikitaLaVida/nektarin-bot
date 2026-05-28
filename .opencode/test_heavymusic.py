import feedparser, ssl

ssl._create_default_https_context = ssl._create_unverified_context

feed = feedparser.parse('http://heavymusic.ru/rss.php')
print(f'Encoding: {feed.encoding}')
print(f'Entries: {len(feed.entries)}')
for entry in feed.entries[:5]:
    title = entry.get("title", "")
    desc = entry.get("description", "") or ""
    print(f'  Title: {title[:80]}')
    artists = ["slipknot", "green day", "hollywood undead", "korn", "disturbed", 
               "linkin park", "shinedown", "limp bizkit", "metallica", "rammstein", 
               "papa roach", "evanescence", "avenged sevenfold", "five finger",
               "system of a down", "bring me the horizon"]
    combined = (title + " " + desc).lower()
    for a in artists:
        if a in combined:
            print(f'    MATCH: {a}!')

if feed.entries:
    first = feed.entries[0]
    desc = first.get("description", "")
    print(f'\nFirst desc sample: {desc[:200]}')
