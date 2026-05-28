import feedparser, ssl, sys

ssl._create_default_https_context = ssl._create_unverified_context

# Redirect stdout to handle emoji
sys.stdout.reconfigure(encoding='utf-8')

artists_lower = ["slipknot", "green day", "hollywood undead", "korn",
    "disturbed", "linkin park", "system of a down", "three days grace",
    "breaking benjamin", "shinedown", "papa roach", "evanescence",
    "bring me the horizon", "avenged sevenfold", "metallica",
    "rammstein", "limp bizkit", "mudvayne", "seether",
    "stone sour", "theory of a deadman", "godsmack",
    "five finger death punch", "i prevail", "bad omens",
    "motionless in white", "ice nine kills", "architects",
    "the amity affliction", "memphis may fire", "asking alexandria"]

feeds = [
    ("https://www.blabbermouth.net/feed/", "blabbermouth"),
    ("https://loudwire.com/feed/", "loudwire"),
    ("https://metalinjection.net/feed", "metalinjection"),
    ("https://rocknloadmag.com/feed/", "rocknload"),
]

for url, source in feeds:
    feed = feedparser.parse(url)
    print(f'\n=== {source} ({len(feed.entries)} entries) ===')
    for entry in feed.entries[:20]:
        title = entry.get("title", "")
        raw_desc = entry.get("description", "") or ""
        combined = (title + " " + raw_desc).lower()
        matched = [a for a in artists_lower if a in combined]
        if matched:
            print(f'  OK: [{", ".join(matched)}] {title[:80]}')
    # Show some un-matched titles to see content
    unmatched = [e.get("title","") for e in feed.entries[:15] if not any(a in (e.get("title","") + " " + (e.get("description","") or "")).lower() for a in artists_lower)]
    if unmatched:
        print(f'  (sample unmatched):')
        for t in unmatched[:5]:
            print(f'    - {t[:80]}')
