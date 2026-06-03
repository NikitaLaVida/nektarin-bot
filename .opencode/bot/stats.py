import os
import time
from bot.config import CHANNEL_ID, ADMIN_CHAT_ID
from bot.core import tg, escape_html


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
        state["weekly_comments"] = [c for c in comments if c.get("time", 0) <= week_ago]
        print(f"  Weekly comments posted ({len(week_comments)} collected, {len(best)} selected)")
        return True
    return False
