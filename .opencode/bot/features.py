import os
import re
import time
import random
import hashlib
import requests
import feedparser
from datetime import datetime, timezone

from bot.config import (
    CHANNEL_ID, STATE_FILE, CHANNEL_SIGNATURE, ADMIN_CHAT,
    ANIME_FEEDS, ROCK_FEEDS, ROCK_ARTISTS, ROCK_TRACKS,
    MAX_DESC_LEN, MODERATION_TTL, MODERATION_INTERVAL,
    WIKI_UA, GAME_DEDUP_HOURS,
    TITLE_DEDUP_HOURS, TITLE_DEDUP_MIN_WORDS, TITLE_SIMILARITY_THRESHOLD,
    MAX_CAPTION_LEN, MAX_IMAGE_SIZE, TWITCH_CLIENT_ID, _SEP,
    RSS_FEEDS,
)
from bot.core import (
    tg, tg_get, save_state, escape_md, clean, clean_desc,
    is_hot, is_trailer, translate_en_ru, shorten,
    extract_game, extract_numbers, extract_platforms,
    detect_genre, detect_theme, is_gaming_related,
    get_recent_game_names, get_recent_titles, title_similarity,
    has_gaming_context, send_error, load_state, log,
    extract_youtube, is_hd, pick, smart_comment, send_audio_file,
    COMMENTARIES, THEME_EMOJI, THEME_HASHTAGS,
    embed_link, TEMPLATES,
)
from bot.security import safe_download_image, detect_image_type, is_safe_url
from bot.images import find_image, rss_image, find_post_image


def make_caption(title, desc, link, game=None):
    if not desc:
        desc = title
    title = escape_md(title)
    desc = escape_md(desc)
    if not game:
        game = extract_game(title)
    game = escape_md(game)
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
    if len(caption) > MAX_CAPTION_LEN:
        caption = caption[:MAX_CAPTION_LEN - 3] + "..."
        caption = re.sub(r'(\*{1,2}|_{1,2}|`+)\s*$', '', caption)
    return caption


def send_post(title, desc, link, img_url, youtube_url=None, game=None, custom_caption=None):
    caption = custom_caption or make_caption(title, desc, link, game)
    is_trailer_post = youtube_url and is_trailer(title)
    if is_trailer_post:
        try:
            text = f"{caption}\n\n{youtube_url}"
            r = tg("sendMessage", json={
                "chat_id": CHANNEL_ID, "text": text,
                "parse_mode": "Markdown", "disable_web_page_preview": False,
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
                    "parse_mode": "Markdown",
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
        "chat_id": CHANNEL_ID, "text": caption, "parse_mode": "Markdown",
    }, timeout=10)
    if r:
        msg_id = r.json()["result"]["message_id"]
        print(f"  Sent: {title[:60]} (msg#{msg_id})")
        return msg_id
    print(f"  Send failed")
    return None


