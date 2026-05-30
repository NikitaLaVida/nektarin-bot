import os
import sys
import json
import re
import time
import random
import requests
import io
from html import unescape
from PIL import Image
from deep_translator import GoogleTranslator

from bot.config import (
    STATE_FILE, LOG_FILE, TG_API, TG_PROXY, MAX_RSS_TEXT_LEN,
    MAX_IMAGE_SIZE, PRIORITY_KEYWORDS, YOUTUBE_RE_SRC,
    TRAILER_KEYWORDS, BOILERPLATE, MAX_CAPTION_LEN, MAX_DESC_LEN,
    CHANNEL_SIGNATURE, THEME_WORDS, GENRE_TAGS, PLATFORMS,
    GAMING_SIGNAL_WORDS, NON_GAMING_TITLE_WORDS,
    GAME_DEDUP_HOURS, TITLE_DEDUP_HOURS, TITLE_DEDUP_MIN_WORDS,
    WIKI_UA, _CFG, ADMIN_CHAT_ID,
    CHANNEL_ID, BOT_TOKEN, _SEP, TG_PROXY as TG_PROXY_VAL,
)

_TRANSLATOR = GoogleTranslator(source='en', target='ru')
_TRANSLATE_CACHE = {}
_TRANSLATE_CACHE_MAX = 500
_orig_print = print

def safe_print(*args, **kwargs):
    safe = []
    for a in args:
        if isinstance(a, str):
            safe.append(a.encode("utf-8", errors="replace").decode("utf-8", errors="replace").encode("cp1251", errors="replace").decode("cp1251"))
        else:
            safe.append(a)
    _orig_print(*safe, **kwargs)

print = safe_print


def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def escape_html(text):
    text = str(text)
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def clean(text):
    text = unescape(text or "")
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text[:MAX_RSS_TEXT_LEN]
    text = text.replace("\x00", "")
    return text


def clean_desc(text):
    text = clean(text)
    for pat in BOILERPLATE:
        text = re.sub(pat, "", text, flags=re.I | re.M)
    return text.strip().strip(",").strip()


def shorten(s, max_len=200):
    if not s:
        return ""
    if len(s) <= max_len:
        return s
    half = max_len // 2
    for sep, keep in [(". ", 1), ("! ", 1), ("? ", 1), (", ", 0), (" ", 0)]:
        cut = s.rfind(sep, 0, max_len)
        if half < cut <= max_len:
            return s[:cut + keep]
    return s[:max_len].rstrip()


def translate_en_ru(text):
    if not text:
        return text
    key = text[:200]
    if key in _TRANSLATE_CACHE:
        return _TRANSLATE_CACHE[key]
    if len(_TRANSLATE_CACHE) >= _TRANSLATE_CACHE_MAX:
        _TRANSLATE_CACHE.clear()
    try:
        result = _TRANSLATOR.translate(text)
        _TRANSLATE_CACHE[key] = result
        return result
    except Exception as e:
        print(f"  Translation error: {e}")
        _TRANSLATE_CACHE[key] = text
        return text


def is_hot(item):
    text = (item["title"] + " " + item.get("desc", "")).lower()
    for kw in PRIORITY_KEYWORDS:
        if kw in text:
            return True
    return False


def is_trailer(title):
    t = title.lower()
    return any(kw in t for kw in TRAILER_KEYWORDS)


YOUTUBE_RE = re.compile(YOUTUBE_RE_SRC)


def extract_youtube(raw_html):
    m = YOUTUBE_RE.search(raw_html or "")
    if m:
        return f"https://www.youtube.com/watch?v={m.group(1)}"
    return None


def has_gaming_context(title, desc):
    text = (title + " " + desc).lower()
    for w in GAMING_SIGNAL_WORDS:
        if w in text:
            return True
    return False


def is_gaming_related(title, desc):
    t = title.lower()
    for w in NON_GAMING_TITLE_WORDS:
        if w in t:
            return has_gaming_context(title, desc)
    return True


def get_recent_game_names(posted_msgs, hours=GAME_DEDUP_HOURS):
    cutoff = time.time() - hours * 3600
    names = set()
    for mid, data in posted_msgs.items():
        t = data.get("time", 0)
        if t >= cutoff and data.get("game"):
            names.add(data["game"].lower())
    return names


