import os
import re
import time
import random
import hashlib
import glob
import threading
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import feedparser
from datetime import datetime, timezone

from bot.config import (
    CHANNEL_ID, STATE_FILE, CHANNEL_SIGNATURE,
    ADMIN_CHAT_ID,
    ANIME_FEEDS, ROCK_FEEDS, ROCK_ARTISTS, ROCK_TRACKS,
    MAX_DESC_LEN, PRIORITY_KEYWORDS,
    MAX_CAPTION_LEN, MAX_IMAGE_SIZE, _SEP,
    RSS_FEEDS, get_global_state, _SCORING,
)
from bot.core import (
    tg, escape_html, clean, clean_desc,
    is_hot, is_trailer, translate_en_ru, shorten,
    extract_game, extract_numbers, extract_platforms,
    detect_genre, detect_theme, is_gaming_related,
    get_recent_game_names, send_error,
    extract_youtube, is_hd, pick, send_audio_file,
    COMMENTARIES, THEME_EMOJI, THEME_HASHTAGS,
    TEMPLATES,
)
from bot.security import safe_download_image, detect_image_type
from bot.images import find_image, rss_image, find_post_image

logger = logging.getLogger(__name__)


def _is_english(text):
    if not text:
        return False
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    cyrillic = sum(1 for c in letters if '\u0400' <= c <= '\u04FF')
    if cyrillic > 0:
        return False
    latin = sum(1 for c in letters if c.isascii() and c.isalpha())
    return latin / len(letters) > 0.5

def make_caption(title, desc, link, game=None):
    raw_title = title
    raw_desc = desc
    if not desc:
        desc = title
    if _is_english(raw_title):
        raw_title = translate_en_ru(raw_title)
    if _is_english(raw_desc):
        raw_desc = translate_en_ru(raw_desc)
    title = escape_html(raw_title)
    desc = escape_html(raw_desc)
    if not game:
        game = extract_game(raw_title)
    game = escape_html(game)
    numbers = extract_numbers(raw_desc)
    platforms = extract_platforms(raw_title + " " + raw_desc)
    genre = detect_genre(raw_desc)
    theme = detect_theme(raw_title, raw_desc)
    builder = TEMPLATES.get(theme, TEMPLATES["generic"])
    parts = builder(title, desc, game, numbers, platforms, genre, link)
    caption = "\n".join(parts)
    emoji = THEME_EMOJI.get(theme, "\U0001F4F0")
    caption = f"{emoji} {caption}"
    caption += CHANNEL_SIGNATURE
    hashtag = THEME_HASHTAGS.get(theme, "#игровыеновости")
    caption += f"\n{hashtag}"
    if genre:
        caption += f" #{genre}"
    if len(caption) > MAX_CAPTION_LEN:
        caption = caption[:MAX_CAPTION_LEN - 3] + "..."
    return caption


def send_post(title, desc, link, img_url, youtube_url=None, game=None, custom_caption=None):
    caption = custom_caption or make_caption(title, desc, link, game)
    caption_with_link = f"{caption}\n\n{youtube_url}" if youtube_url else caption
    if img_url:
        try:
            img_bytes = safe_download_image(img_url, timeout=15)
            if img_bytes and is_hd(img_bytes):
                img_ext, img_mime = detect_image_type(img_bytes)
                files = {"photo": (f"image.{img_ext}", img_bytes, img_mime)}
                payload = {
                    "chat_id": CHANNEL_ID, "caption": caption_with_link,
                    "parse_mode": "HTML",
                }
                r = tg("sendPhoto", data=payload, files=files, timeout=30)
                if r:
                    msg_id = r.json()["result"]["message_id"]
                    print(f"  Sent with image: {title[:60]} (msg#{msg_id})")
                    return msg_id
            print(f"  Image failed or too small, sending text")
        except Exception as e:
            print(f"  Image err: {e}")
    r = tg("sendMessage", json={
        "chat_id": CHANNEL_ID, "text": caption_with_link, "parse_mode": "HTML",
    }, timeout=15)
    if r:
        msg_id = r.json()["result"]["message_id"]
        print(f"  Sent: {title[:60]} (msg#{msg_id})")
        return msg_id
    print(f"  Send failed")
    return None


