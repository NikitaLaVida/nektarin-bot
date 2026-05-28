import feedparser, urllib.request

url = 'http://www.castlerock.ru/rockblog/rss/'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
resp = urllib.request.urlopen(req, timeout=15)
raw = resp.read()

# The RSS says encoding=windows-1251
text = raw.decode('windows-1251', errors='replace')
feed = feedparser.parse(text)

artists = ["slipknot", "green day", "hollywood undead", "korn", "disturbed", 
           "linkin park", "shinedown", "limp bizkit", "metallica", "rammstein", 
           "papa roach", "evanescence", "avenged sevenfold", "five finger death punch",
           "system of a down", "bring me the horizon", "three days grace",
           "breaking benjamin", "stone sour", "bad omens", "godsmack",
           "i prevail", "motionless in white", "architects",
           "foo fighters", "muse", "offspring", "smashing pumpkins",
           "ozzy", "black sabbath", "iron maiden", "judas priest",
           "motley crue", "guns n roses", "acdc", "ac/dc",
           "red hot chili", "nirvana", "pearl jam", "soundgarden",
           "alice in chains", "stone temple"]

print(f'Castle Rock entries: {len(feed.entries)}')
matches = 0
for entry in feed.entries:
    title = entry.get("title", "")
    raw_desc = entry.get("description", "") or ""
    desc = entry.get("summary", "") or raw_desc
    combined = (title + " " + desc).lower()
    matched = [a for a in artists if a in combined]
    if matched:
        matches += 1
        print(f'  MATCH [{", ".join(matched)}]: {title[:80]}')

print(f'\nTotal matches: {matches}/{len(feed.entries)}')
print(f'\nAll titles (first 15):')
for entry in feed.entries[:15]:
    print(f'  - {entry.get("title", "")[:80]}')