def get_recent_titles(posted_msgs, hours=TITLE_DEDUP_HOURS):
    cutoff = time.time() - hours * 3600
    titles = []
    for mid, data in posted_msgs.items():
        t = data.get("time", 0)
        title = data.get("title", "")
        if t >= cutoff and title:
            titles.append(title.lower())
    return titles


def title_similarity(a, b):
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if len(words_a) < TITLE_DEDUP_MIN_WORDS or len(words_b) < TITLE_DEDUP_MIN_WORDS:
        return 0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union) if union else 0


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"ids": {}}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)


def _get_token():
    token = BOT_TOKEN
    if not token:
        token = os.environ.get("BOT_TOKEN", "")
    if not token:
        token = os.environ.get("TG_BOT_TOKEN", "")
    if not token:
        token = _CFG.get("bot_token", "")
    return token


def tg(method, **kwargs):
    token = _get_token()
    if not token:
        print(f"  TG {method}: no token")
        return None
    try:
        timeout = kwargs.pop("timeout", 10)
        proxies = {"https": TG_PROXY_VAL} if TG_PROXY_VAL else None
        r = requests.post(f"{TG_API}{token}/{method}", timeout=timeout, proxies=proxies, **kwargs)
        if r.status_code == 200:
            return r
        print(f"  TG {method} failed ({r.status_code}): {r.text[:80]}")
    except Exception as e:
        print(f"  TG {method} err: {e}")
    return None


def tg_get(method, params=None):
    token = _get_token()
    if not token:
        return None
    try:
        proxies = {"https": TG_PROXY_VAL} if TG_PROXY_VAL else None
        r = requests.get(f"{TG_API}{token}/{method}", params=params, timeout=10, proxies=proxies)
        if r.status_code == 200:
            return r.json()
        print(f"  TG GET {method} failed ({r.status_code}): {r.text[:100]}")
    except Exception as e:
        print(f"  TG GET {method} err: {e}")
    return None


def process_updates(state, pending_by_msg_id):
    bot_id = state.get("_bot_id", 0)
    linked_group = state.get("_linked_chat_id", 0)
    if not bot_id:
        try:
            me = tg("getMe", json={})
            if me:
                bot_id = me.json()["result"]["id"]
                state["_bot_id"] = bot_id
        except Exception:
            pass
    if not linked_group:
        try:
            chat_info = tg("getChat", json={"chat_id": CHANNEL_ID})
            if chat_info:
                data = chat_info.json()
                linked_group = data.get("result", {}).get("linked_chat_id")
                if linked_group:
                    state["_linked_chat_id"] = linked_group
        except Exception:
            pass
    if not pending_by_msg_id and not linked_group:
        return {}
    offset = state.get("moderation_offset", 0)
    result = tg_get("getUpdates", {"offset": offset, "timeout": 0})
    if not result:
        return {}
    replies = {}
    target_set = set(pending_by_msg_id) if pending_by_msg_id else set()
    for update in result.get("result", []):
        upd_id = update["update_id"]
        msg = update.get("message", {})
        if not msg:
            state["moderation_offset"] = upd_id + 1
            continue
        from_id = msg.get("from", {}).get("id", 0)
        chat_id = msg.get("chat", {}).get("id")
        text = msg.get("text", "").strip()
        if from_id == ADMIN_CHAT_ID:
            reply = msg.get("reply_to_message", {})
            reply_to = reply.get("message_id")
            if reply_to in target_set:
                replies[reply_to] = text or None
                state["moderation_offset"] = upd_id + 1
                continue
        if linked_group and chat_id == linked_group and text and from_id != bot_id:
            text_lower = text.lower()
            track_pats = [r" — ", r" – ", r" - ", r"–", r"—", r"youtube\.com", r"youtu\.be"]
            is_track = any(re.search(p, text) for p in track_pats) or \
                text_lower.startswith("трек ") or \
                text_lower.startswith("песня ") or \
                text_lower.startswith("музыка ")
            if is_track:
                state["listener_track"] = {
                    "text": text,
                    "from": msg.get("from", {}).get("first_name", "Подписчик"),
                    "time": time.time(),
                    "week": time.strftime("%Y-W%V"),
                }
                print(f"  Listener track saved: {text[:60]}")
            tg("sendMessage", json={
                "chat_id": linked_group,
                "text": random.choice(REPLY_TEMPLATES),
                "reply_to_message_id": msg.get("message_id"),
            }, timeout=10)
        state["moderation_offset"] = upd_id + 1
    return replies


