import feedparser, ssl

ssl._create_default_https_context = ssl._create_unverified_context

feed = feedparser.parse("http://www.castlerock.ru/rockblog/rss/")
print(f'Encoding: {feed.encoding}')
print(f'Entries: {len(feed.entries)}')
for entry in feed.entries[:10]:
    title = entry.get("title", "")
    print(f'Title: {repr(title)}')
print()

# Check what artists appear in titles
all_text = " ".join(e.get("title", "") + " " + e.get("description", "") for e in feed.entries)
print(f'Total text length: {len(all_text)}')
print(f'Sample: {all_text[:500]}')

# Check for our artist names
artists = ["slipknot", "green day", "hollywood", "korn", "disturbed", "linkin park",
           "system", "shinedown", "papa roach", "rammstein", "metallica", "foo fighter"]
for a in artists:
    if a.lower() in all_text.lower():
        print(f'  Found: {a}')
