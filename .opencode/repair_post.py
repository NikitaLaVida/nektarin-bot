# -*- coding: utf-8 -*-
import sys, json, os, re, feedparser, requests, time, random
from html import unescape

BOT_TOKEN = "8879790921:AAE9hwgmrpSoa5wr7NCXA6H9CBDp6JgC3s0"
CHANNEL_ID = "@NektarinGaming"

# Load bot code for extract_game, find_image, make_caption, send_post
sys.argv = ['test']
exec(open(r'C:\Users\La Vida Loca\.opencode\gaming_news_bot.py', encoding='utf-8').read().split('if __name__')[0])

# Step 1: Delete old message 1587
base = f"https://api.telegram.org/bot{BOT_TOKEN}/"
print("Deleting msg#1587...")
r = requests.post(base + "deleteMessage", json={
    "chat_id": CHANNEL_ID,
    "message_id": 1587,
}, timeout=8)
if r.status_code == 200:
    print("  Deleted OK")
else:
    print(f"  Delete failed: {r.text[:200]}")

# Step 2: Scan RSS feeds for Elden Ring article
print("\nSearching RSS for Elden Ring castle article...")
found = None
for url, source, limit in RSS_FEEDS:
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:limit]:
            title = clean(entry.get("title", ""))
            desc = clean_desc(entry.get("description", "") or "")
            if "elden ring" in title.lower() or "elden ring" in desc.lower():
                if any(w in desc.lower() for w in ["скриншот", "замк", "касл", "castle", "screenshot"]):
                    found = {
                        "title": title,
                        "desc": desc,
                        "link": entry.get("link", ""),
                        "source": source,
                        "youtube_url": extract_youtube(entry.get("description", "") or ""),
                    }
                    print(f"  Found: {title[:60]}")
                    print(f"  Source: {source}, URL: {entry.get('link', '')[:80]}")
                    break
    except:
        pass
    if found:
        break

if not found:
    print("\nArticle not in RSS feeds.")
    print("Posts in state:", list(state.get("posted_msgs", {}).keys())[-5:])
    exit()

# Step 3: Re-post with image
print(f"\nReposting: {found['title'][:60]}")
img_url = find_image(found["title"], found["desc"], found["source"])
print(f"  Image: {img_url}")

caption = make_caption(found["title"], found["desc"], found.get("link", ""))
print(f"  Caption: {caption[:100]}...")

# Send
if img_url:
    img_data = requests.get(img_url, timeout=10)
    if img_data.status_code == 200:
        files = {"photo": ("image.jpg", img_data.content, "image/jpeg")}
        r = requests.post(base + "sendPhoto", data={
            "chat_id": CHANNEL_ID,
            "caption": caption,
            "parse_mode": "Markdown",
        }, files=files, timeout=20)
        if r.status_code == 200:
            msg_id = r.json()["result"]["message_id"]
            print(f"  Reposted with image! msg#{msg_id}")
        else:
            print(f"  sendPhoto failed: {r.text[:200]}")
    else:
        print(f"  Image download failed: {img_data.status_code}")
else:
    print("  No image found, sending as text")
    r = requests.post(base + "sendMessage", json={
        "chat_id": CHANNEL_ID,
        "text": caption,
        "parse_mode": "Markdown",
    }, timeout=10)
    if r.status_code == 200:
        print(f"  Sent text: msg#{r.json()['result']['message_id']}")