def score_news_item(item, ids, content_hashes, recent_games):
    if item["id"] in ids:
        return None
    if str(item.get("content_hash", "")) in content_hashes:
        return None
    score = 0
    desc_len = len(item.get("desc", ""))
    score += min(desc_len * _SCORING["desc_score_per_char"], _SCORING["desc_max_score"])
    if extract_numbers(item.get("desc", "")):
        score += _SCORING["numbers_boost"]
    if extract_platforms(item["title"] + " " + item.get("desc", "")):
        score += _SCORING["platforms_boost"]
    game = extract_game(item["title"])
    game_lower = game.lower()
    if not is_gaming_related(item["title"], item.get("desc", "")):
        score += _SCORING["non_gaming_penalty"]
    elif game and len(game_lower) > 3:
        score += _SCORING["game_found_boost"]
    if game_lower and len(game_lower) > 3 and game_lower in recent_games:
        hot = any(kw in (item["title"] + " " + item.get("desc", "")).lower() for kw in PRIORITY_KEYWORDS)
        score += _SCORING["repeat_hot_penalty"] if hot else _SCORING["repeat_penalty"]
    theme = detect_theme(item["title"], item.get("desc", ""))
    if is_hot(item):
        score += _SCORING["hot_boost"]
    if is_trailer(item["title"]):
        score += _SCORING["trailer_boost"]
    if item.get("youtube_url"):
        score += _SCORING["youtube_boost"]
    if theme == "rumor":
        score += _SCORING["rumor_penalty"]
    item["_score"] = score
    item["_game"] = game
    item["_theme"] = theme
    return item


# ---- Free Games ----

