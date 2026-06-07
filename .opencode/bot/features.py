import os
import re
import time
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import feedparser

from bot.config import (
    CHANNEL_ID, STATE_FILE, CHANNEL_SIGNATURE,
    PRIORITY_KEYWORDS,
    MAX_CAPTION_LEN, MAX_IMAGE_SIZE, _SEP,
    RSS_FEEDS, get_global_state, _SCORING,
    POST_LOG_FILE,
)
from bot.core import (
    tg, escape_html, clean, clean_desc,
    is_hot, is_trailer, translate_en_ru, shorten,
    extract_game, extract_numbers, extract_platforms,
    detect_genre, detect_theme, is_gaming_related,
    extract_youtube, is_hd,
    THEME_EMOJI, THEME_HASHTAGS,
    TEMPLATES,
)
from bot.security import safe_download_image, detect_image_type
from bot.images import rss_image, find_post_image
from bot.learning import apply_game_override, source_score_mod


def _is_english(text: str) -> bool:
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


def make_caption(title: str, desc: str, link: str, game: str = None) -> str:
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


def _log_post_history(title, game, source, msg_id):
    try:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} | {msg_id} | {source} | {game or ''} | {title[:60]}"
        os.makedirs(os.path.dirname(POST_LOG_FILE), exist_ok=True)
        with open(POST_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"  Post history log err: {e}")


def send_post(title: str, desc: str, link: str, img_url: str | None, youtube_url: str = None, game: str = None, custom_caption: str = None) -> int | None:
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
                    _log_post_history(title, game, "photo", msg_id)
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
        _log_post_history(title, game, "text", msg_id)
        return msg_id
    print(f"  Send failed")
    return None


def score_news_item(item: dict, ids: dict, content_hashes: dict, recent_games: set, learning: dict = None) -> dict | None:
    if item.get("id") in ids:
        return None
    if str(item.get("content_hash", "")) in content_hashes:
        return None
    result = dict(item)
    score = 0
    desc_len = len(result.get("desc", ""))
    score += min(desc_len * _SCORING["desc_score_per_char"], _SCORING["desc_max_score"])
    if extract_numbers(result.get("desc", "")):
        score += _SCORING["numbers_boost"]
    if extract_platforms(result["title"] + " " + result.get("desc", "")):
        score += _SCORING["platforms_boost"]
    game = extract_game(result["title"])
    if learning:
        override = apply_game_override(learning, result["title"])
        if override:
            game = override
            result["_override"] = True
    game_lower = game.lower()
    if not is_gaming_related(result["title"], result.get("desc", "")):
        score += _SCORING["non_gaming_penalty"]
    elif game and len(game_lower) > 3:
        score += _SCORING["game_found_boost"]
    if game_lower and len(game_lower) > 3 and game_lower in recent_games:
        hot = any(kw in (result["title"] + " " + result.get("desc", "")).lower() for kw in PRIORITY_KEYWORDS)
        score += _SCORING["repeat_hot_penalty"] if hot else _SCORING["repeat_penalty"]
    if learning:
        source = result.get("source", "")
        score += source_score_mod(learning, source)
    theme = detect_theme(result["title"], result.get("desc", ""))
    if is_hot(result):
        score += _SCORING["hot_boost"]
    if is_trailer(result["title"]):
        score += _SCORING["trailer_boost"]
    if result.get("youtube_url"):
        score += _SCORING["youtube_boost"]
    if theme == "rumor":
        score += _SCORING["rumor_penalty"]
    result["_score"] = score
    result["_game"] = game
    result["_theme"] = theme
    return result


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
        if src_err.get("count", 0) > 10 and time.time() - src_err.get("time", 0) < 86400:
            print(f"  {source}: hard blocked (10+ errors in 24h)")
            return []
        entries = []
        for attempt in range(2):
            try:
                resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"}, stream=True)
                max_bytes = 2 * 1024 * 1024
                raw = b""
                for chunk in resp.iter_content(chunk_size=65536):
                    raw += chunk
                    if len(raw) > max_bytes:
                        print(f"  {source}: feed too large ({len(raw)} bytes), truncating")
                        break
                feed = feedparser.parse(raw)
                seen = set()
                for entry in feed.entries[:limit]:
                    raw_desc = entry.get("description", "") or ""
                    raw_title = entry.get("title", "") or ""
                    if len(raw_title) > 2000:
                        print(f"  {source}: oversized title ({len(raw_title)} chars), truncating")
                        raw_title = raw_title[:2000]
                    if len(raw_desc) > 50000:
                        print(f"  {source}: oversized desc ({len(raw_desc)} chars), truncating")
                        raw_desc = raw_desc[:50000]
                    title = clean(raw_title)
                    desc = clean_desc(raw_desc)
                    link = entry.get("link", "")
                    norm = re.sub(r"[^a-zа-яё0-9 ]", "", (title + desc[:100]).lower())
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
