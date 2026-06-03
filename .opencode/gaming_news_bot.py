import os
import sys
import time
import signal
import atexit
import threading
from concurrent.futures import ThreadPoolExecutor
import requests

from bot.config import (
    STATE_FILE, LOG_FILE, CHANNEL_ID, CHANNEL_SIGNATURE,
    ADMIN_CHAT_ID, SILENT_HOURS, MODERATION_INTERVAL,
    MODERATION_TTL, set_global_state, WATCHED_GAMES,
    validate_config,
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
    make_caption, post_listener_chart,
    post_anime_news, post_rock_news, make_channel_stats,
    game_ost_tracks, find_post_image, send_daily_admin_stats,
    post_weekly_poll, post_weekly_comments,
    _send_rock_audio,
)


def _init_state():
    state = load_state()
    set_global_state("state", state)
    ids = state.get("ids", {})
    if ids and isinstance(next(iter(ids.values()), None), bool):
        ids = {k: (v if isinstance(v, dict) else {"time": 0}) for k, v in ids.items()}
        print(f"  Migrated legacy ids")
    try:
        cutoff = time.time() - 7 * 86400
        ids = {k: v for k, v in ids.items() if v.get("time", 0) > cutoff}
        if len(ids) > 5000:
            ids = dict(sorted(ids.items(), key=lambda x: -x[1]["time"])[:5000])
    except Exception as e:
        print(f"  ids cleanup err: {e}")
        ids = {}
    tmpdir = os.path.join(os.path.dirname(STATE_FILE), "audio_tmp")
    if os.path.exists(tmpdir):
        try:
            for f in os.listdir(tmpdir):
                try:
                    p = os.path.join(tmpdir, f)
                    if os.path.isfile(p):
                        os.remove(p)
                except Exception as _:
                    pass
            print(f"  Cleaned up audio_tmp/")
        except Exception as _:
            pass
    return state, ids


def _process_deals(state, today, is_daytime):
    posted = 0
    steam_deals = fetch_steam_deals()
    epic_free = fetch_epic_free_games()
    gog_free = fetch_gog_free_games()
    deals_posted = state.setdefault("deals_posted", {})
    new_epic = []
    new_gog = []
    for fg in epic_free:
        if fg["title"] not in deals_posted:
            deals_posted[fg["title"]] = {"time": time.time()}
            new_epic.append(fg)
    for fg in gog_free:
        if fg["title"] not in deals_posted:
            deals_posted[fg["title"]] = {"time": time.time()}
            new_gog.append(fg)
    if new_epic or new_gog:
        print(f"  New free games: {len(new_epic) + len(new_gog)}")
        if is_daytime:
            if send_deals_batch([], new_epic, new_gog):
                posted += 1
        new_epic_titles = {g["title"] for g in new_epic}
        new_gog_titles = {g["title"] for g in new_gog}
        epic_free = [g for g in epic_free if g["title"] not in new_epic_titles]
        gog_free = [g for g in gog_free if g["title"] not in new_gog_titles]
    if today != state.get("last_deals_date", ""):
        state["last_deals_date"] = today
        has = steam_deals or epic_free or gog_free
        if has and is_daytime:
            if send_deals_batch(steam_deals, epic_free, gog_free):
                posted += 1
    # Watched games
    if steam_deals:
        watched = [d for d in steam_deals if any(w in d["title"].lower() for w in WATCHED_GAMES)]
        if watched:
            lines = ["\U0001F4E6 <b>Скидки на отслеживаемые игры!</b>", ""]
            for d in watched:
                app_link = f'https://store.steampowered.com/app/{d["appid"]}/'
                lines.append(f'\U0001F539 <a href="{app_link}">{escape_html(d["title"])} -{d["discount"]}%</a>')
                lines.append(f"   \u20BD {d['final_price']:.0f} вместо {d['original_price']:.0f}")
                if d.get("expires"):
                    lines.append(f"   \U0001F512 до {d['expires']}")
            try:
                tg("sendMessage", json={"chat_id": ADMIN_CHAT_ID, "text": "\n".join(lines),
                    "parse_mode": "HTML", "disable_web_page_preview": False}, timeout=8)
                print(f"  Watched game alert sent ({len(watched)} items)")
            except Exception as e:
                print(f"  Watched alert err: {e}")
    return posted


def _post_scheduled(state, now_h):
    today = time.strftime("%Y-%m-%d")
    if state.get("anime_posted") != today and now_h >= 12:
        post_anime_news(state)
    if state.get("rock_posted") != today and now_h >= 15:
        post_rock_news(state)


def _fetch_and_score(state, ids):
    raw = fetch_news()
    print(f"\nTotal raw items: {len(raw)}")
    unseen = []
    content_hashes = state.setdefault("content_hashes", {})
    posted_msgs = state.setdefault("posted_msgs", {})
    recent_games = get_recent_game_names(posted_msgs)
    for item in raw:
        scored = score_news_item(item, ids, content_hashes, recent_games)
        if scored:
            unseen.append(scored)
    unseen.sort(key=lambda x: -x["_score"])
    print(f"Unseen candidates: {len(unseen)}")
    return unseen