def fetch_epic_free_games():
    try:
        r = requests.get(
            "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions",
            params={"locale": "ru-RU", "country": "RU"}, timeout=12,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        games = []
        for el in data.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", []):
            if not el.get("promotions"):
                continue
            title = el.get("title", "")
            if not title or title.lower().startswith("mystery game"):
                continue
            promos = el["promotions"]
            offer = None
            source = None
            for offer_list, src in [
                (promos.get("promotionalOffers"), "current"),
                (promos.get("upcomingPromotionalOffers"), "upcoming"),
            ]:
                if not offer_list:
                    continue
                po = offer_list[0].get("promotionalOffers", [{}])[0]
                ds = po.get("discountSetting") or {}
                if ds.get("discountPercentage") == 0:
                    offer = po
                    source = src
                    break
            if not offer:
                continue
            slug = el.get("productSlug", "")
            if slug in (None, "", "[]"):
                slug = el.get("urlSlug", "") or ""
            if slug in (None, "", "[]"):
                slug = ""
            else:
                for attr in el.get("customAttributes") or []:
                    if attr.get("key") == "com.epicgames.app.productSlug" and attr.get("value") not in (None, "", "[]"):
                        slug = attr["value"]
                        break
            url = f"https://store.epicgames.com/ru/p/{slug}" if slug else ""
            desc = clean(el.get("description", "") or "")
            desc = re.sub(r"^Get ", "", desc, flags=re.I)
            key_images = el.get("keyImages", [])
            image = None
            for t in ("Thumbnail", "DieselGameBoxTall", "DieselGameBoxWide"):
                for img in key_images:
                    if img.get("type") == t:
                        image = img.get("url")
                        break
                if image:
                    break
            if not image and key_images:
                image = key_images[0].get("url")
            end_str = offer.get("endDate", "")
            end_readable = ""
            if end_str:
                try:
                    dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                    end_readable = dt.astimezone().strftime("%d.%m.%Y %H:%M МСК")
                except Exception as e:
                    print(f"  Epic date parse err: {e}")
                    end_readable = end_str[:10]
            games.append({
                "title": title, "desc": desc[:200], "image": image,
                "url": url, "end_date": end_readable, "source": source,
            })
        return games
    except Exception as e:
        print(f"  Epic free games error: {e}")
        return []


def fetch_gog_free_games():
    try:
        r = requests.get("https://www.gog.com/games/ajax/filtered",
            params={"mediaType": "game", "price": "free", "limit": 10}, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
        games = []
        for product in data.get("products", []):
            title = product.get("title", "")
            if not title:
                continue
            url = f"https://www.gog.com{product.get('url', '')}" if product.get("url") else ""
            image = product.get("image") or product.get("image_facebook") or ""
            games.append({"title": title, "url": url, "image": image})
        return games
    except Exception as e:
        print(f"  GOG free games error: {e}")
        return []


def send_deals_batch(steam_deals, epic_free, gog_free):
    lines = ["\U0001F4F0 <b>Акции и раздачи</b>", ""]
    count = 0
    if epic_free:
        lines.append("\U0001F381 <b>Epic Games</b>")
        for g in epic_free:
            if g.get("url"):
                lines.append(f'\U0001F539 <a href="{g["url"]}">{escape_html(g["title"])}</a>')
            else:
                lines.append(f"\U0001F539 {escape_html(g['title'])}")
            if g.get("end_date"):
                lines.append(f"   \U0001F512 до {g['end_date']}")
            count += 1
        lines.append("")
    if gog_free:
        lines.append("\U0001F4F0 <b>GOG</b>")
        for g in gog_free:
            if g.get("url"):
                lines.append(f'\U0001F539 <a href="{g["url"]}">{escape_html(g["title"])}</a>')
            else:
                lines.append(f"\U0001F539 {escape_html(g['title'])}")
            count += 1
        lines.append("")
    if steam_deals:
        lines.append("\U0001F3AE <b>Steam</b>")
        for d in sorted(steam_deals, key=lambda x: -x["discount"]):
            app_link = f'https://store.steampowered.com/app/{d["appid"]}/'
            emoji = "\U0001F525" if d["discount"] >= 90 else "\U0001F539"
            lines.append(f'{emoji} <a href="{app_link}">{escape_html(d["title"])} -{d["discount"]}%</a>')
            lines.append(f"   \u20BD {d['final_price']:.0f} вместо {d['original_price']:.0f}")
            if d.get("expires"):
                lines.append(f"   \U0001F512 до {d['expires']}")
            count += 1
        lines.append("")
    if count == 0:
        return None
    text = "\n".join(lines).strip()
    if len(text) > 4000:
        text = text[:3997] + "..."
    r = tg("sendMessage", json={
        "chat_id": CHANNEL_ID, "text": text,
        "parse_mode": "HTML", "disable_web_page_preview": False,
    }, timeout=12)
    if r:
        msg_id = r.json()["result"]["message_id"]
        print(f"  Deals batch sent ({count} items, msg#{msg_id})")
        return msg_id
    print(f"  Deals batch failed")
    send_error("Deals batch failed")
    return None


def fetch_steam_deals(min_discount=70):
    try:
        r = requests.get("https://store.steampowered.com/api/featuredcategories",
            params={"cc": "RU", "l": "russian"}, timeout=10)
        if r.status_code != 200:
            print(f"  Steam categories API: {r.status_code}")
            return []
        data = r.json()
        deals = []
        for item in data.get("specials", {}).get("items", []):
            dp = item.get("discount_percent", 0)
            if dp < min_discount:
                continue
            appid = item.get("id")
            name = item.get("name", "")
            if not appid or not name:
                continue
            orig = (item.get("original_price") or 0) / 100
            final = (item.get("final_price") or 0) / 100
            expires = item.get("discount_expiration")
            if expires:
                expires_dt = datetime.fromtimestamp(expires, tz=timezone.utc).astimezone()
                expires_str = expires_dt.strftime("%d.%m.%Y %H:%M МСК")
            else:
                expires_str = ""
            deals.append({
                "appid": appid, "title": name, "discount": dp,
                "original_price": orig, "final_price": final,
                "image": item.get("large_capsule_image") or item.get("small_capsule_image"),
                "expires": expires_str,
            })
        return deals
    except Exception as e:
        print(f"  Steam deals error: {e}")
        return []





def score_anime_entry(title, desc, interests):
    text = (title + " " + desc).lower()
    liked = interests.get("liked_titles", [])
    score = 0
    for kw in liked:
        if kw in text:
            score += 10
    return score


ANIME_EMOJI_MAP = {
    "sequel": "\U0001F3AC",
    "announce": "\U0001F389",
    "drama": "\U0001F4A2",
    "generic": "\U0001F48C",
}
ANIME_COMMENTARIES = [
    "Анимешники, внимание!", "Новость из мира аниме.",
    "Смотрим, не отрываясь.", "Для тех, кто любит субтитры.",
    "Отаку, ваш выход.", "На заметку аниме-фанату.",
    "Только для истинных ценителей.", "Аниме-индустрия не спит.",
    "Берём на карандаш.", "Ждём озвучку.",
]

def anime_caption(title, desc, link):
    theme = detect_theme(title, desc)
    emoji = ANIME_EMOJI_MAP.get(theme, "\U0001F48C")
    commentary = pick(ANIME_COMMENTARIES)
    ru_title = translate_en_ru(title)
    ru_desc = translate_en_ru(shorten(desc, 200))
    body = f"{ru_title}. {ru_desc}" if ru_desc else ru_title
    return f"{emoji} {commentary}\n{_SEP * 7}\n{body}\n\nПодробнее: {link}{CHANNEL_SIGNATURE}\n#аниме"


def post_anime_news(state):
    today = time.strftime("%Y-%m-%d")
    last = state.get("anime_posted", "")
    if last == today:
        return False
    anime_links = state.setdefault("posted_anime_links", [])
    interests = state.get("anime_interests", {})
    if not interests:
        interests = {"liked_titles": ["аниме", "аниме-сериал", "аниме фильм", "сезон", "манга"]}
        state["anime_interests"] = interests
    candidates = []
    for url, source, limit in ANIME_FEEDS:
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:limit + 10]:
                raw_title = entry.get("title", "")
                title = clean(raw_title)
                raw_desc = entry.get("description", "") or ""
                desc = clean_desc(raw_desc)
                if not title:
                    continue
                sc = score_anime_entry(title, desc, interests)
                link = entry.get("link", "")
                if link in anime_links:
                    continue
                candidates.append((sc, title, desc, raw_desc, link, rss_image(entry), source))
        except Exception as e:
            print(f"  Anime feed {source} err: {e}")
    if not candidates:
        return False
    candidates.sort(key=lambda x: -x[0])
    best = candidates[0]
    sc, title, desc, raw_desc, link, img, source = best
    print(f"  Anime best: {title[:50]} (score={sc})")
    caption = anime_caption(title, desc, link)
    preview = f"\U0001F514 <b>\u041F\u0440\u0435-\u043C\u043E\u0434\u0435\u0440\u0430\u0446\u0438\u044F (\u0430\u043D\u0438\u043C\u0435)</b>\n\n{caption}"
    mod_msg_id = None
    if img:
        try:
            img_bytes = safe_download_image(img, timeout=8)
            if img_bytes and is_hd(img_bytes):
                ext, mime = detect_image_type(img_bytes)
                r = tg("sendPhoto", data={
                    "chat_id": ADMIN_CHAT_ID, "caption": preview, "parse_mode": "HTML",
                }, files={"photo": (f"anime.{ext}", img_bytes, mime)}, timeout=15)
                if r:
                    mod_msg_id = r.json()["result"]["message_id"]
        except Exception as e:
            print(f"  Anime preview img err: {e}")
    if not mod_msg_id:
        r = tg("sendMessage", json={
            "chat_id": ADMIN_CHAT_ID, "text": preview, "parse_mode": "HTML",
        }, timeout=10)
        if r:
            mod_msg_id = r.json()["result"]["message_id"]
    if mod_msg_id:
        pending = state.setdefault("pending_moderation", [])
        pending.append({
            "title": title, "desc": desc, "link": link, "img_url": img,
            "game": "", "source": source, "content_hash": "",
            "msg_id": mod_msg_id, "time": time.time(),
            "id": f"anime_{int(time.time())}",
            "_type": "anime", "custom_caption": caption,
            "_link": link,
        })
        state["anime_posted"] = today
        print(f"  Anime sent to moderation: {title[:50]}")
        return True
    return False


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


def download_audio(query, output_dir, max_results=1):
    try:
        import yt_dlp
        opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(output_dir, "%(id)s.%(ext)s"),
            "quiet": True, "no_warnings": True,
            "default_search": "ytsearch",
            "max_filesize": 45000000,
        }
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
                if matches:
                    fn = matches[0]
                    results.append((fn, title))
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
    # Shuffle and try up to 4 tracks, pick first 2 that work
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