def send_error(msg):
    try:
        tg("sendMessage", json={
            "chat_id": ADMIN_CHAT_ID,
            "text": f"\U0001F6A8 <b>Bot Error</b>\n\n{escape_html(msg[:500])}",
            "parse_mode": "HTML",
        }, timeout=8)
    except Exception:
        pass


def is_hd(img_data):
    try:
        img = Image.open(io.BytesIO(img_data))
        w, h = img.size
        if max(w, h) >= 1280:
            return True
        if w * h >= 500000:
            return True
        print(f"  Image too small: {w}x{h}")
        return False
    except Exception:
        return True


def detect_theme(title, desc):
    text = f"{title} {desc}".lower()
    for theme, words in THEME_WORDS.items():
        if any(w.lower() in text for w in words):
            return theme
    return "generic"


def extract_game(title):
    for sep in (" — ", " – ", " - ", " | ", ": ", "; "):
        if sep in title:
            title = title.split(sep)[0].strip()
    title = re.sub(r"[:;!?—–|/«»]", "", title)
    stop_words = {
        "предзагрузка", "обзор", "геймплей", "дата", "выхода", "системные",
        "создатель", "разработчики", "автор", "геймеры", "фанаты",
        "инсайдер", "журналисты", "студия", "релиз", "продажи", "тираж",
        "новый", "новая", "новые", "новое", "петиция", "объяснил",
        "рассказал", "подтвердил", "опроверг", "инсайд", "файтинг", "экшн",
        "хоррор", "rpg", "шутер", "стратеги", "гонки", "симулятор", "трейлер",
        "геймплейный", "требуют", "раскрыла", "показала", "получил", "доступна",
        "вышла", "вышел", "анонсировала", "объявила", "появится", "появился",
        "стал", "стала", "отложен", "перенесен", "назван", "уже",
        "завершили", "превысил", "подписали", "больше", "тысяч", "человек",
        "capcom", "bungie", "valve", "activision", "ubisoft", "bethesda",
        "microsoft", "sony", "nintendo",
        "playstation", "xbox", "консоль", "приставк",
        "в", "и", "на", "с", "со", "из", "по", "за", "от", "до",
        "у", "о", "об", "во", "при", "про", "для", "без", "через",
        "ещё", "уже", "все", "как", "так", "что", "кто", "где",
        "это", "его", "её", "их", "нам", "вам", "когда", "пока",
        "после", "снова", "опять", "теперь", "после", "также",
    }
    words = title.split()
    kept = []
    for w in words[:15]:
        wc = w.strip(".,!?-:;—–\"'()")
        if not wc:
            continue
        if re.match(r"^[a-zA-Z0-9].*", wc):
            kept.append(wc)
        elif wc[0].isupper() and wc.lower() not in stop_words:
            kept.append(wc)
    game = " ".join(kept).strip()
    platform_names = {"PS5", "PS4", "PS3", "Xbox", "PC", "Nintendo", "Switch", "Steam", "PlayStation"}
    parts = game.split()
    game = " ".join(p for p in parts if p not in platform_names).strip()
    game = re.sub(r"\bPlayStation\s*\d+\b", "", game, flags=re.I).strip()
    game = re.sub(r"\bNintendo\s+\w+\b", "", game, flags=re.I).strip()
    game = re.sub(r"\bXbox\s+(?:Series|One|360|)\b", "", game, flags=re.I).strip()
    game = re.sub(r"\bSwitch\s*2\b", "", game, flags=re.I).strip()
    game = re.sub(r"^(?:Capcom|Bungie|Valve|Activision|Ubisoft|Bethesda|Sony|Microsoft|Nintendo|EA)\s+", "", game, flags=re.I).strip()
    game = re.sub(r"\s+", " ", game).strip()
    if re.match(r"^[А-ЯЁ][а-яё]+\s*$", game):
        game = title[:40] if title else game
    if not game:
        game = words[0] if words else ""
    if 3 < len(game) <= 50:
        return game
    if len(game) > 50:
        short = game[:game.rfind(" ", 0, 47)]
        return short + "..." if len(short) > 3 else game[:45] + "..."
    return game[:40] if game else title[:30]


