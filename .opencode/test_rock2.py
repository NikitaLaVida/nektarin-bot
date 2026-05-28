import sys, os, json, feedparser, requests, hashlib, re, io, time, random, ssl
from html import unescape
from datetime import datetime, timezone
from PIL import Image

ssl._create_default_https_context = ssl._create_unverified_context

# Import needed functions from the bot
BOT_TOKEN = "8879790921:AAE9hwgmrpSoa5wr7NCXA6H9CBDp6JgC3s0"
CHANNEL_ID = "@NektarinGaming"
CHANNEL_SIGNATURE = "\n— @NektarinGaming"
MAX_DESC_LEN = 250

ROCK_FEEDS = [
    ("https://www.blabbermouth.net/feed/", "blabbermouth", 15),
    ("https://loudwire.com/feed/", "loudwire", 15),
    ("https://metalinjection.net/feed", "metalinjection", 15),
    ("https://rocknloadmag.com/feed/", "rocknload", 10),
]

ROCK_ARTISTS = [
    "slipknot", "green day", "hollywood undead", "korn",
    "disturbed", "linkin park", "system of a down", "three days grace",
    "breaking benjamin", "shinedown", "papa roach", "evanescence",
    "bring me the horizon", "avenged sevenfold", "metallica",
    "rammstein", "limp bizkit", "mudvayne", "seether",
    "stone sour", "theory of a deadman", "godsmack",
    "five finger death punch", "i prevail", "bad omens",
    "motionless in white", "ice nine kills", "architects",
    "the amity affliction", "memphis may fire", "asking alexandria",
]

def escape_md(text):
    for ch in r"\`*_{}[]()#+-.!|":
        text = text.replace(ch, "\\" + ch)
    return text

def clean(text):
    return unescape(text.strip())

def clean_desc(text):
    text = re.sub(r"<[^>]+>", "", text)
    return unescape(text.strip())

def shorten(s, max_len=200):
    s = s.strip()
    if len(s) <= max_len:
        return s
    return s[:max_len].rsplit(" ", 1)[0] + "..."

def rss_image(entry):
    media = entry.get("media_content") or entry.get("media_thumbnail") or []
    if media:
        return media[0].get("url", "")
    links = entry.get("links", [])
    for ln in links:
        if ln.get("type", "").startswith("image"):
            return ln.get("href", "")
    content = entry.get("content", [])
    if content and isinstance(content[0], dict):
        val = content[0].get("value", "")
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', val)
        if m:
            return m.group(1)
    summary = entry.get("summary", "")
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary)
    if m:
        return m.group(1)
    desc = entry.get("description", "")
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc)
    if m:
        return m.group(1)
    return ""

artists_lower = [a.lower() for a in ROCK_ARTISTS]
total_matches = 0

print("=== Rock News Test ===\n")

for url, source, limit in ROCK_FEEDS:
    try:
        feed = feedparser.parse(url)
        print(f'{source}: {len(feed.entries)} entries')
        for entry in feed.entries[:limit]:
            raw_title = entry.get("title", "")
            title = clean(raw_title)
            raw_desc = entry.get("description", "") or ""
            desc = clean_desc(raw_desc)
            combined = (title + " " + desc).lower()
            matched = [a for a in artists_lower if a in combined]
            if matched:
                total_matches += 1
                artists_str = ", ".join(matched[:3])
                safe_title = escape_md(title)
                safe_desc = escape_md(shorten(desc, MAX_DESC_LEN))
                tags = " #" + " #".join(a.replace(" ", "_") for a in matched[:3])
                link = entry.get("link", "")
                img = rss_image(entry)
                caption = f"🎸 **{safe_title}**\n\n{safe_desc}\n\n[Подробнее]({link}){CHANNEL_SIGNATURE}\n{tags}"
                print(f'\n  MATCH [{artists_str}]:')
                print(f'  Title: {title[:80]}')
                print(f'  Image: {img[:80] if img else "none"}')
                print(f'  Caption [{len(caption)} chars]: {caption[:120]}...')
        print()
    except Exception as e:
        print(f'{source}: {type(e).__name__}: {e}')
        print()

print(f'\nTotal matches: {total_matches}')
