import os
import re
import time
import random
import hashlib
import glob
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import feedparser
from datetime import datetime, timezone

from bot.config import (
    CHANNEL_ID, STATE_FILE, CHANNEL_SIGNATURE, ADMIN_CHAT,
    ADMIN_CHAT_ID,
    ANIME_FEEDS, ROCK_FEEDS, ROCK_ARTISTS, ROCK_TRACKS,
    MAX_DESC_LEN,
    WIKI_UA,
    MAX_CAPTION_LEN, MAX_IMAGE_SIZE, _SEP,
    RSS_FEEDS, get_global_state,
)
from bot.core import (
    tg, save_state, escape_html, clean, clean_desc,
    is_hot, is_trailer, translate_en_ru, shorten,
    extract_game, extract_numbers, extract_platforms,
    detect_genre, detect_theme, is_gaming_related,
    get_recent_game_names, send_error,
    extract_youtube, is_hd, pick, send_audio_file,
    COMMENTARIES, THEME_EMOJI, THEME_HASHTAGS,
    TEMPLATES,
)
from bot.security import safe_download_image, detect_image_type, is_safe_url
from bot.images import find_image, rss_image, find_post_image


def make_caption(title, desc, link, game=None):
    if not desc:
        desc = title
    title = escape_html(title)
    desc = escape_html(desc)
    if not game:
        game = extract_game(title)
    game = escape_html(game)
    numbers = extract_numbers(desc)
    platforms = extract_platforms(title + " " + desc)
    genre = detect_genre(desc)
    theme = detect_theme(title, desc)
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
    is_trailer_post = youtube_url and is_trailer(title)
    if is_trailer_post:
        try:
            text = f"{caption}\n\n{youtube_url}"
            r = tg("sendMessage", json={
                "chat_id": CHANNEL_ID, "text": text,
                "parse_mode": "HTML", "disable_web_page_preview": False,
            }, timeout=15)
            if r:
                msg_id = r.json()["result"]["message_id"]
                print(f"  Sent trailer: {title[:60]} (msg#{msg_id})")
                return msg_id
            print(f"  Trailer send failed ({r.status_code if r else 'no response'})")
        except Exception as e:
            print(f"  Trailer err: {e}")
    if img_url:
        try:
            img_bytes = safe_download_image(img_url, timeout=10)
            if img_bytes and is_hd(img_bytes):
                img_ext, img_mime = detect_image_type(img_bytes)
                files = {"photo": (f"image.{img_ext}", img_bytes, img_mime)}
                payload = {
                    "chat_id": CHANNEL_ID, "caption": caption,
                    "parse_mode": "HTML",
                }
                r = tg("sendPhoto", data=payload, files=files, timeout=20)
                if r:
                    msg_id = r.json()["result"]["message_id"]
                    print(f"  Sent with image: {title[:60]} (msg#{msg_id})")
                    return msg_id
            print(f"  Image failed or too small, sending text")
        except Exception as e:
            print(f"  Image err: {e}")
    r = tg("sendMessage", json={
        "chat_id": CHANNEL_ID, "text": caption, "parse_mode": "HTML",
    }, timeout=10)
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
    score += min(desc_len / 5, 20)
    if extract_numbers(item.get("desc", "")):
        score += 5
    if extract_platforms(item["title"] + " " + item.get("desc", "")):
        score += 3
    game = extract_game(item["title"])
    game_lower = game.lower()
    if not is_gaming_related(item["title"], item.get("desc", "")):
        score -= 50
    elif game and len(game_lower) > 3:
        score += 10
    if game_lower and len(game_lower) > 3 and game_lower in recent_games:
        score -= 500
    theme = detect_theme(item["title"], item.get("desc", ""))
    if is_hot(item):
        score += 50
    if is_trailer(item["title"]):
        score += 10
    if item.get("youtube_url"):
        score += 5
    if theme == "rumor":
        score -= 15
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
                except Exception:
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
        for d in steam_deals:
            app_link = f'https://store.steampowered.com/app/{d["appid"]}/'
            lines.append(f'\U0001F539 <a href="{app_link}">{escape_html(d["title"])} -{d["discount"]}%</a>')
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


def anime_caption(title, desc, link):
    theme = detect_theme(title, desc)
    emoji = THEME_EMOJI.get(theme, "\U0001F48C")
    commentary = pick(COMMENTARIES.get(theme, COMMENTARIES["generic"]))
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
    msg_id = None
    if img:
        try:
            img_bytes = safe_download_image(img, timeout=8)
            if img_bytes and is_hd(img_bytes):
                ext, mime = detect_image_type(img_bytes)
                r = tg("sendPhoto", data={
                    "chat_id": CHANNEL_ID, "caption": caption, "parse_mode": "HTML",
                }, files={"photo": (f"anime.{ext}", img_bytes, mime)}, timeout=15)
                if r:
                    msg_id = r.json()["result"]["message_id"]
        except Exception:
            pass
    if not msg_id:
        r = tg("sendMessage", json={
            "chat_id": CHANNEL_ID, "text": caption, "parse_mode": "HTML",
        }, timeout=10)
        if r:
            msg_id = r.json()["result"]["message_id"]
    if msg_id:
        state["anime_posted"] = today
        if link not in anime_links:
            anime_links.append(link)
        posted_msgs = state.setdefault("posted_msgs", {})
        posted_msgs[str(msg_id)] = {
            "title": title, "game": "",
            "time": time.time(), "source": source,
        }
        print(f"  Anime news posted: {title[:50]}")
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


