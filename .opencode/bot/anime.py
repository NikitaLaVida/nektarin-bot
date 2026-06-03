import os
import time
import requests
import feedparser
from bot.config import (
    ADMIN_CHAT_ID, CHANNEL_SIGNATURE,
    ANIME_FEEDS, ANIME_EMOJI_MAP, ANIME_COMMENTARIES, _SEP,
)
from bot.core import (
    tg, escape_html, clean, clean_desc, shorten,
    translate_en_ru, pick, is_hd, send_preview, detect_theme,
)
from bot.security import safe_download_image
from bot.images import rss_image


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
    preview = f"\U0001F514 <b>Пре-модерация (аниме)</b>\n\n{caption}"
    img_bytes = None
    if img:
        try:
            b = safe_download_image(img, timeout=8)
            if b and is_hd(b):
                img_bytes = b
        except Exception as e:
            print(f"  Anime preview img err: {e}")
    mod_msg_id = send_preview(ADMIN_CHAT_ID, preview, img_bytes=img_bytes, timeout=15)
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