def _update_rock_state(state, msg_id, title, artist, link, source, today, rocks_links):
    state["rock_posted"] = today
    if link not in rocks_links:
        rocks_links.append(link)
    posted_msgs = state.setdefault("posted_msgs", {})
    posted_msgs[str(msg_id)] = {
        "title": title, "game": artist,
        "time": time.time(), "source": source,
    }


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
                preview = f"\U0001F514 <b>\u041F\u0440\u0435-\u043C\u043E\u0434\u0435\u0440\u0430\u0446\u0438\u044F (\u0440\u043E\u043A)</b>\n\n{caption}"
                mod_msg_id = None
                if photo_bytes:
                    ext, mime = detect_image_type(photo_bytes)
                    r = tg("sendPhoto", data={
                        "chat_id": ADMIN_CHAT_ID, "caption": preview, "parse_mode": "HTML",
                    }, files={"photo": (f"rock.{ext}", photo_bytes, mime)}, timeout=15)
                    if r:
                        mod_msg_id = r.json()["result"]["message_id"]
                if not mod_msg_id:
                    r = tg("sendMessage", json={
                        "chat_id": ADMIN_CHAT_ID, "text": preview, "parse_mode": "HTML",
                    }, timeout=10)
                    if r:
                        mod_msg_id = r.json()["result"]["message_id"]
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