def post_rock_news(state):
    today = time.strftime("%Y-%m-%d")
    last = state.get("rock_posted", "")
    if last == today:
        return False
    rocks_links = state.setdefault("posted_rock_links", [])
    artists_lower = [a.lower() for a in ROCK_ARTISTS]
    for url, source, limit in ROCK_FEEDS:
        try:
            feed = feedparser.parse(url)
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
                caption_photo = None
                if album_name:
                    cover_url = album_cover_url(artist, album_name)
                    if cover_url:
                        try:
                            cover_bytes = safe_download_image(cover_url, timeout=8)
                            if cover_bytes and is_hd(cover_bytes):
                                caption_photo = cover_bytes
                        except Exception:
                            pass
                if not caption_photo and img:
                    try:
                        img_bytes = safe_download_image(img, timeout=8)
                        if img_bytes and is_hd(img_bytes):
                            caption_photo = img_bytes
                    except Exception:
                        pass
                msg_id = None
                if caption_photo:
                    ext, mime = detect_image_type(caption_photo)
                    r = tg("sendPhoto", data={
                        "chat_id": CHANNEL_ID, "caption": caption, "parse_mode": "HTML",
                    }, files={"photo": (f"rock.{ext}", caption_photo, mime)}, timeout=15)
                    if r:
                        msg_id = r.json()["result"]["message_id"]
                if not msg_id:
                    r = tg("sendMessage", json={
                        "chat_id": CHANNEL_ID, "text": caption, "parse_mode": "HTML",
                    }, timeout=10)
                    if r:
                        msg_id = r.json()["result"]["message_id"]
                if msg_id:
                    tracks = ROCK_TRACKS.get(artist, [])
                    if len(tracks) >= 2:
                        picked = random.sample(tracks, 2)
                        tmpdir = os.path.join(os.path.dirname(STATE_FILE), "audio_tmp")
                        os.makedirs(tmpdir, exist_ok=True)
                        for tname, tquery in picked:
                            results = download_audio(tquery, tmpdir)
                            path = None
                            if results:
                                path, _ = results[0]
                            if path and os.path.exists(path):
                                r = send_audio_file(path, tname, performer=artist.title())
                                if r:
                                    print(f"  Audio sent: {tname} (msg#{r.json()['result']['message_id']})")
                                else:
                                    print(f"  Audio send failed for {tname}")
                            else:
                                print(f"  Audio download failed for {tname}")
                if msg_id:
                    state["rock_posted"] = today
                    if link not in rocks_links:
                        rocks_links.append(link)
                    posted_msgs = state.setdefault("posted_msgs", {})
                    posted_msgs[str(msg_id)] = {
                        "title": title, "game": artist,
                        "time": time.time(), "source": source,
                    }
                    print(f"  Rock news posted: {title[:50]} [{artists_str}]")
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
    if source_counts:
        lines.append("")
        lines.append("\U0001F4E1 <b>Источники:</b>")
        for s, c in sorted(source_counts.items(), key=lambda x: -x[1])[:5]:
            lines.append(f"\U0001F539 {s} — {c}")
    if pending:
        lines.append("")
        lines.append(f"\U0001F514 В модерации: <b>{len(pending)}</b>")
    lines.append("")
    lines.append("<i>Бот работает в штатном режиме</i>")
    text = "\n".join(lines)
    r = tg("sendMessage", json={
        "chat_id": ADMIN_CHAT_ID,
        "text": text, "parse_mode": "HTML",
    }, timeout=10)
    if r:
        state["last_daily_admin_stats"] = today
        print(f"  Daily admin stats sent ({total_today} posts)")
        return True
    return False


def post_listener_track(state):
    track = state.get("listener_track")
    if not track:
        return False
    current_week = time.strftime("%Y-W%V")
    if track.get("week") != current_week:
        del state["listener_track"]
        return False
    text = track["text"]
    from_name = track.get("from", "Подписчик")
    tmpdir = os.path.join(os.path.dirname(STATE_FILE), "audio_tmp")
    os.makedirs(tmpdir, exist_ok=True)
    safe_query = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ\s\-—–\'\"@]", "", text)[:100]
    if not safe_query.strip():
        print(f"  Listener track sanitized to empty, skipping")
        return False
    results = download_audio(safe_query, tmpdir)
    path = None
    real_title = text
    if results:
        path, real_title = results[0]
    if path and os.path.exists(path):
        r = send_audio_file(path, text[:60], performer=from_name)
        if not r:
            return False
        del state["listener_track"]
        print(f"  Listener track posted: {text[:50]}")
        return True
    else:
        print(f"  Could not download listener track: {text[:60]}")
        return False


def fetch_news():
    _state = get_global_state("state", {})
    _feed_errors = _state.get("feed_errors", {})

    def fetch_one(url, source, limit):
        src_err = _feed_errors.get(source, {})
        if src_err.get("count", 0) > 3 and time.time() - src_err.get("time", 0) < 3600:
            print(f"  {source}: skipped (circuit breaker, {src_err['count']} errors)")
            return []
        entries = []
        for attempt in range(2):
            try:
                resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
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
                _feed_errors[source] = {"count": 0, "time": 0}
                _state["feed_errors"] = _feed_errors
                return entries
            except Exception as e:
                if attempt == 0:
                    print(f"  {source} error: {e}, retrying...")
                    time.sleep(5)
                else:
                    print(f"  {source} retry failed: {e}")
                    _feed_errors[source] = {"count": src_err.get("count", 0) + 1, "time": time.time()}
                    _state["feed_errors"] = _feed_errors
        return entries

    all_items = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(fetch_one, url, s, lim) for url, s, lim in RSS_FEEDS]
        for fut in as_completed(futures):
            all_items.extend(fut.result())

    seen_hashes = set()
    items = []
    for entry in all_items:
        h = entry["content_hash"]
        if h in seen_hashes:
            continue
        seen_hashes.add(h)
        items.append(entry)
    return items



