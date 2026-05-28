import os
import sys
import time
import signal
import atexit
import requests
from datetime import datetime, timezone

from bot.config import (
    STATE_FILE, LOG_FILE, CHANNEL_ID, CHANNEL_SIGNATURE, ADMIN_CHAT,
    ADMIN_CHAT_ID, SILENT_HOURS, MODERATION_INTERVAL,
    MODERATION_TTL, set_global_state, WATCHED_GAMES,
)
from bot.core import (
    _get_token, tg, save_state, escape_md, clean, clean_desc,
    is_hot, is_trailer, extract_game, extract_numbers,
    extract_platforms, detect_theme, check_user_reply,
    get_recent_game_names, get_recent_titles, title_similarity,
    is_gaming_related, pick, load_state, log, shorten, send_audio_file,
)
from bot.security import (
    security_check, _acquire_lock, _release_lock, _safe_exit,
    _disk_space_check,
)
from bot.features import (
    send_post, send_live_notification, fetch_news,
    fetch_steam_deals, fetch_epic_free_games, fetch_gog_free_games,
    send_deals_batch, check_is_live,
    make_caption, reply_to_comments, post_listener_track,
    post_anime_news, post_rock_news, make_channel_stats,
    game_ost_tracks, find_post_image,
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

    # Twitch live
    print("Checking Twitch...")
    live = check_is_live()
    if live:
        title, game = live
        was_live = state.get("stream_live_posted", False)
        if not was_live:
            print(f"  LIVE: {title}")
            send_live_notification(title, game)
            state["stream_live_posted"] = True
        else:
            print(f"  Already posted live notification")
    else:
        if state.get("stream_live_posted", False):
            print("  Stream ended, resetting flag")
        state["stream_live_posted"] = False

    now_h = time.localtime().tm_hour
    now_wday = time.localtime().tm_wday
    today = time.strftime("%Y-%m-%d")

    if now_h in SILENT_HOURS:
        print(f"Night mode ({now_h}:00 — {max(SILENT_HOURS)+1}:00), skipping news")
        save_state(state)
        _release_lock()
        return

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
        deal_msg = send_deals_batch([], new_epic, new_gog)
        if deal_msg:
            posted += 1
        new_ids = {g["title"] for g in new_free}
        epic_free = [g for g in epic_free if g["title"] not in new_ids]
        gog_free = [g for g in gog_free if g["title"] not in new_ids]

    if today != deals_date:
        state["last_deals_date"] = today
        has_deals = steam_deals or epic_free or gog_free
        if has_deals:
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
        lines = ["\U0001F4E6 **Скидки на отслеживаемые игры!**", ""]
        for d in watched_matched:
            lines.append(f"\U0001F539 [{escape_md(d['title'])} -{d['discount']}%](https://store.steampowered.com/app/{d['appid']}/)")
            lines.append(f"   \u20BD {d['final_price']:.0f} вместо {d['original_price']:.0f}")
            if d.get("expires"):
                lines.append(f"   \U0001F512 до {d['expires']}")
        text = "\n".join(lines)
        try:
            r = tg("sendMessage", json={
                "chat_id": ADMIN_CHAT,
                "text": text, "parse_mode": "Markdown",
                "disable_web_page_preview": False,
            }, timeout=8)
            print(f"  Watched game alert sent ({len(watched_matched)} items)")
        except Exception as e:
            print(f"  Watched alert err: {e}")

    # Anime & rock auto-post by time
    if 14 <= now_h <= 16:
        post_anime_news(state)
    if now_h in (12, 15, 18):
        post_rock_news(state)

    save_state(state)

    # Fetch & score news
    raw = fetch_news()
    print(f"\nTotal raw items: {len(raw)}")

    unseen = []
    content_hashes = state.setdefault("content_hashes", {})
    posted_msgs = state.setdefault("posted_msgs", {})
    recent_games = get_recent_game_names(posted_msgs)
    recent_titles = get_recent_titles(posted_msgs)
    for item in raw:
        if item["id"] in ids:
            continue
        if str(item["content_hash"]) in content_hashes:
            continue
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
        item["_score"] = score
        item["_game"] = game
        item["_theme"] = theme
        recent_games = get_recent_game_names(posted_msgs)
        unseen.append(item)

    unseen.sort(key=lambda x: -x["_score"])
    print(f"Unseen candidates: {len(unseen)}")

    # Moderation
    pending = state.get("pending_moderation", [])

    # Check replies for existing pending
    new_pending = []
    for p in pending:
        msg_id = p.get("msg_id")
        if msg_id:
            reply = check_user_reply(state, msg_id)
            if reply:
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
                comment = escape_md(reply[:200]) if reply else ""
                if comment:
                    caption = caption.replace(CHANNEL_SIGNATURE, f"\n\n_{comment}_{CHANNEL_SIGNATURE}", 1)
                msg_id_posted = send_post(p_title, p_desc, p_link, p_img, p_youtube, p_game, caption)

                # OST tracks on approval
                if msg_id_posted and p_game:
                    p_game_name = extract_game(p_title)
                    if p_game_name and len(p_game_name) > 2:
                        tracks = game_ost_tracks(p_game_name, os.path.join(os.path.dirname(STATE_FILE), "audio_tmp"))
                        if tracks and len(tracks) >= 2:
                            for path, track_title in tracks[:2]:
                                if path and os.path.exists(path):
                                    r = send_audio_file(path, track_title)
                                    if r:
                                        print(f"  OST sent for {p_game_name}: {track_title[:50]}")

                if msg_id_posted:
                    posted += 1
                continue

        # Check TTL
        p_time = p.get("time", 0)
        if time.time() - p_time > MODERATION_TTL:
            print(f"  Moderation expired for {p.get('title', '?')[:40]}")
            continue
        new_pending.append(p)

    # Add new unseen items to pending
    last_mod = state.get("last_moderation_sent", 0)
    if unseen and (time.time() - last_mod >= MODERATION_INTERVAL):
        for best in unseen[:3]:
            caption = make_caption(best["title"], best.get("desc", ""), best["link"], best["_game"])
            img = find_post_image(best)
            preview_text = f"\U0001F514 **Пре-модерация**\n\n{caption}"
            r = tg("sendMessage", json={
                "chat_id": ADMIN_CHAT,
                "text": preview_text,
                "parse_mode": "Markdown",
            }, timeout=10)
            if r:
                mod_msg_id = r.json()["result"]["message_id"]
                new_pending.append({
                    "title": best["title"],
                    "desc": best.get("desc", ""),
                    "link": best["link"],
                    "img_url": img,
                    "youtube_url": best.get("youtube_url"),
                    "game": best["_game"],
                    "msg_id": mod_msg_id,
                    "time": time.time(),
                })
                print(f"  Moderation #{len(new_pending)}: {best['title'][:50]}")
                ids[best["id"]] = {"time": time.time()}
        if new_pending:
            state["last_moderation_sent"] = time.time()

    state["pending_moderation"] = new_pending

    # Reply to comments
    try:
        reply_to_comments(state)
    except Exception as e:
        print(f"  Comment reply err: {e}")

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
                "chat_id": CHANNEL_ID, "text": stats, "parse_mode": "Markdown",
            }, timeout=10)
            if r:
                print(f"  Weekly stats posted")
                posted += 1

    # Cleanup state
    state["ids"] = ids
    keep_keys = {
        "ids", "stream_live_posted", "last_digest", "posted_msgs",
        "deals_posted", "watched_alerted",
        "anime_posted", "rock_posted",
        "posted_rock_links", "posted_anime_links",
        "last_deals_date", "content_hashes", "comment_offset",
        "_bot_id", "listener_track", "last_moderation_sent",
        "pending_moderation", "moderation_offset",
    }
    for k in list(state.keys()):
        if k not in keep_keys:
            del state[k]
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
    recent_titles = get_recent_titles(posted_msgs)

    raw = fetch_news()
    print(f"\nTotal raw items: {len(raw)}")

    unseen = []
    for item in raw:
        if item["id"] in ids:
            continue
        if str(item["content_hash"]) in content_hashes:
            continue
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
        item["_score"] = score
        item["_game"] = game
        item["_theme"] = theme
        unseen.append(item)

    unseen.sort(key=lambda x: -x["_score"])
    print(f"Unseen candidates: {len(unseen)}")

    pending = state.get("pending_moderation", [])
    sent = 0
    for best in unseen[:count]:
        caption = make_caption(best["title"], best.get("desc", ""), best["link"], best["_game"])
        img = find_post_image(best)
        preview_text = f"\U0001F514 **Пре-модерация**\n\n{caption}"
        r = tg("sendMessage", json={
            "chat_id": ADMIN_CHAT,
            "text": preview_text,
            "parse_mode": "Markdown",
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
                            "chat_id": ADMIN_CHAT,
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
                        "chat_id": ADMIN_CHAT,
                        "text": f"\U0001F4A5 Bot crashed:\n\n{str(e)[:200]}",
                    }, timeout=8)
            except Exception:
                pass
