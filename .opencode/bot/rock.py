import os
import re
import time
import random
import glob
import requests
import feedparser
from concurrent.futures import ThreadPoolExecutor, as_completed
from bot.config import (
    ADMIN_CHAT_ID, STATE_FILE, CHANNEL_SIGNATURE, ROCK_FEEDS, ROCK_ARTISTS,
    ROCK_TRACKS, MAX_DESC_LEN, COOKIES_FILE,
)
from bot.core import (
    tg, escape_html, clean, clean_desc, shorten,
    translate_en_ru, is_hd, send_audio_file, send_preview,
)
from bot.security import safe_download_image
from bot.images import rss_image


def extract_album_name(title, desc):
    text = title + " " + desc
    patterns = [
        r"album\s+(?:«|'|\")(.*?)(?:»|'|\")",
        r"(?:«|'|\")(.*?)(?:»|'|\")\s*(?:album|LP)",
        r"new\s+(?:album|LP|record|single)\s+(?:«|'|\")(.*?)(?:»|'|\")",
        r"(?:«|'|\")(.*?)(?:»|'|\")\s*(?:out|released|drops|arrives)",
        r"(?:album|LP)\s+(?:called|titled|named)\s+(?:«|'|\")(.*?)(?:»|'|\")",
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            return m.group(1).strip()
    return None


def album_cover_url(artist, album_name):
    try:
        q = requests.utils.quote(f"{artist} {album_name}")
        r = requests.get(f"https://itunes.apple.com/search?term={q}&entity=album&limit=3",
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        if r.status_code == 200:
            for result in r.json().get("results", []):
                art = result.get("artworkUrl100", "")
                if art:
                    return art.replace("100x100", "1200x1200").replace("100x100bb", "1200x1200bb")
    except Exception as e:
        print(f"  Album cover err: {e}")
    return None


SAFE_AUDIO_EXTS = {".m4a", ".mp3", ".webm", ".opus", ".ogg", ".wav", ".mp4", ".aac", ".flac"}


def _safe_audio_path(fn):
    try:
        real = os.path.realpath(fn)
        if not os.path.exists(real):
            print(f"  Audio file gone: {fn}")
            return None
        ext = os.path.splitext(real)[1].lower()
        if ext not in SAFE_AUDIO_EXTS:
            print(f"  Blocked unsafe extension ({ext}): {fn}")
            try:
                os.remove(real)
            except Exception:
                pass
            return None
    except Exception as e:
        print(f"  Path check err: {e}")
        return None
    return fn


def download_audio(query, output_dir, max_results=1):
    try:
        import yt_dlp
        opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(output_dir, "%(id)s.%(ext)s"),
            "quiet": True, "no_warnings": True,
            "default_search": "ytsearch",
            "max_filesize": 45000000,
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
        }
        if os.path.exists(COOKIES_FILE):
            opts["cookiefile"] = COOKIES_FILE
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=True)
            entries = info.get("entries", [info])
            results = []
            for entry in entries:
                video_id = entry.get("id", "")
                title = entry.get("title", query)
                if not video_id:
                    continue
                pattern = os.path.join(output_dir, f"{video_id}.*")
                matches = glob.glob(pattern)
                for fn in matches:
                    safe = _safe_audio_path(fn)
                    if safe:
                        results.append((safe, title))
                    break
            if results:
                return results
    except Exception as e:
        print(f"  Audio download err: {e}")
    return None


def game_ost_tracks(game_name, output_dir):
    clean_name = re.sub(r"[^a-zA-Z0-9 \-\']", "", game_name).strip()
    if not clean_name:
        return []
    query = f"{clean_name} OST"
    print(f"  Searching OST for: {query}")
    results = download_audio(query, output_dir, max_results=5)
    if not results or len(results) < 2:
        print(f"  Not enough OST results for {game_name}, trying broader...")
        results = download_audio(f"{clean_name} soundtrack", output_dir, max_results=5)
    if results and len(results) >= 2:
        picked = random.sample(results, 2) if len(results) > 2 else results
        print(f"  Got {len(results)} OST results for {game_name}, picked 2")
        return picked
    elif results:
        print(f"  Only 1 OST result for {game_name}")
        return results
    return []


def _build_rock_caption(title, desc, link, matched):
    ru_title = translate_en_ru(title)
    ru_desc = translate_en_ru(shorten(desc, MAX_DESC_LEN))
    safe_title = escape_html(ru_title)
    safe_desc = escape_html(ru_desc)
    tags = " #" + " #".join(a.replace(" ", "_") for a in matched[:3])
    artist = matched[0]
    album_name = extract_album_name(title, desc)
    album_line = ""
    if album_name:
        album_line = f" — новый альбом «{escape_html(album_name)}»"
        print(f"  Album detected: {album_name}")
    caption = f"\U0001F3B8 <b>{safe_title}</b>{album_line}\n\n{safe_desc}\n\n<a href=\"{link}\">\u041F\u043E\u0434\u0440\u043E\u0431\u043D\u0435\u0435</a>"
    caption += f"{CHANNEL_SIGNATURE}\n{tags}"
    return caption, artist, album_name