def extract_numbers(text):
    found = []
    for m in re.finditer(r"(\d[\d\s]*(?:[.,]\d+)?)\s*(млн|тыс|миллион|миллиард|%)?", text):
        num = m.group(1).replace(" ", "").replace(",", ".")
        unit = m.group(2) or ""
        found.append(f"{num} {unit}".strip())
    return found[:3]


def extract_platforms(text):
    return [p for p in PLATFORMS if p.lower() in text.lower()]


def detect_genre(text):
    for g in GENRE_TAGS:
        if g in text.lower():
            return g
    return None


def pick(seq):
    return random.choice(seq) if seq else ""


def smart_comment(theme, game, title):
    kw = escape_html(game) if game else ""
    ctx = {
        "sales": [f"Продажи {kw} бьют рекорды!", f"Народ раскупает {kw}", f"{kw} — успех!"],
        "delay": [f"Релиз {kw} отложили. Ну такое.", f"{kw} задерживается. Снова.", f"Перенос {kw}. Ну вот опять."],
        "sequel": [f"Продолжение {kw} на подходе!", f"В мир {kw} вернёмся скоро.", f"Сиквел {kw} — будет жарко."],
        "console": [f"{kw} выходит на консолях!", f"Консольщики, {kw} ваша.", f"{kw} — теперь и на диване."],
        "drama": [f"Скандал вокруг {kw}!", f"Драма: {kw} снова в центре.", f"Шум вокруг {kw} нарастает."],
        "rumor": [f"Слух: {kw}...", f"Говорят, {kw} готовит сюрприз.", f"Инсайд: {kw}."],
        "announce": [f"Анонс {kw}! Дождались.", f"{kw} официально анонсирована!", f"Ждали? {kw} в разработке."],
        "generic": [f"Новость дня.", f"Вот это поворот.", f"Держите в курсе."],
    }
    return random.choice(ctx.get(theme, ctx["generic"]))


COMMENTARIES = {
    "sales": [
        "Ого, неплохо продаётся!", "Народ знает толк.",
        "Миллионеры, блин.", "Кассовый успех на лицо.",
        "А вы уже купили или ждёте скидку?",
    ],
    "delay": [
        "Ну вот, опять перенос...", "Ждали? Потерпите ещё.",
        "Классика жанра — очередной перенос.",
        "Видимо, решили допилить до ума.", "Не судьба пока.",
    ],
    "sequel": [
        "О, а вот это интересно.", "Продолжение следует!",
        "Надо будет обязательно глянуть.",
        "Вернуться во вселенную — отличная идея.",
        "Сиквел, которого все ждали.",
    ],
    "console": [
        "Консольщики, внимание.", "Эксклюзивчик подвезли.",
        "На консолях тоже праздник.", "Поиграть можно будет и на диване.",
    ],
    "drama": [
        "Ой, всё...", "Скандалы, интриги, расследования.",
        "Драма на ровном месте.", "Без хайпа никак.",
        "И снова вокруг игры шум.",
    ],
    "generic": [
        "Вот такое дело.", "Новости игропрома.",
        "Держите в курсе.", "Будет интересно.", "На заметку.",
    ],
}


THEME_EMOJI = {
    "sales": "\U0001F4B0",
    "delay": "\u23F3",
    "sequel": "\U0001F525",
    "console": "\U0001F3AE",
    "drama": "\U0001F4A2",
    "rumor": "\U0001F52E",
    "announce": "\U0001F389",
    "generic": "\U0001F4F0",
}

THEME_HASHTAGS = {
    "sales": "#продажи",
    "delay": "#перенос",
    "sequel": "#сиквел",
    "console": "#консоли",
    "drama": "#драма",
    "rumor": "#слухи",
    "announce": "#анонс",
    "generic": "#игровыеновости",
}

