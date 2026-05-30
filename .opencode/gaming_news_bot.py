import os
import sys
import time
import signal
import atexit
import threading
import requests

from bot.config import (
    STATE_FILE, LOG_FILE, CHANNEL_ID, CHANNEL_SIGNATURE,
    ADMIN_CHAT_ID, SILENT_HOURS, MODERATION_INTERVAL,
    MODERATION_TTL, set_global_state, WATCHED_GAMES,
)
from bot.core import (
    _get_token, tg, save_state, escape_html,
    extract_game, process_updates,
    get_recent_game_names,
    load_state, send_audio_file,
)
from bot.security import (
    security_check, _acquire_lock, _release_lock, _safe_exit,
    _disk_space_check, safe_download_image, detect_image_type,
)
from bot.core import is_hd
from bot.features import (
    send_post, fetch_news, score_news_item,
    fetch_steam_deals, fetch_epic_free_games, fetch_gog_free_games,
    send_deals_batch,
    make_caption, post_listener_track,
    post_anime_news, post_rock_news, make_channel_stats,
    game_ost_tracks, find_post_image, send_daily_admin_stats,
)


def main():
    _acquire_lock()
    signal.signal(signal.SIGINT, _safe_exit)
    signal.signal(signal.SIGTERM, _safe_exit)
    atexit.register(_release_lock)

    if not _get_token():
        print("Error: no bot token")
        _release_lock()
        return

    class Tee:
        def __init__(self):
            os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
            self.file = open(LOG_FILE, "a", encoding="utf-8")
            self.console = sys.stdout
        def write(self, data):
            self.console.write(data)
            if data.strip():
                self.file.write(data)
                self.file.flush()
        def flush(self):
            self.console.flush()
            self.file.flush()
    sys.stdout = Tee()

    started = time.time()
    print("=== Gaming News Bot v4 (modular) ===\n")
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"Started at {ts}")
    log_path = os.path.abspath(LOG_FILE)
    print(f"Logging to {log_path}")

    _disk_space_check()

    state = load_state()
    set_global_state("state", state)
    ids = state.get("ids", {})

    ids_cutoff = time.time() - 7 * 86400
    ids = {k: v for k, v in ids.items() if v.get("time", 0) > ids_cutoff}
    if len(ids) > 5000:
        ids = dict(sorted(ids.items(), key=lambda x: -x[1]["time"])[:5000])

    # Cleanup temp audio
    tmpdir = os.path.join(os.path.dirname(STATE_FILE), "audio_tmp")
    if os.path.exists(tmpdir):
        try:
            for fname in os.listdir(tmpdir):
                fpath = os.path.join(tmpdir, fname)
                try:
                    if os.path.isfile(fpath):
                        os.remove(fpath)
                except Exception:
                    pass
            print(f"  Cleaned up audio_tmp/")
        except Exception:
            pass

    security_check(state)

    now_h = time.localtime().tm_hour
    now_wday = time.localtime().tm_wday
    today = time.strftime("%Y-%m-%d")
    is_daytime = now_h not in SILENT_HOURS

    posted = 0

    # Deals
    deals_date = state.setdefault("last_deals_date", "")
    deals_posted = state.setdefault("deals_posted", {})
    steam_deals = fetch_steam_deals()
    epic_free = fetch_epic_free_games()
    gog_free = fetch_gog_free_games()

    new_free = []
    for src_name, fg_list in [("Epic", epic_free), ("GOG", gog_free)]:
        for fg in fg_list:
            fg_id = fg["title"]
            if fg_id not in deals_posted:
                deals_posted[fg_id] = {"time": time.time()}
                new_free.append(fg)

    if new_free:
        print(f"  New free games: {len(new_free)}")
        new_epic = [g for g in epic_free if g["title"] in {x["title"] for x in new_free}]
        new_gog = [g for g in gog_free if g["title"] in {x["title"] for x in new_free}]
        if is_daytime:
            deal_msg = send_deals_batch([], new_epic, new_gog)
            if deal_msg:
                posted += 1
        new_ids = {g["title"] for g in new_free}
        epic_free = [g for g in epic_free if g["title"] not in new_ids]
        gog_free = [g for g in gog_free if g["title"] not in new_ids]

    if today != deals_date:
        state["last_deals_date"] = today
        has_deals = steam_deals or epic_free or gog_free
        if has_deals and is_daytime:
            deal_msg = send_deals_batch(steam_deals, epic_free, gog_free)
            if deal_msg:
                posted += 1

    # Watched games
    posted_msgs = state.get("posted_msgs", {})
    watched_matched = []
    if steam_deals:
        for deal in steam_deals:
            t = deal["title"].lower()
            if any(w in t for w in WATCHED_GAMES):
                watched_matched.append(deal)

    if watched_matched:
        lines = ["\U0001F4E6 <b>Скидки на отслеживаемые игры!</b>", ""]
        for d in watched_matched:
            app_link = f'https://store.steampowered.com/app/{d["appid"]}/'
            lines.append(f'\U0001F539 <a href="{app_link}">{escape_html(d["title"])} -{d["discount"]}%</a>')
            lines.append(f"   \u20BD {d['final_price']:.0f} вместо {d['original_price']:.0f}")
            if d.get("expires"):
                lines.append(f"   \U0001F512 до {d['expires']}")
        text = "\n".join(lines)
        try:
            r = tg("sendMessage", json={
                "chat_id": ADMIN_CHAT_ID,
                "text": text, "parse_mode": "HTML",
                "disable_web_page_preview": False,
            }, timeout=8)
            print(f"  Watched game alert sent ({len(watched_matched)} items)")
        except Exception as e:
            print(f"  Watched alert err: {e}")

    # Anime & rock auto-post by time
    if is_daytime:
        if now_h in (12, 18):
            post_anime_news(state)
        if now_h in (15, 21):
            post_rock_news(state)

    save_state(state)

    # Fetch & score news
    raw = fetch_news()
    print(f"\nTotal raw items: {len(raw)}")

    unseen = []
    content_hashes = state.setdefault("content_hashes", {})
    posted_msgs = state.setdefault("posted_msgs", {})
    recent_games = get_recent_game_names(posted_msgs)
    for item in raw:
        scored = score_news_item(item, ids, content_hashes, recent_games)
        if scored:
            recent_games = get_recent_game_names(posted_msgs)
            unseen.append(scored)

    unseen.sort(key=lambda x: -x["_score"])
    print(f"Unseen candidates: {len(unseen)}")

    # WATCHED_GAMES auto-post — bypass moderation
    watched_auto = None
    for item in unseen:
        game_lower = item.get("_game", "").lower()
        if any(w in game_lower for w in WATCHED_GAMES) and item["_score"] > 30:
            watched_auto = item
            break
    if watched_auto:
        print(f"  WATCHED_GAMES auto-post: {watched_auto['title'][:50]}")
        img = find_post_image(watched_auto)
        msg_id = send_post(
            watched_auto["title"], watched_auto.get("desc", ""),
            watched_auto["link"], img, watched_auto.get("youtube_url"),
            watched_auto["_game"],
        )
        if msg_id:
            posted_msgs = state.setdefault("posted_msgs", {})
            posted_msgs[str(msg_id)] = {
                "title": watched_auto["title"],
                "game": watched_auto["_game"] or "",
                "time": time.time(),
                "source": watched_auto.get("source", "watched"),
            }
            ch = watched_auto.get("content_hash")
            if ch:
                content_hashes = state.setdefault("content_hashes", {})
                content_hashes[str(ch)] = time.time()
            ids[watched_auto["id"]] = {"time": time.time()}
            posted += 1
            try:
                game_name = escape_html(watched_auto["_game"] or watched_auto["title"][:30])
                tg("sendMessage", json={
                    "chat_id": ADMIN_CHAT_ID,
                    "text": f"\U0001F4E6 <b>Авто-пост:</b> {game_name}\n\nСовпадение с WATCHED_GAMES, опубликовано в канал.",
                    "parse_mode": "HTML",
                }, timeout=8)
            except Exception:
                pass
            unseen = [x for x in unseen if x["id"] != watched_auto["id"]]

    # Moderation
    pending = state.get("pending_moderation", [])

    # Check TTL first — drop expired
    active_pending = []
    for p in pending:
        p_time = p.get("time", 0)
        if time.time() - p_time > MODERATION_TTL:
            print(f"  Moderation expired for {p.get('title', '?')[:40]}")
            continue
        active_pending.append(p)
    pending = active_pending

    # Check replies for ALL pending items in ONE API call
    pending_by_msg_id = {}
    for p in pending:
        msg_id = p.get("msg_id")
        if msg_id:
            pending_by_msg_id[msg_id] = p

    replies = process_updates(state, pending_by_msg_id)

    new_pending = []
    for p in pending:
        msg_id = p.get("msg_id")
        if msg_id and msg_id in replies:
            reply = replies[msg_id]
            if not reply:
                print(f"  Moderation skipped via empty reply")
                continue
            reply_lower = reply.lower().strip()
            skip_words = ["skip", "пропуск", "нет", "no"]
            if reply_lower in skip_words:
                print(f"  Moderation skipped via reply")
                continue
            # Approval — post the content
            p_title = p.get("title", "")
            p_desc = p.get("desc", "")
            p_link = p.get("link", "")
            p_img = p.get("img_url")
            p_youtube = p.get("youtube_url")
            p_game = p.get("game")
            # Add commentary
            caption = make_caption(p_title, p_desc, p_link, p_game)
            comment = escape_html(reply[:200]) if reply else ""
            if comment:
                marker = "\n\nПодробнее:"
                if marker in caption:
                    caption = caption.replace(marker, f"\n\n<blockquote>{comment}</blockquote>{marker}", 1)
                else:
                    caption = caption.replace(CHANNEL_SIGNATURE, f"\n\n<i>{comment}</i>{CHANNEL_SIGNATURE}", 1)
            msg_id_posted = send_post(p_title, p_desc, p_link, p_img, p_youtube, p_game, caption)

            if msg_id_posted:
                posted_msgs = state.setdefault("posted_msgs", {})
                posted_msgs[str(msg_id_posted)] = {
                    "title": p_title, "game": p_game or "",
                    "time": time.time(), "source": p.get("source", "moderation"),
                }
                ch = p.get("content_hash")
                if ch:
                    content_hashes = state.setdefault("content_hashes", {})
                    content_hashes[str(ch)] = time.time()
                posted += 1

                # OST tracks on approval (background thread)
                if p_game:
                    p_game_name = extract_game(p_title)
                    if p_game_name and len(p_game_name) > 2:
                        def _post_ost(name, title, tmpdir):
                            tracks = game_ost_tracks(name, tmpdir)
                            if tracks and len(tracks) >= 2:
                                for path, track_title in tracks[:2]:
                                    if path and os.path.exists(path):
                                        r = send_audio_file(path, track_title)
                                        if r:
                                            print(f"  OST sent for {name}: {track_title[:50]}")
                        tmpdir = os.path.join(os.path.dirname(STATE_FILE), "audio_tmp")
                        threading.Thread(target=_post_ost, args=(p_game_name, p_title, tmpdir), daemon=True).start()
            continue

        # Still waiting — re-add to pending
        new_pending.append(p)

    # Add new unseen items to pending
    last_mod = state.get("last_moderation_sent", 0)
    if unseen and (time.time() - last_mod >= MODERATION_INTERVAL):
        for best in unseen[:3]:
            caption = make_caption(best["title"], best.get("desc", ""), best["link"], best["_game"])
            img = find_post_image(best)
            preview_text = f"\U0001F514 <b>Пре-модерация</b>\n\n{caption}"
            mod_msg_id = None
            if img:
                try:
                    img_bytes = safe_download_image(img, timeout=10)
                    if img_bytes and is_hd(img_bytes):
                        ext, mime = detect_image_type(img_bytes)
                        r = tg("sendPhoto", data={
                            "chat_id": ADMIN_CHAT_ID, "caption": preview_text, "parse_mode": "HTML",
                        }, files={"photo": (f"preview.{ext}", img_bytes, mime)}, timeout=15)
                        if r:
                            mod_msg_id = r.json()["result"]["message_id"]
                except Exception:
                    pass
            if not mod_msg_id:
                r = tg("sendMessage", json={
                    "chat_id": ADMIN_CHAT_ID,
                    "text": preview_text,
                    "parse_mode": "HTML",
                }, timeout=10)
                if r:
                    mod_msg_id = r.json()["result"]["message_id"]
            if mod_msg_id:
                new_pending.append({
                    "title": best["title"],
                    "desc": best.get("desc", ""),
                    "link": best["link"],
                    "img_url": img,
                    "youtube_url": best.get("youtube_url"),
                    "game": best["_game"],
                    "source": best.get("source", ""),
                    "content_hash": best.get("content_hash", ""),
                    "msg_id": mod_msg_id,
                    "time": time.time(),
                })
                print(f"  Moderation #{len(new_pending)}: {best['title'][:50]}")
                ids[best["id"]] = {"time": time.time()}
        if new_pending:
            state["last_moderation_sent"] = time.time()

    state["pending_moderation"] = new_pending

    # Listener track
    try:
        post_listener_track(state)
    except Exception as e:
        print(f"  Listener track err: {e}")

    # Weekly stats
    if now_wday == 6 and now_h == 12:
        stats = make_channel_stats(state)
        if stats:
            r = tg("sendMessage", json={
                "chat_id": CHANNEL_ID, "text": stats, "parse_mode": "HTML",
            }, timeout=10)
            if r:
                print(f"  Weekly stats posted")
                posted += 1

    # Daily admin stats
    try:
        send_daily_admin_stats(state)
    except Exception as e:
        print(f"  Daily admin stats err: {e}")

    # Cleanup state
    state["ids"] = ids
    keep_keys = {
        "ids", "last_digest", "posted_msgs",
        "deals_posted",
        "anime_posted", "rock_posted",
        "posted_rock_links", "posted_anime_links",
        "last_deals_date", "content_hashes", "last_daily_admin_stats",
        "_bot_id", "_linked_chat_id", "listener_track", "last_moderation_sent",
        "pending_moderation", "moderation_offset",
        "_last_security_check", "feed_errors",
    }
    for k in list(state.keys()):
        if k not in keep_keys:
            del state[k]

    # TTL cleanup for unbounded state
    cutoff_7d = time.time() - 7 * 86400
    cutoff_30d = time.time() - 30 * 86400

    msgs = state.get("posted_msgs", {})
    msgs = {k: v for k, v in msgs.items() if v.get("time", 0) > cutoff_7d}
    if len(msgs) > 1000:
        msgs = dict(sorted(msgs.items(), key=lambda x: -x[1].get("time", 0))[:1000])
    state["posted_msgs"] = msgs

    ch = state.get("content_hashes", {})
    ch = {k: v for k, v in ch.items() if v > cutoff_7d}
    if len(ch) > 500:
        ch = dict(sorted(ch.items(), key=lambda x: -x[1])[:500])
    state["content_hashes"] = ch

    dp = state.get("deals_posted", {})
    dp = {k: v for k, v in dp.items() if v.get("time", 0) > cutoff_30d}
    if len(dp) > 500:
        dp = dict(sorted(dp.items(), key=lambda x: -x[1].get("time", 0))[:500])
    state["deals_posted"] = dp

    rl = state.get("posted_rock_links", [])
    if len(rl) > 100:
        state["posted_rock_links"] = rl[-100:]

    al = state.get("posted_anime_links", [])
    if len(al) > 100:
        state["posted_anime_links"] = al[-100:]

    save_state(state)
    print(f"\nNew posts: {posted}")
    print(f"History: {len(ids)}")