def _find_rock_photo(artist, album_name, img):
    if album_name:
        cover_url = album_cover_url(artist, album_name)
        if cover_url:
            try:
                cover_bytes = safe_download_image(cover_url, timeout=8)
                if cover_bytes and is_hd(cover_bytes):
                    return cover_bytes
            except Exception as e:
                print(f"  Rock cover download err: {e}")
    if img:
        try:
            img_bytes = safe_download_image(img, timeout=8)
            if img_bytes and is_hd(img_bytes):
                return img_bytes
        except Exception as e:
            print(f"  Rock img download err: {e}")
    return None


def _send_rock_audio(artist, tmpdir):
    tracks = ROCK_TRACKS.get(artist, [])
    if not tracks:
        print(f"  No ROCK_TRACKS for {artist}, trying fallback...")
        for key in ROCK_TRACKS:
            if artist in key or key in artist:
                tracks = ROCK_TRACKS[key]
                print(f"  Fallback matched '{key}' for '{artist}'")
                break
    if not tracks:
        print(f"  No tracks found for {artist}, skipping audio")
        return
    os.makedirs(tmpdir, exist_ok=True)
    pool = []
    for tname, tquery in random.sample(tracks, min(len(tracks), 4)):
        pool.append((tname, tquery))
    sent_count = 0
    max_send = min(2, len(tracks))
    with ThreadPoolExecutor(max_workers=3) as executor:
        fut_map = {}
        for tname, tquery in pool:
            fut = executor.submit(download_audio, tquery, tmpdir)
            fut_map[fut] = (tname, tquery)
        for fut in as_completed(fut_map, timeout=60):
            if sent_count >= max_send:
                break
            tname, tquery = fut_map[fut]
            try:
                results = fut.result(timeout=5)
                path = None
                if results:
                    path, _ = results[0]
                if path and os.path.exists(path):
                    r = send_audio_file(path, tname, performer=artist.title())
                    if r:
                        sent_count += 1
                        print(f"  Audio sent ({sent_count}/{max_send}): {tname}")
                    else:
                        print(f"  Audio send failed for {tname}")
                else:
                    print(f"  Audio download gave no file for {tname}")
            except Exception as e:
                print(f"  Audio error for {tname}: {e}")
    if sent_count == 0:
        print(f"  All audio downloads failed for {artist}")


def post_rock_news(state):
    today = time.strftime("%Y-%m-%d")
    last = state.get("rock_posted", "")
    if last == today:
        return False
    rocks_links = state.setdefault("posted_rock_links", [])
    artists_lower = [a.lower() for a in ROCK_ARTISTS]
    tmpdir = os.path.join(os.path.dirname(STATE_FILE), "audio_tmp")
    for url, source, limit in ROCK_FEEDS:
        try:
            resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:limit]:
                raw_title = entry.get("title", "")
                title = clean(raw_title)
                raw_desc = entry.get("description", "") or ""
                desc = clean_desc(raw_desc)
                combined = (title + " " + desc).lower()
                matched = [a for a in artists_lower if a in combined]
                if not matched:
                    continue
                link = entry.get("link", "")
                if link in rocks_links:
                    print(f"  Rock already posted: {title[:40]}")
                    continue
                img = rss_image(entry)
                artists_str = ", ".join(matched[:3])
                caption, artist, album_name = _build_rock_caption(title, desc, link, matched)
                photo_bytes = _find_rock_photo(artist, album_name, img)
                preview = f"\U0001F514 <b>Пре-модерация (рок)</b>\n\n{caption}"
                mod_msg_id = send_preview(ADMIN_CHAT_ID, preview, img_bytes=photo_bytes, timeout=15)
                if mod_msg_id:
                    pending = state.setdefault("pending_moderation", [])
                    pending.append({
                        "title": title, "desc": desc, "link": link, "img_url": img,
                        "game": artist, "source": source, "content_hash": "",
                        "msg_id": mod_msg_id, "time": time.time(),
                        "id": f"rock_{int(time.time())}",
                        "_type": "rock", "custom_caption": caption,
                        "_artist": artist, "_tmpdir": tmpdir, "_link": link,
                    })
                    state["rock_posted"] = today
                    print(f"  Rock sent to moderation: {title[:50]} [{artists_str}]")
                    return True
        except Exception as e:
            print(f"  Rock feed {source} err: {e}")
    return False
