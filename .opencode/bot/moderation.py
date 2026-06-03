import os
import time
import atexit
from concurrent.futures import ThreadPoolExecutor

from bot.config import (
    STATE_FILE, CHANNEL_ID, CHANNEL_SIGNATURE,
    ADMIN_CHAT_ID, WATCHED_GAMES, _SCORING,
    TITLE_DEDUP_MIN_WORDS, MODERATION_TTL, MODERATION_INTERVAL,
)
from bot.core import (
    tg, escape_html, extract_game, save_state,
    process_updates, load_state, send_audio_file, send_preview,
    is_hd, get_recent_game_names,
)
from bot.security import safe_download_image, _disk_space_check
from bot.images import find_post_image
from bot.features import (
    send_post, fetch_news, score_news_item, make_caption,
    game_ost_tracks, _send_rock_audio,
)
from bot.learning import (
    init_learning, track_source_post, track_source_skip, learn_game_override,
)


_AUDIO_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="audio")
atexit.register(lambda: _AUDIO_EXECUTOR.shutdown(wait=False))


def _send_moderation_preview(item, pending, pending_ids):
    img = find_post_image(item)
    preview = f"\U0001F514 <b>Пре-модерация</b>\n\n{make_caption(item['title'], item.get('desc',''), item['link'], item['_game'])}"
    img_bytes = None
    if img:
        try:
            b = safe_download_image(img, timeout=15)
            if b and is_hd(b):
                img_bytes = b
        except Exception as e:
            print(f"  Mod preview img err: {e}")
    mod_msg_id = send_preview(ADMIN_CHAT_ID, preview, img_bytes=img_bytes, timeout=25)
    if mod_msg_id:
        pending.append({
            "title": item["title"], "desc": item.get("desc",""), "link": item["link"],
            "img_url": img, "youtube_url": item.get("youtube_url"), "game": item["_game"],
            "source": item.get("source",""), "content_hash": item.get("content_hash",""),
            "msg_id": mod_msg_id, "time": time.time(),
            "id": item["id"],
        })
        pending_ids.add(item["id"])
    return mod_msg_id is not None