def make_channel_stats(state):
    all_msgs = state.get("posted_msgs", {})
    now_t = time.time()
    week_ago = now_t - 604800
    recent = [(mid, data) for mid, data in all_msgs.items() if data.get("time", 0) >= week_ago]
    if len(recent) < 3:
        return None
    total_week = len(recent)
    game_counts = {}
    for mid, data in recent:
        game = data.get("game", "")
        if game:
            game_counts[game] = game_counts.get(game, 0) + 1
    top_games = sorted(game_counts.items(), key=lambda x: -x[1])[:5]
    source_counts = {}
    for mid, data in recent:
        src = data.get("source", "other")
        source_counts[src] = source_counts.get(src, 0) + 1
    top_sources = sorted(source_counts.items(), key=lambda x: -x[1])[:3]
    lines = ["\U0001F4CA <b>Статистика недели</b>", ""]
    lines.append(f"\U0001F4F0 Всего постов: <b>{total_week}</b>")
    if top_games:
        lines.append("")
        lines.append("\U0001F3AE <b>Топ игр:</b>")
        for g, c in top_games:
            lines.append(f"\U0001F539 {g} — {c}")
    if top_sources:
        lines.append("")
        lines.append("\U0001F4E1 <b>Источники:</b>")
        for s, c in top_sources:
            lines.append(f"\U0001F539 {s} — {c}")
    lines.append("")
    lines.append("<i>Спасибо, что читаете!</i>")
    return "\n".join(lines)