REPLY_TEMPLATES = [
    "В точку! \U0001F44D", "Согласен на все 100%",
    "Мнение засчитано \U0001F91D", "Спорно, но достойно уважения",
    "Инсайдерская информация подтверждает", "Добавлю себе в цитатник",
    "Ты читаешь мои мысли", "Лучший комментарий недели",
    "Проверял — так и есть", "Ты слишком далеко зашёл \U0001F480",
    "Бот молчит — значит одобряет \u2705", "Задокументировано в архивах канала",
]


def embed_link(text, link):
    if not link or link in text:
        return text
    return f"{text}\n\nПодробнее: {link}"


def template_sales(title, desc, game, numbers, platforms, genre, link):
    s = shorten(desc, MAX_DESC_LEN)
    n = numbers[0] if numbers else "внушительное количество"
    commentary = smart_comment("sales", game, title)
    body = f"Продажи {game} достигли отметки в {n} копий. {s}"
    return [commentary, _SEP * 7, embed_link(body, link)]


def template_delay(title, desc, game, numbers, platforms, genre, link):
    s = shorten(desc, MAX_DESC_LEN)
    commentary = smart_comment("delay", game, title)
    body = f"Релиз {game} перенесён. {s}"
    return [commentary, _SEP * 7, embed_link(body, link)]


def template_sequel(title, desc, game, numbers, platforms, genre, link):
    s = shorten(desc, MAX_DESC_LEN)
    commentary = smart_comment("sequel", game, title)
    body = f"{game} — продолжение истории. {s}"
    return [commentary, _SEP * 7, embed_link(body, link)]


def template_console(title, desc, game, numbers, platforms, genre, link):
    s = shorten(desc, MAX_DESC_LEN)
    commentary = smart_comment("console", game, title)
    body = f"{game}{' на ' + '/'.join(platforms[:3]) if platforms else ''}. {s}"
    return [commentary, _SEP * 7, embed_link(body, link)]


def template_drama(title, desc, game, numbers, platforms, genre, link):
    s = shorten(desc, MAX_DESC_LEN)
    commentary = smart_comment("drama", game, title)
    body = f"Скандал вокруг {game}. {s}"
    return [commentary, _SEP * 7, embed_link(body, link)]


def template_generic(title, desc, game, numbers, platforms, genre, link):
    s = shorten(desc, MAX_DESC_LEN)
    commentary = smart_comment("generic", game, title)
    body = f"{title}. {s}" if s else title
    return [commentary, _SEP * 7, embed_link(body, link)]


def template_rumor(title, desc, game, numbers, platforms, genre, link):
    s = shorten(desc, MAX_DESC_LEN)
    commentary = smart_comment("rumor", game, title)
    body = f"Говорят, что {game}. {s}"
    return [commentary, _SEP * 7, embed_link(body, link)]


def template_announce(title, desc, game, numbers, platforms, genre, link):
    s = shorten(desc, MAX_DESC_LEN)
    commentary = smart_comment("announce", game, title)
    body = f"Анонс! {game}. {s}"
    return [commentary, _SEP * 7, embed_link(body, link)]


TEMPLATES = {
    "sales": template_sales,
    "delay": template_delay,
    "sequel": template_sequel,
    "console": template_console,
    "drama": template_drama,
    "rumor": template_rumor,
    "announce": template_announce,
    "generic": template_generic,
}


def send_audio_file(path, title, performer=None, chat_id=None):
    ext = os.path.splitext(path)[1] or ".webm"
    mime_map = {
        ".mp3": "audio/mpeg", ".m4a": "audio/mp4",
        ".webm": "audio/webm", ".opus": "audio/opus",
        ".ogg": "audio/ogg", ".wav": "audio/wav",
    }
    mime = mime_map.get(ext.lower(), "audio/mpeg")
    payload = {"chat_id": chat_id or CHANNEL_ID, "title": title[:60]}
    if performer:
        payload["performer"] = performer
    with open(path, "rb") as f:
        r = tg("sendAudio", data=payload,
               files={"audio": (f"audio{ext}", f, mime)}, timeout=30)
    if r:
        try:
            os.remove(path)
        except Exception:
            pass
    return r
