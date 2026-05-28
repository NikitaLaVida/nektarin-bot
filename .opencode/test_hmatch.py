import feedparser, ssl

ssl._create_default_https_context = ssl._create_unverified_context

feed = feedparser.parse('http://heavymusic.ru/rss.php')

artists = ["slipknot", "green day", "hollywood undead", "korn", "disturbed", 
           "linkin park", "shinedown", "limp bizkit", "metallica", "rammstein", 
           "papa roach", "evanescence", "avenged sevenfold", "five finger death punch",
           "system of a down", "bring me the horizon", "three days grace",
           "breaking benjamin", "stone sour", "bad omens", "godsmack",
           "i prevail", "motionless in white", "architects"]

print(f'Entries: {len(feed.entries)}')
matches = 0
for entry in feed.entries:
    title = entry.get("title", "")
    desc = entry.get("description", "") or ""
    combined = (title + " " + desc).lower()
    matched = [a for a in artists if a in combined]
    if matched:
        matches += 1
        print(f'  MATCH [{", ".join(matched)}]: {title[:60]}')

print(f'\nTotal matches: {matches}/{len(feed.entries)}')