def _post_watched_auto(state, ids, unseen):
    posted = 0
    for item in unseen:
        if any(w in item.get("_game", "").lower() for w in WATCHED_GAMES) and item["_score"] > 30:
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
                try:
                    tg("sendMessage", json={"chat_id": ADMIN_CHAT_ID,
                        "text": f"\U0001F4E6 <b>Авто-пост:</b> {escape_html(item['_game'] or item['title'][:30])}",
                        "parse_mode": "HTML"}, timeout=8)
                except Exception:
                    pass
            break
    return posted


def _send_moderation_preview(item, pending, pending_ids):
    img = find_post_image(item)
    preview = f"\U0001F514 <b>Пре-модерация</b>\n\n{make_caption(item['title'], item.get('desc',''), item['link'], item['_game'])}"
    mod_msg_id = None
    if img:
        try:
            b = safe_download_image(img, timeout=15)
            if b and is_hd(b):
                ext, mime = detect_image_type(b)
                r = tg("sendPhoto", data={"chat_id": ADMIN_CHAT_ID, "caption": preview,
                    "parse_mode": "HTML"}, files={"photo": (f"p.{ext}", b, mime)}, timeout=25)
                if r:
                    mod_msg_id = r.json()["result"]["message_id"]
        except Exception as e:
            print(f"  Mod preview img err: {e}")
    if not mod_msg_id:
        r = tg("sendMessage", json={"chat_id": ADMIN_CHAT_ID, "text": preview, "parse_mode": "HTML"}, timeout=15)
        if r:
            mod_msg_id = r.json()["result"]["message_id"]
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
        for best in unseen_filtered[:3]:
            if _send_moderation_preview(best, new_pending, pending_ids):
                pass
        if new_pending:
            state["last_moderation_sent"] = time.time()
    state["pending_moderation"] = new_pending
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


def _run_weekly_tasks(state, now_wday, now_h):
    if now_wday != 6 or now_h != 12:
        return 0
    posted = 0
    stats = make_channel_stats(state)
    if stats:
        try:
            if tg("sendMessage", json={"chat_id": CHANNEL_ID, "text": stats, "parse_mode": "HTML"}, timeout=10):
                posted += 1
        except Exception as e:
            print(f"  Weekly stats err: {e}")
    for fn, name in [(post_listener_chart, "chart"), (post_weekly_poll, "poll"), (post_weekly_comments, "comments")]:
        try:
            if fn(state):
                posted += 1
        except Exception as e:
            print(f"  Weekly {name} err: {e}")
    return posted


def _cleanup_state(state, ids):
    cutoff = time.time() - 14 * 86400
    ids = {k: v for k, v in ids.items() if isinstance(v, dict) and v.get("time", 0) > cutoff}
    if len(ids) > 3000:
        ids = dict(sorted(ids.items(), key=lambda x: -x[1].get("time", 0))[:3000])
    state["ids"] = ids
    keep = {"ids","last_digest","posted_msgs","deals_posted","anime_posted","rock_posted",
        "posted_rock_links","posted_anime_links","last_deals_date","content_hashes",
        "last_daily_admin_stats","_bot_id","_linked_chat_id","listener_tracks",
        "last_moderation_sent","pending_moderation","moderation_offset","weekly_comments",
        "_last_security_check","feed_errors","last_weekly_poll","poll_index","last_weekly_comments"}
    for k in list(state.keys()):
        if k not in keep:
            del state[k]
    try:
        c30 = time.time() - 30*86400
        msgs = state.get("posted_msgs", {})
        msgs = {k:v for k,v in msgs.items() if v.get("time",0) > c30}
        if len(msgs) > 2000:
            msgs = dict(sorted(msgs.items(), key=lambda x: -x[1].get("time",0))[:2000])
        state["posted_msgs"] = msgs
        ch = state.get("content_hashes", {})
        ch = {k:(v if isinstance(v,(int,float)) else time.time()) for k,v in ch.items()}
        ch = {k:v for k,v in ch.items() if v > c30}
        if len(ch) > 1000:
            ch = dict(sorted(ch.items(), key=lambda x: -x[1])[:1000])
        state["content_hashes"] = ch
        dp = state.get("deals_posted", {})
        dp = {k:v for k,v in dp.items() if v.get("time",0) > c30}
        if len(dp) > 500:
            dp = dict(sorted(dp.items(), key=lambda x: -x[1].get("time",0))[:500])
        state["deals_posted"] = dp
        for key, lim in [("posted_rock_links",100), ("posted_anime_links",100)]:
            lst = state.get(key, [])
            if len(lst) > lim:
                state[key] = lst[-lim:]
    except Exception as e:
        print(f"  State cleanup err: {e}")