def send_live_notification(title, game):
    text = (
        f"\U0001F534 **Я В ЭФИРЕ!**\n\n"
        f"**{escape_md(title)}**\n"
        f"\u2500" * 20 + "\n"
        f"Игра: **{escape_md(game)}**\n\n"
        f"Смотреть: https://twitch.tv/NektarinGaming"
    )
    try:
        r = tg("sendMessage", json={
            "chat_id": CHANNEL_ID, "text": text,
            "parse_mode": "Markdown", "disable_web_page_preview": False,
        }, timeout=10)
        if r:
            print(f"  Live notification sent: {title[:50]}")
            return True
        print(f"  Live notification failed: {r.text[:100]}")
    except Exception as e:
        print(f"  Live notification err: {e}")
    return False


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
    lines = ["\U0001F4F0 **Акции и раздачи**", ""]
    count = 0
    if epic_free:
        lines.append("\U0001F381 **Epic Games**")
        for g in epic_free:
            if g.get("url"):
                lines.append(f"\U0001F539 [{escape_md(g['title'])}]({g['url']})")
            else:
                lines.append(f"\U0001F539 {escape_md(g['title'])}")
            if g.get("end_date"):
                lines.append(f"   \U0001F512 до {g['end_date']}")
            count += 1
        lines.append("")
    if gog_free:
        lines.append("\U0001F4F0 **GOG**")
        for g in gog_free:
            if g.get("url"):
                lines.append(f"\U0001F539 [{escape_md(g['title'])}]({g['url']})")
            else:
                lines.append(f"\U0001F539 {escape_md(g['title'])}")
            count += 1
        lines.append("")
    if steam_deals:
        lines.append("\U0001F3AE **Steam**")
        for d in steam_deals:
            lines.append(f"\U0001F539 [{escape_md(d['title'])} -{d['discount']}%](https://store.steampowered.com/app/{d['appid']}/)")
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
        "parse_mode": "Markdown", "disable_web_page_preview": False,
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
                    "chat_id": CHANNEL_ID, "caption": caption, "parse_mode": "Markdown",
                }, files={"photo": (f"anime.{ext}", img_bytes, mime)}, timeout=15)
                if r:
                    msg_id = r.json()["result"]["message_id"]
        except Exception:
            pass
    if not msg_id:
        r = tg("sendMessage", json={
            "chat_id": CHANNEL_ID, "text": caption, "parse_mode": "Markdown",
        }, timeout=10)
        if r:
            msg_id = r.json()["result"]["message_id"]
    if msg_id:
        state["anime_posted"] = today
        if link not in anime_links:
            anime_links.append(link)
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
            "max_filesize": 15000000,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=True)
            entries = info.get("entries", [info])
            results = []
            for entry in entries:
                fn = ydl.prepare_filename(entry)
                title = entry.get("title", query)
                if os.path.exists(fn):
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
                safe_title = escape_md(ru_title)
                safe_desc = escape_md(ru_desc)
                tags = " #" + " #".join(a.replace(" ", "_") for a in matched[:3])
                artist = matched[0]
                album_name = extract_album_name(title, desc)
                album_line = ""
                if album_name:
                    album_line = f" — новый альбом «{escape_md(album_name)}»"
                    print(f"  Album detected: {album_name}")
                caption = f"\U0001F3B8 **{safe_title}**{album_line}\n\n{safe_desc}\n\n[\u041F\u043E\u0434\u0440\u043E\u0431\u043D\u0435\u0435]({link})"
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
                        "chat_id": CHANNEL_ID, "caption": caption, "parse_mode": "Markdown",
                    }, files={"photo": (f"rock.{ext}", caption_photo, mime)}, timeout=15)
                    if r:
                        msg_id = r.json()["result"]["message_id"]
                if not msg_id:
                    r = tg("sendMessage", json={
                        "chat_id": CHANNEL_ID, "text": caption, "parse_mode": "Markdown",
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
                                path, real_title = results[0]
                            if path and os.path.exists(path):
                                r = send_audio_file(path, tname, performer=artist.title())
                                if r:
                                    print(f"  Audio sent: {tname} (msg#{r.json()['result']['message_id']})")
                if msg_id:
                    state["rock_posted"] = today
                    if link not in rocks_links:
                        rocks_links.append(link)
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
    lines = ["\U0001F4CA **Статистика недели**", ""]
    lines.append(f"\U0001F4F0 Всего постов: **{total_week}**")
    if top_games:
        lines.append("")
        lines.append("\U0001F3AE **Топ игр:**")
        for g, c in top_games:
            lines.append(f"\U0001F539 {g} — {c}")
    if top_sources:
        lines.append("")
        lines.append("\U0001F4E1 **Источники:**")
        for s, c in top_sources:
            lines.append(f"\U0001F539 {s} — {c}")
    lines.append("")
    lines.append("_Спасибо, что читаете!_")
    return "\n".join(lines)





REPLY_TEMPLATES = [
    "В точку! \U0001F44D", "Согласен на все 100%",
    "Мнение засчитано \U0001F91D", "Спорно, но достойно уважения",
    "Инсайдерская информация подтверждает", "Добавлю себе в цитатник",
    "Ты читаешь мои мысли", "Лучший комментарий недели",
    "Проверял — так и есть", "Ты слишком далеко зашёл \U0001F480",
    "Бот молчит — значит одобряет \u2705", "Задокументировано в архивах канала",
]


def reply_to_comments(state):
    bot_id = state.get("_bot_id", 0)
    if not bot_id:
        try:
            me = tg("getMe", json={})
            if me:
                bot_id = me.json()["result"]["id"]
                state["_bot_id"] = bot_id
        except Exception:
            pass
    try:
        chat_info = tg("getChat", json={"chat_id": CHANNEL_ID})
        if not chat_info:
            return 0
        data = chat_info.json()
        linked_group = data.get("result", {}).get("linked_chat_id")
        if not linked_group:
            return 0
    except Exception:
        return 0
    offset_key = "comment_offset"
    offset = state.get(offset_key, 0)
    replied = 0
    try:
        updates = tg("getUpdates", json={
            "offset": offset, "timeout": 0, "allowed_updates": ["message"],
        })
        if updates:
            results = updates.json().get("result", [])
            for upd in results:
                msg = upd.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                if chat_id != linked_group:
                    offset = upd["update_id"] + 1
                    continue
                text = msg.get("text", "").strip()
                from_id = msg.get("from", {}).get("id", 0)
                if not text or from_id == bot_id:
                    offset = upd["update_id"] + 1
                    continue
                text_lower = text.lower()
                track_patterns = [
                    r" — ", r" – ", r" - ", r"–", r"—",
                    r"youtube\.com", r"youtu\.be",
                ]
                is_track_suggestion = any(re.search(p, text) for p in track_patterns) or \
                    text_lower.startswith("трек ") or \
                    text_lower.startswith("песня ") or \
                    text_lower.startswith("музыка ")
                if is_track_suggestion:
                    state["listener_track"] = {
                        "text": text,
                        "from": msg.get("from", {}).get("first_name", "Подписчик"),
                        "time": time.time(),
                        "week": time.strftime("%Y-W%V"),
                    }
                    print(f"  Listener track saved: {text[:60]}")
                reply = random.choice(REPLY_TEMPLATES)
                tg("sendMessage", json={
                    "chat_id": linked_group,
                    "text": reply,
                    "reply_to_message_id": msg.get("message_id"),
                }, timeout=10)
                replied += 1
                offset = upd["update_id"] + 1
    except Exception as e:
        print(f"  Comment reply err: {e}")
        return replied
    state[offset_key] = offset
    if replied:
        print(f"  Replied to {replied} comments")
    return replied


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
    items = []
    seen_hashes = set()
    for url, source, limit in RSS_FEEDS:
        print(f"Loading: {url}")
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:limit]:
                raw_desc = entry.get("description", "") or ""
                title = clean(entry.get("title", ""))
                youtube_url = extract_youtube(raw_desc)
                desc = clean_desc(raw_desc)
                link = entry.get("link", "")
                norm = re.sub(r"[^a-zа-яё0-9]", "", (title + desc[:100]).lower())
                h = hashlib.md5(norm.encode()).hexdigest()
                if h in seen_hashes:
                    continue
                seen_hashes.add(h)
                items.append({
                    "title": title, "desc": desc, "link": link,
                    "source": source, "youtube_url": youtube_url,
                    "rss_img": rss_image(entry),
                    "id": "".join(c for c in link if c.isalnum()),
                    "content_hash": h,
                })
            print(f"  OK: {len(feed.entries)} items")
        except Exception as e:
            print(f"  Error loading {url}: {e}")
    return items


def check_is_live():
    try:
        r = requests.post("https://gql.twitch.tv/gql",
            json={
                "query": "query($login: String, timeout=6) {user(login: $login) {stream {title type viewersCount game {name}}}}",
                "variables": {"login": "NektarinGaming"}
            },
            headers={"Client-ID": TWITCH_CLIENT_ID, "User-Agent": "Mozilla/5.0"},
            timeout=8)
        if r.status_code == 200:
            data = r.json()
            s = data.get("data", {}).get("user", {}).get("stream")
            if s:
                return s.get("title", ""), s.get("game", {}).get("name", "unknown")
        return None
    except Exception as e:
        print(f"  Twitch check error: {e}")
    return None