def _process_moderation(state, ids, unseen):
    posted = 0
    learning = init_learning(state)
    pending = state.get("pending_moderation", [])
    active = [p for p in pending if time.time() - p.get("time", 0) <= MODERATION_TTL]
    expired = len(pending) - len(active)
    if expired:
        print(f"  Moderation expired: {expired} items")
    pending_by_msg_id = {p["msg_id"]: p for p in active if p.get("msg_id")}
    pending_ids = {p.get("id") for p in active if p.get("id")}
    replies = process_updates(state, pending_by_msg_id)
    new_pending = []
    for p in active:
        msg_id = p.get("msg_id")
        if msg_id and msg_id in replies:
            reply = replies[msg_id]
            reply_lower = (reply or "").lower().strip()
            if not reply or reply_lower in ("skip", "пропуск", "нет", "no"):
                print(f"  Moderation skipped: {p.get('title', '?')[:40]}")
                track_source_skip(learning, p.get("source", "unknown"))
                if p.get("id"):
                    pending_ids.discard(p["id"])
                continue
            p_title, p_desc, p_link = p.get("title",""), p.get("desc",""), p.get("link","")
            p_img, p_youtube, p_game = p.get("img_url"), p.get("youtube_url"), p.get("game")
            if reply_lower.startswith("caption:"):
                caption = reply[8:].strip() or make_caption(p_title, p_desc, p_link, p_game)
                print(f"  Caption override: {caption[:60]}...")
            else:
                caption = make_caption(p_title, p_desc, p_link, p_game)
                comment = escape_html(reply[:200])
                marker = "\n\nПодробнее:"
                if marker in caption:
                    caption = caption.replace(marker, f"\n\n<blockquote>{comment}</blockquote>{marker}", 1)
                else:
                    caption = caption.replace(CHANNEL_SIGNATURE, f"\n\n<i>{comment}</i>{CHANNEL_SIGNATURE}", 1)
                learned_game = extract_game(reply)
                if learned_game and learned_game != p_game and len(learned_game) > 2:
                    learn_game_override(learning, p_title, learned_game)
                    print(f"  Learned game override: '{p_game}' -> '{learned_game}'")
            custom_cap = p.get("custom_caption")
            if custom_cap and not reply_lower.startswith("caption:"):
                comment = escape_html(reply[:200])
                marker = "\n\nПодробнее:"
                if marker in custom_cap:
                    custom_cap = custom_cap.replace(marker, f"\n\n<blockquote>{comment}</blockquote>{marker}", 1)
                else:
                    custom_cap = custom_cap.replace(CHANNEL_SIGNATURE, f"\n\n<i>{comment}</i>{CHANNEL_SIGNATURE}", 1)
                print(f"  Admin comment embedded into custom caption")
            elif not custom_cap:
                custom_cap = caption
            msg_id_posted = send_post(p_title, p_desc, p_link, p_img, p_youtube, p_game, caption=custom_cap)
            if msg_id_posted:
                track_source_post(learning, p.get("source", "unknown"))
                posted_msgs = state.setdefault("posted_msgs", {})
                posted_msgs[str(msg_id_posted)] = {"title": p_title, "game": p_game or "",
                    "time": time.time(), "source": p.get("source", "moderation")}
                ch = p.get("content_hash")
                if ch:
                    state.setdefault("content_hashes", {})[str(ch)] = time.time()
                pid = p.get("id")
                if pid:
                    ids[pid] = {"time": time.time()}
                    pending_ids.discard(pid)
                posted += 1
                ptype = p.get("_type", "")
                if ptype == "rock":
                    today = time.strftime("%Y-%m-%d")
                    state["rock_posted"] = today
                    rocks_links = state.setdefault("posted_rock_links", [])
                    rlink = p.get("_link")
                    if rlink and rlink not in rocks_links:
                        rocks_links.append(rlink)
                    artist = p.get("_artist", "")
                    if artist:
                        tmpdir = p.get("_tmpdir", "")
                        if tmpdir:
                            _AUDIO_EXECUTOR.submit(_post_rock_audio_worker, artist, tmpdir)
                elif ptype == "anime":
                    state["anime_posted"] = time.strftime("%Y-%m-%d")
                    anime_links = state.setdefault("posted_anime_links", [])
                    alink = p.get("_link") or p.get("link")
                    if alink and alink not in anime_links:
                        anime_links.append(alink)
                elif p_game and any(w in p_game.lower() for w in WATCHED_GAMES):
                    name = extract_game(p_title)
                    if name and len(name) > 2:
                        tmpdir = os.path.join(os.path.dirname(STATE_FILE), "audio_tmp")
                        print(f"  OST download queued for: {name}")
                        _AUDIO_EXECUTOR.submit(_post_ost_worker, name, p_title, tmpdir)
                continue
        new_pending.append(p)
    last_mod = state.get("last_moderation_sent", 0)
    if unseen and time.time() - last_mod >= MODERATION_INTERVAL:
        unseen_filtered = [x for x in unseen if x["id"] not in pending_ids]
        if not unseen_filtered:
            state["pending_moderation"] = new_pending
            return posted
        last_themes = state.get("last_posted_themes", [])
        unseen_filtered.sort(key=lambda x: (last_themes.count(x.get("_theme", "generic")), -x["_score"]))
        sent = 0
        posted_msgs = state.get("posted_msgs", {})
        dedup_cutoff = time.time() - _SCORING["title_dedup_hours"] * 3600
        posted_titles = [
            v.get("title", "") for v in posted_msgs.values()
            if v.get("time", 0) >= dedup_cutoff and v.get("title")
        ]
        threshold = _SCORING["title_dedup_threshold"]
        for best in unseen_filtered:
            title_new = best["title"]
            words_new = set(title_new.lower().split())
            dup = False
            if len(words_new) >= TITLE_DEDUP_MIN_WORDS:
                for old_title in posted_titles:
                    words_old = set(old_title.lower().split())
                    if len(words_old) < TITLE_DEDUP_MIN_WORDS:
                        continue
                    inter = len(words_new & words_old)
                    union = len(words_new | words_old)
                    if union > 0 and inter / union >= threshold:
                        dup = True
                        break
            if dup:
                continue
            if _send_moderation_preview(best, new_pending, pending_ids):
                sent += 1
        if new_pending:
            themes = [x.get("_theme", "generic") for x in unseen_filtered[:3]]
            state["last_posted_themes"] = (state.get("last_posted_themes", []) + themes)[-3:]
            state["last_moderation_sent"] = time.time()
            print(f"  Sent {sent} items for moderation")
    state["pending_moderation"] = new_pending
    return posted