def send_daily_admin_stats(state):
    today = time.strftime("%Y-%m-%d")
    last = state.get("last_daily_admin_stats", "")
    if last == today:
        return False
    all_msgs = state.get("posted_msgs", {})
    now_t = time.time()
    day_ago = now_t - 86400
    recent = [(mid, data) for mid, data in all_msgs.items() if data.get("time", 0) >= day_ago]
    total_today = len(recent)
    source_counts = {}
    for mid, data in recent:
        src = data.get("source", "other")
        source_counts[src] = source_counts.get(src, 0) + 1
    pending = state.get("pending_moderation", [])
    lines = ["\U0001F4CB <b>Статистика дня</b>", ""]
    lines.append(f"\U0001F4F0 Постов сегодня: <b>{total_today}</b>")
    subs = 0
    try:
        r = tg("getChatMemberCount", json={"chat_id": CHANNEL_ID}, timeout=8)
        if r:
            subs = r.json().get("result", 0)
            lines.append(f"\U0001F465 Подписчиков: <b>{subs}</b>")
    except Exception as e:
        print(f"  getChatMemberCount err: {e}")
    if source_counts:
        lines.append("")
        lines.append("\U0001F4E1 <b>Источники:</b>")
        for s, c in sorted(source_counts.items(), key=lambda x: -x[1])[:5]:
            lines.append(f"\U0001F539 {s} — {c}")
    if pending:
        lines.append("")
        lines.append(f"\U0001F514 В модерации: <b>{len(pending)}</b>")
    lines.append("")
    lines.append(f"<i>Бот работает в штатном режиме</i>")
    text = "\n".join(lines)
    r = tg("sendMessage", json={
        "chat_id": ADMIN_CHAT_ID,
        "text": text, "parse_mode": "HTML",
    }, timeout=10)
    if r:
        state["last_daily_admin_stats"] = today
        print(f"  Daily admin stats sent ({total_today} posts, {subs} subs)")
        return True
    return False


def post_listener_chart(state):
    tracks = state.get("listener_tracks", [])
    current_week = time.strftime("%Y-W%V")
    week_tracks = [t for t in tracks if t.get("week") == current_week]
    if not week_tracks:
        return False
    lines = ["\U0001F3B5 <b>Листенер-чарт этой недели</b>", ""]
    for i, t in enumerate(week_tracks[:15], 1):
        from_name = t.get("from", "Подписчик")
        lines.append(f"{i}. {escape_html(t['text'][:80])} — <i>{escape_html(from_name)}</i>")
    if len(week_tracks) > 15:
        lines.append("")
        lines.append(f"И ещё {len(week_tracks) - 15} треков")
    text = "\n".join(lines)
    r = tg("sendMessage", json={
        "chat_id": CHANNEL_ID, "text": text,
        "parse_mode": "HTML",
    }, timeout=10)
    if r:
        state["listener_tracks"] = [t for t in tracks if t.get("week") != current_week]
        print(f"  Listener chart posted ({len(week_tracks)} tracks)")
        return True
    return False


def post_weekly_poll(state):
    last_poll = state.get("last_weekly_poll", "")
    today = time.strftime("%Y-%m-%d")
    # Only on Sunday
    if time.strftime("%w") != "0":
        return False
    if last_poll == today:
        return False
    polls = [
        {
            "question": "\U0001F3AE Какой трейлер ждёте больше всего?",
            "options": ["GTA VI", "The Witcher 4", "Metroid Prime 4", "Cтейлз у камня"],
        },
        {
            "question": "\U0001F4F0 Какая новость была самой интересной на неделе?",
            "options": ["Анонсы игр", "Скидки и раздачи", "Железо", "Слухи и инсайды"],
        },
        {
            "question": "\U0001F3B2 Во что играете сейчас?",
            "options": ["AAA-проект", "Инди", "Мультиплеер", "Прохожу старую классику"],
        },
    ]
    poll_chat_id = state.get("_linked_chat_id") or ADMIN_CHAT_ID
    poll_idx = state.setdefault("poll_index", 0) % len(polls)
    poll = polls[poll_idx]
    r = tg("sendPoll", json={
        "chat_id": poll_chat_id,
        "question": poll["question"],
        "options": poll["options"],
        "is_anonymous": False,
        "type": "regular",
    }, timeout=10)
    if r:
        state["poll_index"] = poll_idx + 1
        state["last_weekly_poll"] = today
        print(f"  Weekly poll sent: {poll['question'][:40]}")
        return True
    return False


