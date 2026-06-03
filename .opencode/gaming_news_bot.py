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
    validate_config, _SCORING,
)
from bot.core import (
    _get_token, tg, save_state, escape_html,
    get_recent_game_names,
    load_state,
)
from bot.security import (
    security_check, _acquire_lock, _release_lock, _safe_exit,
    _disk_space_check,
)
from bot.features import (
    fetch_news, score_news_item,
    fetch_steam_deals, fetch_epic_free_games, fetch_gog_free_games,
    send_deals_batch,
    post_anime_news, post_rock_news,
    make_channel_stats, send_daily_admin_stats,
    post_listener_chart, post_weekly_poll, post_weekly_comments,
)
from bot.learning import init_learning
from bot.moderation import (
    _process_moderation, force_moderation,
)


def _init_state():
    state = load_state()
    set_global_state("state", state)
    ids = state.get("ids", {})
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
                except Exception as _e:
                    print(f"  audio_tmp file remove err: {_e}")
            print(f"  Cleaned up audio_tmp/")
        except Exception as _e:
            print(f"  audio_tmp cleanup err: {_e}")
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
    learning = init_learning(state)
    for item in raw:
        scored = score_news_item(item, ids, content_hashes, recent_games, learning)
        if scored:
            unseen.append(scored)
    unseen.sort(key=lambda x: -x["_score"])
    print(f"Unseen candidates: {len(unseen)}")
    return unseen


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
        "_last_security_check","feed_errors","last_weekly_poll","poll_index","last_weekly_comments",
        "learning","last_posted_themes"}
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
    print("=== Gaming News Bot v5 (modular) ===\n")
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

run_iteration = main


def print_stats():
    state = load_state()
    posted = state.get("posted_msgs", {})
    ids = state.get("ids", {})
    deals = state.get("deals_posted", {})
    pending = state.get("pending_moderation", [])
    content_hashes = state.get("content_hashes", {})
    learning = state.get("learning", {})
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
    sq = learning.get("source_quality", {})
    if sq:
        print(f"  \U0001F4CA <b>Качество источников:</b>")
        for src, data in sorted(sq.items(), key=lambda x: -x[1].get("total", 0)):
            total = data.get("total", 0)
            skipped = data.get("skipped", 0)
            ratio = f"{skipped/total*100:.0f}%" if total > 0 else "-"
            print(f"    {src}: {data.get('posted',0)}/{total} posted, skip {ratio}")
    go = learning.get("game_overrides", {})
    active_overrides = {k: v for k, v in go.items() if not k.startswith("_")}
    if active_overrides:
        print(f"  \U0001F4CB <b>Коррекции названий:</b>")
        for k, v in sorted(active_overrides.items())[:10]:
            print(f"    \u00AB{k[:40]}\u00BB \u2192 {v}")
    print(f"{'='*40}\n")


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
        except Exception as _e:
            print(f"  _safe_exit err: {_e}")
    try:
        bot_token = _get_token()
        if bot_token:
            requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={
                "chat_id": ADMIN_CHAT_ID,
                "text": f"\u26A0 Bot {'crashed' if fatal else 'error'}:\n\n{str(e)[:200]}",
            }, timeout=8)
    except Exception as _e:
        print(f"  Crash alert send err: {_e}")


if __name__ == "__main__":
    from bot.poller import run_cli
    run_cli()
