import os, sys, re, json, requests, random, time
from html import unescape

BOT_TOKEN = "8879790921:AAE9hwgmrpSoa5wr7NCXA6H9CBDp6JgC3s0"
ADMIN_CHAT = 710307297
TG_API = "https://api.telegram.org/bot"

def tg(method, **kwargs):
    try:
        timeout = kwargs.pop("timeout", 10)
        r = requests.post(f"{TG_API}{BOT_TOKEN}/{method}", timeout=timeout, **kwargs)
        if r.status_code == 200:
            return r
        print(f"TG {method} failed: {r.text[:80]}")
    except Exception as e:
        print(f"TG {method} err: {e}")
    return None

# Test 1: Album cover via iTunes
print("--- Test 1: iTunes album cover ---")
q = requests.utils.quote("slipknot the end so far")
r = requests.get(f"https://itunes.apple.com/search?term={q}&entity=album&limit=3",
                 headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
if r.status_code == 200:
    data = r.json()
    for result in data.get("results", []):
        art = result.get("artworkUrl100", "")
        if art:
            cover = art.replace("100x100", "600x600")
            print(f"Cover URL: {cover}")
            # Download and send
            resp = requests.get(cover, timeout=8)
            if resp.status_code == 200:
                r2 = tg("sendPhoto", data={
                    "chat_id": ADMIN_CHAT,
                    "caption": "🎸 **Slipknot** — новый альбом «The End, So Far»\n\nТест обложки\n\n— @NektarinGaming\n#slipknot",
                    "parse_mode": "Markdown",
                }, files={"photo": ("cover.jpg", resp.content, "image/jpeg")}, timeout=15)
                if r2:
                    print(f"Cover sent: msg#{r2.json()['result']['message_id']}")
                else:
                    print("Cover send failed")
            break
else:
    print("iTunes API failed")

# Test 2: yt-dlp audio download
print("\n--- Test 2: Audio download ---")
import yt_dlp
opts = {
    "format": "bestaudio/best",
    "outtmpl": os.path.join(os.environ.get("TEMP", "."), "%(id)s.%(ext)s"),
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "max_filesize": 10000000,
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "128",
    }],
}
query = "Slipknot Duality"
with yt_dlp.YoutubeDL(opts) as ydl:
    info = ydl.extract_info(f"ytsearch:{query}", download=True)
    entries = info.get("entries", [info])
    if entries:
        fn = ydl.prepare_filename(entries[0])
        fn = fn.rsplit(".", 1)[0] + ".mp3"
        title = entries[0].get("title", query)
        if os.path.exists(fn):
            print(f"Downloaded: {fn} ({os.path.getsize(fn)} bytes)")
            # Send as audio
            with open(fn, "rb") as f:
                r3 = tg("sendAudio", data={
                    "chat_id": ADMIN_CHAT,
                    "title": "Duality",
                    "performer": "Slipknot",
                    "caption": "🎵 *Duality*",
                    "parse_mode": "Markdown",
                }, files={"audio": ("Duality.mp3", f, "audio/mpeg")}, timeout=30)
                if r3:
                    print(f"Audio sent: msg#{r3.json()['result']['message_id']}")
            os.remove(fn)
            print("Cleaned up")
        else:
            print(f"File not found: {fn}")
    else:
        print("No results")

print("\nDone!")