def _post_watched_auto(state, ids, unseen):
    posted = 0
    last_themes = state.get("last_posted_themes", [])
    for item in unseen:
        if any(w in item.get("_game", "").lower() for w in WATCHED_GAMES) and item["_score"] > _SCORING["min_watched_auto_score"]:
            theme = item.get("_theme", "generic")
            if theme in last_themes:
                print(f"  WATCHED_GAMES skip (theme {theme} recently posted): {item['title'][:40]}")
                continue
            print(f"  WATCHED_GAMES auto-post: {item['title'][:50]}")
            img = find_post_image(item)
            msg_id = send_post(item["title"], item.get("desc", ""), item["link"], img,
                item.get("youtube_url"), item["_game"])
            if msg_id:
                posted_msgs = state.setdefault("posted_msgs", {})
                posted_msgs[str(msg_id)] = {"title": item["title"], "game": item["_game"] or "",
                    "time": time.time(), "source": item.get("source", "watched")}
                ch = item.get("content_hash")
                if ch:
                    state.setdefault("content_hashes", {})[str(ch)] = time.time()
                ids[item["id"]] = {"time": time.time()}
                posted += 1
                state["last_posted_themes"] = (state.get("last_posted_themes", []) + [theme])[-3:]
                try:
                    tg("sendMessage", json={"chat_id": ADMIN_CHAT_ID,
                        "text": f"\U0001F4E6 <b>Авто-пост:</b> {escape_html(item['_game'] or item['title'][:30])}",
                        "parse_mode": "HTML"}, timeout=8)
                except Exception as e:
                    print(f"  Auto-post notify err: {e}")
            break
    return posted


def _post_ost_worker(name, title, tmpdir):
    for path, tt in (game_ost_tracks(name, tmpdir) or [])[:2]:
        if path and os.path.exists(path):
            send_audio_file(path, tt)


def _post_rock_audio_worker(artist, tmpdir):
    try:
        _send_rock_audio(artist, tmpdir)
    except Exception as e:
        print(f"  Rock audio worker err: {e}")


def force_moderation(count=3):
    state = load_state()
    _disk_space_check()
    ids = state.get("ids", {})
    content_hashes = state.setdefault("content_hashes", {})
    posted_msgs = state.setdefault("posted_msgs", {})
    recent_games = get_recent_game_names(posted_msgs)

    raw = fetch_news()
    print(f"\nTotal raw items: {len(raw)}")

    unseen = []
    for item in raw:
        scored = score_news_item(item, ids, content_hashes, recent_games)
        if scored:
            unseen.append(scored)

    unseen.sort(key=lambda x: -x["_score"])
    print(f"Unseen candidates: {len(unseen)}")

    pending = state.get("pending_moderation", [])
    pending_ids = {p.get("id") for p in pending if p.get("id")}
    sent = 0
    for best in unseen[:count]:
        if best["id"] in pending_ids:
            print(f"  Already pending: {best['title'][:40]}")
            continue
        if _send_moderation_preview(best, pending, pending_ids):
            print(f"  Moderation #{sent+1}: {best['title'][:50]}")
            sent += 1

    state["pending_moderation"] = pending
    state["last_moderation_sent"] = time.time()
    save_state(state)
    print(f"\nSent {sent} moderation previews")