def run_iteration():
    main()
    _release_lock()
    _acquire_lock()


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
    sent = 0
    for best in unseen[:count]:
        caption = make_caption(best["title"], best.get("desc", ""), best["link"], best["_game"])
        img = find_post_image(best)
        preview_text = f"\U0001F514 <b>Пре-модерация</b>\n\n{caption}"
        r = tg("sendMessage", json={
            "chat_id": ADMIN_CHAT_ID,
            "text": preview_text,
            "parse_mode": "HTML",
        }, timeout=10)
        if r:
            mod_msg_id = r.json()["result"]["message_id"]
            pending.append({
                "title": best["title"],
                "desc": best.get("desc", ""),
                "link": best["link"],
                "img_url": img,
                "youtube_url": best.get("youtube_url"),
                "game": best["_game"],
                "source": best.get("source", ""),
                "content_hash": best.get("content_hash", ""),
                "msg_id": mod_msg_id,
                "time": time.time(),
            })
            ids[best["id"]] = {"time": time.time()}
            print(f"  Moderation #{sent+1}: {best['title'][:50]}")
            sent += 1

    state["pending_moderation"] = pending
    state["ids"] = ids
    state["last_moderation_sent"] = time.time()
    save_state(state)
    print(f"\nSent {sent} moderation previews")