def post_weekly_comments(state):
    last_comments_post = state.get("last_weekly_comments", "")
    today = time.strftime("%Y-%m-%d")
    if time.strftime("%w") != "0":
        return False
    if last_comments_post == today:
        return False
    comments = state.get("weekly_comments", [])
    week_ago = time.time() - 86400 * 7
    week_comments = [c for c in comments if c.get("time", 0) > week_ago]
    if len(week_comments) < 3:
        return False
    import heapq
    best = heapq.nlargest(3, week_comments, key=lambda x: len(x.get("text", "")))
    lines = ["\U0001F4AC <b>Комментарии недели</b>", ""]
    for i, c in enumerate(best, 1):
        from_name = escape_html(c.get("from", "Подписчик"))
        text = escape_html(c["text"][:200])
        lines.append(f"{i}. <i>{from_name}:</i>")
        lines.append(f"   {text}")
        lines.append("")
    text = "\n".join(lines).strip()
    if not text:
        return False
    r = tg("sendMessage", json={
        "chat_id": CHANNEL_ID, "text": text,
        "parse_mode": "HTML",
    }, timeout=10)
    if r:
        state["last_weekly_comments"] = today
        # Clear old comments
        state["weekly_comments"] = [c for c in comments if c.get("time", 0) <= week_ago]
        print(f"  Weekly comments posted ({len(week_comments)} collected, {len(best)} selected)")
        return True
    return False


def fetch_news():
    _state = get_global_state("state", {})
    _feed_errors = _state.get("feed_errors", {})
    _feed_lock = threading.Lock()

    def fetch_one(url, source, limit):
        with _feed_lock:
            src_err = _feed_errors.get(source, {})
        if src_err.get("count", 0) > 3 and time.time() - src_err.get("time", 0) < 3600:
            print(f"  {source}: skipped (circuit breaker, {src_err['count']} errors)")
            return []
        entries = []
        for attempt in range(2):
            try:
                resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
                feed = feedparser.parse(resp.content)
                seen = set()
                for entry in feed.entries[:limit]:
                    raw_desc = entry.get("description", "") or ""
                    title = clean(entry.get("title", ""))
                    desc = clean_desc(raw_desc)
                    link = entry.get("link", "")
                    norm = re.sub(r"[^a-zа-яё0-9]", "", (title + desc[:100]).lower())
                    h = hashlib.md5(norm.encode()).hexdigest()
                    if h in seen:
                        continue
                    seen.add(h)
                    entries.append({
                        "title": title, "desc": desc, "link": link,
                        "source": source, "youtube_url": extract_youtube(raw_desc),
                        "rss_img": rss_image(entry),
                        "id": "".join(c for c in link if c.isalnum()),
                        "content_hash": h,
                    })
                print(f"  {source}: {len(feed.entries)} items")
                with _feed_lock:
                    _feed_errors[source] = {"count": 0, "time": 0}
                    _state["feed_errors"] = _feed_errors
                return entries
            except Exception as e:
                if attempt == 0:
                    print(f"  {source} error: {e}, retrying...")
                    time.sleep(5)
                else:
                    print(f"  {source} retry failed: {e}")
                    with _feed_lock:
                        _feed_errors[source] = {"count": src_err.get("count", 0) + 1, "time": time.time()}
                        _state["feed_errors"] = _feed_errors
        return entries

    all_items = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(fetch_one, url, s, lim) for url, s, lim in RSS_FEEDS]
        for fut in as_completed(futures):
            all_items.extend(fut.result())

    # Log feed errors
    errs = [(s, e) for s, e in _feed_errors.items() if e.get("count", 0) > 0]
    if errs:
        for src, e in errs:
            print(f"  Feed [{src}]: {e.get('count', 0)} errors, last: {time.strftime('%H:%M', time.localtime(e.get('time', 0)))}")

    seen_hashes = set()
    items = []
    for entry in all_items:
        h = entry["content_hash"]
        if h in seen_hashes:
            continue
        seen_hashes.add(h)
        items.append(entry)
    return items