def main():
    _acquire_lock()
    validate_config()
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
    print(f"Started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Logging to {os.path.abspath(LOG_FILE)}")

    _disk_space_check()
    state, ids = _init_state()
    security_check(state)

    now_h = time.localtime().tm_hour
    now_wday = time.localtime().tm_wday
    today = time.strftime("%Y-%m-%d")
    is_daytime = now_h not in SILENT_HOURS
    posted = 0

    posted += _process_deals(state, today, is_daytime)
    _post_scheduled(state, now_h)

    save_state(state)

    unseen = _fetch_and_score(state, ids)
    posted += _post_watched_auto(state, ids, unseen)
    unseen = [x for x in unseen if x["id"] not in ids]
    posted += _process_moderation(state, ids, unseen)

    posted += _run_weekly_tasks(state, now_wday, now_h)

    try:
        send_daily_admin_stats(state)
    except Exception as e:
        print(f"  Daily admin stats err: {e}")

    _cleanup_state(state, ids)
    save_state(state)

    print(f"\nNew posts: {posted}")
    print(f"History: {len(ids)}")
    global _LAST_RUN_TIME
    _LAST_RUN_TIME = time.time()


_LAST_RUN_TIME = 0
_AUDIO_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="audio")
atexit.register(lambda: _AUDIO_EXECUTOR.shutdown(wait=False))

run_iteration = main  # backward compat for server's main.py


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


if __name__ == "__main__":
    if "--stats" in sys.argv:
        state = load_state()
        posted = state.get("posted_msgs", {})
        ids = state.get("ids", {})
        deals = state.get("deals_posted", {})
        pending = state.get("pending_moderation", [])
        content_hashes = state.get("content_hashes", {})
        now = time.time()
        day_ago = now - 86400
        week_ago = now - 7 * 86400

        total = len(posted)
        today = sum(1 for d in posted.values() if d.get("time", 0) >= day_ago)
        this_week = sum(1 for d in posted.values() if d.get("time", 0) >= week_ago)

        source_counts = {}
        game_counts = {}
        for d in posted.values():
            src = d.get("source", "other")
            source_counts[src] = source_counts.get(src, 0) + 1
            game = d.get("game", "")
            if game:
                game_counts[game] = game_counts.get(game, 0) + 1

        top_games = sorted(game_counts.items(), key=lambda x: -x[1])[:10]
        top_sources = sorted(source_counts.items(), key=lambda x: -x[1])[:10]

        subs = 0
        try:
            r = tg("getChatMemberCount", json={"chat_id": CHANNEL_ID}, timeout=8)
            if r:
                subs = r.json().get("result", 0)
        except Exception:
            pass

        print(f"\n{'='*40}")
        print(f"  \U0001F4CA <b>NektarinBot Dashboard</b>")
        print(f"{'='*40}")
        print(f"  \U0001F465 Подписчиков:        {subs}")
        print(f"  \U0001F4F0 Всего постов:         {total}")
        print(f"  \U0001F4C5 За сегодня:           {today}")
        print(f"  \U0001F4C6 За неделю:            {this_week}")
        print(f"  \U0001F514 В модерации:          {len(pending)}")
        print(f"  \U0001F4E6 Скидок отправлено:     {len(deals)}")
        print(f"  \U0001F4C1 Уникальных URL:        {len(ids)}")
        print(f"  \U0001F4DC Хешей контента:        {len(content_hashes)}")
        print(f"{'='*40}")
        if top_sources:
            print(f"  \U0001F4E1 <b>Топ-источники:</b>")
            for s, c in top_sources:
                print(f"    {s}: {c}")
        if top_games:
            print(f"  \U0001F3AE <b>Топ-игры:</b>")
            for g, c in top_games:
                print(f"    {g}: {c}")
        print(f"{'='*40}\n")
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
        def _healthcheck():
            import socket as _socket
            s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
            s.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", 8080))
            s.listen(1)
            s.settimeout(1)
            while True:
                try:
                    conn, _ = s.accept()
                    stale = time.time() - _LAST_RUN_TIME > interval * 2.5
                    if stale:
                        body = f"stale last_run={int(_LAST_RUN_TIME)}"
                        conn.sendall(f"HTTP/1.1 503 Service Unavailable\r\nContent-Length: {len(body)}\r\n\r\n{body}".encode())
                    else:
                        conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
                    conn.close()
                except _socket.timeout:
                    continue
                except Exception:
                    break
        t = threading.Thread(target=_healthcheck, daemon=True)
        t.start()
        print(f"  Healthcheck on http://0.0.0.0:8080/healthz")
        while True:
            try:
                main()
            except Exception as e:
                _handle_crash(e, fatal=False)
            print(f"Sleeping {interval}s...")
            time.sleep(interval)
    else:
        try:
            main()
        except Exception as e:
            _handle_crash(e, fatal=True)

def _handle_crash(e, fatal=True):
    import traceback as _tb
    err = _tb.format_exc()
    log_text = f"[{'FATAL' if fatal else 'ERROR'}] {e}\n{err}"
    print(log_text)
    with open(LOG_FILE, "a", encoding="utf-8") as _f:
        _f.write(log_text + "\n")
    if fatal:
        try:
            _safe_exit()
        except Exception:
            pass
    try:
        bot_token = _get_token()
        if bot_token:
            requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={
                "chat_id": ADMIN_CHAT_ID,
                "text": f"\u26A0 Bot {'crashed' if fatal else 'error'}:\n\n{str(e)[:200]}",
            }, timeout=8)
    except Exception:
        pass