if __name__ == "__main__":
    if "--stats" in sys.argv:
        state = load_state()
        posted = state.get("posted_msgs", {})
        print(f"=== Stats: {len(posted)} messages posted ===")
    elif "--mod" in sys.argv:
        n = 3
        for i, arg in enumerate(sys.argv):
            if arg == "--mod" and i + 1 < len(sys.argv) and sys.argv[i + 1].isdigit():
                n = int(sys.argv[i + 1])
        force_moderation(n)
    elif "--daemon" in sys.argv:
        interval = 1200
        for i, arg in enumerate(sys.argv):
            if arg == "--interval" and i + 1 < len(sys.argv):
                interval = int(sys.argv[i + 1])
        print(f"=== Daemon mode, interval={interval}s ===")
        while True:
            try:
                run_iteration()
            except Exception as e:
                import traceback
                err = traceback.format_exc()
                print(f"Daemon iteration failed: {e}\n{err}")
                try:
                    bot_token = _get_token()
                    if bot_token:
                        requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={
                            "chat_id": ADMIN_CHAT_ID,
                            "text": f"\u26A0 Daemon error:\n\n{str(e)[:200]}",
                        }, timeout=8)
                except Exception:
                    pass
            print(f"Sleeping {interval}s...")
            time.sleep(interval)
    else:
        try:
            main()
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            print(f"FATAL: {e}\n{err}")
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[CRASH] {err}\n")
            try:
                _safe_exit()
            except Exception:
                pass
            try:
                bot_token = _get_token()
                if bot_token:
                    requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={
                        "chat_id": ADMIN_CHAT_ID,
                        "text": f"\U0001F4A5 Bot crashed:\n\n{str(e)[:200]}",
                    }, timeout=8)
            except Exception:
                pass
