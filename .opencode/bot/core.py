import os
import sys
import json
import re
import time
import random
import requests
import io
from functools import lru_cache
from html import unescape
from PIL import Image
from deep_translator import GoogleTranslator
from requests.exceptions import RequestException

from bot.config import (
    STATE_FILE, LOG_FILE, TG_API, MAX_RSS_TEXT_LEN,
    MAX_IMAGE_SIZE, PRIORITY_KEYWORDS, YOUTUBE_RE_SRC,
    TRAILER_KEYWORDS, BOILERPLATE, MAX_CAPTION_LEN, MAX_DESC_LEN,
    CHANNEL_SIGNATURE, THEME_WORDS, GENRE_TAGS, PLATFORMS,
    GAMING_SIGNAL_WORDS, NON_GAMING_TITLE_WORDS,
    GAME_DEDUP_HOURS, TITLE_DEDUP_MIN_WORDS,
    _CFG, ADMIN_CHAT_ID,
    CHANNEL_ID, BOT_TOKEN, _SEP, TG_PROXY as TG_PROXY_VAL,
)


def log(*args, **kwargs):
    safe = []
    for a in args:
        if isinstance(a, str):
            safe.append(a.encode("utf-8", errors="replace").decode("utf-8"))
        else:
            safe.append(a)
    print(*safe, **kwargs)





def escape_html(text: str) -> str:
    text = str(text)
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def clean(text: str) -> str:
    text = unescape(text or "")
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text[:MAX_RSS_TEXT_LEN]
    text = text.replace("\x00", "")
    return text


def clean_desc(text: str) -> str:
    text = clean(text)
    for pat in BOILERPLATE:
        text = re.sub(pat, "", text, flags=re.I | re.M)
    return text.strip().strip(",").strip()


def shorten(s: str, max_len: int = 200) -> str:
    if not s:
        return ""
    if len(s) <= max_len:
        return s
    half = max_len // 2
    for sep, keep in [(". ", 1), ("! ", 1), ("? ", 1), (", ", 0)]:
        cut = s.rfind(sep, 0, max_len)
        if half < cut <= max_len:
            return s[:cut + keep]
    last_space = s.rfind(" ", 0, max_len)
    if last_space > half:
        return s[:last_space]
    return s[:max_len].rstrip()


def _get_translator():
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source='en', target='ru')
    except Exception as e:
        log(f"  Translator init err: {e}")
        return None


_TRANSLATOR = None

@lru_cache(maxsize=1000)
def _do_translate(text):
    global _TRANSLATOR
    if _TRANSLATOR is None:
        _TRANSLATOR = _get_translator()
    if _TRANSLATOR:
        try:
            return _TRANSLATOR.translate(text)
        except Exception as e:
            log(f"  Translate err: {e}")
    return _translate_fallback(text)

def _translate_fallback(text):
    try:
        r = requests.get(
            "https://lingva.ml/api/v1/en/ru/" + requests.utils.quote(text[:500]),
            timeout=5,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("translation", text)
    except Exception as e:
        log(f"  lingva fallback err: {e}")
    try:
        r = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "en", "tl": "ru", "dt": "t", "q": text[:1000]},
            timeout=5,
        )
        if r.status_code == 200:
            parts = r.json()
            result = "".join(p[0] for p in parts[0] if p[0])
            if result:
                return result
    except Exception as e:
        log(f"  google translate fallback err: {e}")
    return text

def translate_en_ru(text: str) -> str:
    if not text:
        return text
    try:
        return _do_translate(text)
    except Exception as e:
        log(f"  GoogleTranslate error: {e}, trying fallback...")
        result = _translate_fallback(text)
        if result != text:
            return result
        log(f"  All translators failed")
        return text


def is_hot(item: dict) -> bool:
    text = (item["title"] + " " + item.get("desc", "")).lower()
    for kw in PRIORITY_KEYWORDS:
        if kw in text:
            return True
    return False


def is_trailer(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in TRAILER_KEYWORDS)


YOUTUBE_RE = re.compile(YOUTUBE_RE_SRC)


def extract_youtube(raw_html: str) -> str | None:
    m = YOUTUBE_RE.search(raw_html or "")
    if m:
        return f"https://www.youtube.com/watch?v={m.group(1)}"
    return None


def is_gaming_related(title: str, desc: str) -> bool:
    t = title.lower()
    for w in NON_GAMING_TITLE_WORDS:
        if w in t:
            game = extract_game(title)
            if game and len(game) > 3 and game.lower() not in NON_GAMING_TITLE_WORDS:
                return True
            text = (title + " " + desc).lower()
            return any(w in text for w in GAMING_SIGNAL_WORDS)
    return True


def get_recent_game_names(posted_msgs: dict, hours: int = GAME_DEDUP_HOURS) -> set:
    cutoff = time.time() - hours * 3600
    names = set()
    for mid, data in posted_msgs.items():
        t = data.get("time", 0)
        if t >= cutoff and data.get("game"):
            names.add(data["game"].lower())
    return names


def title_similarity(a, b):
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if len(words_a) < TITLE_DEDUP_MIN_WORDS or len(words_b) < TITLE_DEDUP_MIN_WORDS:
        return 0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union) if union else 0


_STATE_MIGRATIONS = {}

def _register_migration(version):
    def wrapper(fn):
        _STATE_MIGRATIONS[version] = fn
        return fn
    return wrapper


@_register_migration(0)
def _migrate_v1_ids(state):
    ids = state.get("ids", {})
    if ids and isinstance(next(iter(ids.values()), None), bool):
        state["ids"] = {k: {"time": 0} for k in ids}
        return True
    return False


def migrate_state(state):
    version = state.get("_state_version", 0)
    changed = False
    keys = sorted(_STATE_MIGRATIONS)
    for v in keys:
        if v < version:
            continue
        fn = _STATE_MIGRATIONS[v]
        try:
            if fn(state):
                changed = True
                log(f"  Migration v{v} applied")
        except Exception as e:
            log(f"  Migration v{v} failed: {e}")
        state["_state_version"] = v + 1
    return changed


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            size = os.path.getsize(STATE_FILE)
            if size > 50 * 1024 * 1024:
                log(f"  State file too large ({size // 1024 // 1024}MB), refusing load")
                return {"ids": {}}
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
            if migrate_state(state):
                save_state(state)
                log("  State migrated and saved")
            return state
        except (json.JSONDecodeError, OSError) as e:
            log(f"  Corrupt state file, starting fresh: {e}")
            import shutil
            bak = STATE_FILE + f".corrupt.{int(time.time())}"
            try:
                shutil.copy2(STATE_FILE, bak)
                log(f"  Backed up corrupt state to {bak}")
            except Exception:
                pass
    return {"ids": {}}


_LAST_SAVED_STATE = None


def save_state(state):
    global _LAST_SAVED_STATE
    content = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True)
    if content == _LAST_SAVED_STATE:
        return
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATE_FILE)
    _LAST_SAVED_STATE = content


def _get_token():
    token = BOT_TOKEN
    if not token:
        token = os.environ.get("BOT_TOKEN", "")
    if not token:
        token = os.environ.get("TG_BOT_TOKEN", "")
    if not token:
        token = _CFG.get("bot_token", "")
    return token


def _tg_request(method, http_method="post", params=None, **kwargs):
    token = _get_token()
    if not token:
        log(f"  TG {method}: no token")
        return None
    url = f"{TG_API}{token}/{method}"
    proxies = {"https": TG_PROXY_VAL} if TG_PROXY_VAL else None
    timeout = kwargs.pop("timeout", 15)
    for attempt in range(3):
        try:
            if http_method == "get":
                r = requests.get(url, params=params, timeout=timeout, proxies=proxies, **kwargs)
            else:
                r = requests.post(url, timeout=timeout, proxies=proxies, **kwargs)
            if r.status_code == 200:
                return r
            if 400 <= r.status_code < 500:
                log(f"  TG {method} client error ({r.status_code}): {r.text[:80]}")
                return None
            log(f"  TG {method} failed ({r.status_code}), attempt {attempt + 1}")
        except RequestException as e:
            log(f"  TG {method} err [{attempt + 1}]: {e}")
        time.sleep(2)
    return None


def tg(method, **kwargs):
    r = _tg_request(method, "post", **kwargs)
    return r


def tg_get(method, params=None):
    r = _tg_request(method, "get", params=params)
    if r:
        return r.json()
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
        except Exception as e:
            log(f"  getMe err: {e}")
    if not linked_group:
        try:
            chat_info = tg("getChat", json={"chat_id": CHANNEL_ID})
            if chat_info:
                data = chat_info.json()
                linked_group = data.get("result", {}).get("linked_chat_id")
                if linked_group:
                    state["_linked_chat_id"] = linked_group
        except Exception as e:
            log(f"  getChat err: {e}")
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
        if linked_group and chat_id == linked_group and text and bot_id and from_id != bot_id:
            text_lower = text.lower()
            track_pats = [r" — ", r" – ", r" - ", r"–", r"—", r"youtube\.com", r"youtu\.be"]
            is_track = any(re.search(p, text) for p in track_pats) or \
                text_lower.startswith("трек ") or \
                text_lower.startswith("песня ") or \
                text_lower.startswith("музыка ")
            if is_track:
                tracks = state.setdefault("listener_tracks", [])
                tracks.append({
                    "text": text,
                    "from": msg.get("from", {}).get("first_name", "Подписчик"),
                    "time": time.time(),
                    "week": time.strftime("%Y-W%V"),
                })
                if len(tracks) > 100:
                    state["listener_tracks"] = tracks[-100:]
                log(f"  Listener tracks: {len(tracks)} this week, saved: {text[:60]}")
            elif len(text) > 30:
                comments = state.setdefault("weekly_comments", [])
                comments.append({
                    "text": text[:200],
                    "from": msg.get("from", {}).get("first_name", "Подписчик"),
                    "time": time.time(),
                })
                if len(comments) > 300:
                    state["weekly_comments"] = comments[-300:]
            tg("sendMessage", json={
                "chat_id": linked_group,
                "text": random.choice(REPLY_TEMPLATES),
                "reply_to_message_id": msg.get("message_id"),
            }, timeout=10)
        state["moderation_offset"] = upd_id + 1
    if result:
        save_state(state)
    return replies


def send_error(msg):
    try:
        tg("sendMessage", json={
            "chat_id": ADMIN_CHAT_ID,
            "text": f"\U0001F6A8 <b>Bot Error</b>\n\n{escape_html(msg[:500])}",
            "parse_mode": "HTML",
        }, timeout=8)
    except Exception as e:
        log(f"  send_error failed: {e}")


def send_preview(chat_id, preview_text, img_bytes=None, img_ext="jpg", img_mime="image/jpeg", timeout=15):
    mod_msg_id = None
    if img_bytes:
        try:
            r = tg("sendPhoto", data={
                "chat_id": chat_id, "caption": preview_text, "parse_mode": "HTML",
            }, files={"photo": (f"preview.{img_ext}", img_bytes, img_mime)}, timeout=timeout)
            if r:
                mod_msg_id = r.json()["result"]["message_id"]
        except Exception as e:
            log(f"  Preview img err: {e}")
    if not mod_msg_id:
        r = tg("sendMessage", json={
            "chat_id": chat_id, "text": preview_text, "parse_mode": "HTML",
        }, timeout=timeout)
        if r:
            mod_msg_id = r.json()["result"]["message_id"]
    return mod_msg_id


def is_hd(img_data):
    try:
        img = Image.open(io.BytesIO(img_data))
        w, h = img.size
        if max(w, h) >= 1280:
            return True
        if w * h >= 500000:
            return True
        log(f"  Image too small: {w}x{h}")
        return False
    except Exception as e:
        log(f"  is_hd err: {e}")
        return False


def detect_theme(title, desc):
    text = f"{title} {desc}".lower()
    for theme, words in THEME_WORDS.items():
        if any(w.lower() in text for w in words):
            return theme
    return "generic"


_EX_GAME_COMPANY = re.compile(
    r"^(?:Rockstar|Take[- ]Two|Capcom|Bungie|Valve|Activision|Ubisoft|Bethesda"
    r"|Sony|Microsoft|Nintendo|EA|Square\s+Enix|CD\s*Project|Kuro\s+Games"
    r"|Larian|Santa\s+Monica|Kojima|Netflix)\s+", flags=re.I
)
_EX_GAME_TRAIL = re.compile(
    r"(?:\s+(?:влияние|решение|развитие|изменение|начало|будущее"
    r"|работа|запуск|поддержка|проблема|ситуация|процесс"
    r"|подробности|детали|итоги|мнение|впечатление|причина|последствия"
    r"|анализ|исследование"
    r"|глава|главы|главу"
    r"|немецк\w+|российск\w+|японск\w+|китайск\w+|американск\w+"
    r"|блогер\w*|журналист\w*|инсайдер\w*|создател\w*|разработчик\w*"
    r"|геймер\w*|фанат\w*|пользовател\w*|покупател\w*"
    r"|автор\w*|ветеран\w*|дизайнер\w*|продюсер\w*|руководител\w*"
    r"|студи\w+|компани\w+|корпораци\w+|издател\w+"
    r"|презентаци\w+|конференци\w+|выставк\w+|мероприят\w+"
    r"|объяснил\w*|рассказал\w*|подтвердил\w*|опроверг\w*|показал\w*"
    r"|раскрыл\w*|анонсировал\w*|объявил\w*|заявил\w*|отметил\w*"
    r"|появится|появился|выйдет|вышла|вышел|получил|доступна"
    r"|отложен|перенесен\w*|назван\w*|завершил\w*|превысил\w*|подписал\w*"
    r"|требуют|петици\w+|утек\w*|слит\w*|взлом\w*"
    r"|анонс\w*|перенос\w*|слух\w*|утечк\w+|слив\w*"
    r"|продаж\w*|тираж\w*|рекорд\w*|статистик\w*"
    r"|нов\w+|второй|первый|очередной|последний|главный|новейший"
    r"|бесплатно|скидк\w+|раздач\w+|акци\w+|бандл\w*"
    r"|трейлер\w*|геймплей\w*|тизер\w*|ролик\w*|видео"
    r"|график\w*|дата|срок\w*|окно|выход|релиз"
    r"|консоль\w*|приставк\w*|платформ\w*"
    r"|пк|pc|steam|ps\d+|xbox|switch|playstation|nintendo|мод\w*))",
    flags=re.I,
)


def extract_game(title):
    for sep in (" — ", " – ", " - ", " | ", "; "):
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
        "microsoft", "sony", "nintendo", "rockstar", "take-two", "take two",
        "playstation", "xbox", "консоль", "приставк",
        "анонс", "анонса", "анонсу", "анонсом", "анонсе", "анонсы", "анонсов",
        "перенос", "переноса", "переносом", "слух", "слуха", "слухи", "слухов",
        "утечка", "утечки", "утечку", "утечек", "слив", "слива", "сливы",
        "трейлер", "трейлера", "трейлеры", "тизер", "тизера",
        "влияние", "состояние", "решение", "развитие", "изменение", "событие",
        "подробности", "детали", "итоги", "результаты", "мнение", "впечатление",
        "причина", "последствия", "проблема", "ситуация", "будущее", "прошлое",
        "настоящее", "начало", "конец", "процесс", "работа", "запуск",
        "поддержка", "разработка", "производство", "исследование", "анализ",
        "вопрос", "ответ", "факт", "данные", "информация", "новость", "статья",
        "репортаж", "интервью", "колонка", "блог", "пост", "запись",
        "глава", "главы", "главу", "главе", "главой",
        "блогер", "блогеры", "блогера", "блогеров",
        "журналист", "журналисты", "журналиста", "журналистов",
        "инсайдер", "инсайдеры", "инсайдера", "инсайдеров",
        "создатели", "создателя", "создателей",
        "разработчик", "разработчица", "разработчика", "разработчиков",
        "геймер", "геймера", "геймеров",
        "фанат", "фаната", "фанатов", "фанатка", "фанатки",
        "покупатель", "покупатели", "покупателя",
        "авторы", "автора", "авторов",
        "ветеран", "ветераны", "ветерана",
        "дизайнер", "дизайнеры", "дизайнера", "дизайнеров",
        "продюсер", "продюсеры", "продюсера",
        "руководитель", "руководители",
        "немецкие", "немецкий", "немецкая", "немецких", "немецкого", "немецкой",
        "российский", "российская", "российские", "российских", "российского",
        "японский", "японская", "японские", "японских", "японского",
        "американский", "американская", "американские", "американских",
        "китайский", "китайская", "китайские", "китайских",
        "пользователь", "пользователи", "пользователей",
        "компания", "компании", "компанию", "компанией",
        "корпорация", "корпорации", "корпорацию",
        "издатель", "издатели", "издателя", "издательство",
        "студии", "студию", "студией", "студий",
        "конференция", "конференции", "конференцию",
        "презентация", "презентации", "презентацию",
        "выставка", "выставки", "выставку",
        "мероприятие", "мероприятия", "мероприятий",
        "объяснила", "объяснили", "объяснит",
        "рассказала", "рассказали", "расскажут",
        "подтвердила", "подтвердили",
        "опровергла", "опровергли",
        "показала", "показали", "покажут",
        "раскрыла", "раскрыли", "раскроет",
        "анонсировала", "анонсировали",
        "объявила", "объявили", "объявят",
        "заявила", "заявили", "заявит",
        "отметила", "отметили",
        "выйдет", "выйдут", "вышло",
        "получила", "получили", "получат",
        "доступно", "доступны", "доступен",
        "отложили", "отложен",
        "перенесли", "перенесена", "перенесено",
        "назвала", "назвали",
        "завершила", "завершили",
        "превысила", "превысили",
        "подписала", "подписали",
        "требуется", "требовали",
        "петиции", "петицию", "петиций",
        "утекли", "утекло", "утекла",
        "слили", "слито",
        "взломали", "взломан",
        "продажа", "продажу", "продаж", "продажи",
        "тиражи", "тиража",
        "рекорд", "рекорда", "рекорды", "рекордов",
        "статистика", "статистики", "статистику",
        "вторая", "второй", "второе", "вторые",
        "первая", "первой", "первое", "первые",
        "очередная", "очередной", "очередное", "очередные",
        "последняя", "последней", "последнее", "последние",
        "главная", "главной", "главное", "главные",
        "новейшая", "новейшей", "новейшее", "новейшие",
        "бесплатная", "бесплатной", "бесплатное", "бесплатные",
        "скидка", "скидки", "скидку", "скидок",
        "раздача", "раздачи", "раздачу",
        "акция", "акции", "акцию", "акций",
        "бандл", "бандла", "бандлы",
        "ролик", "ролика", "ролики", "роликов",
        "видео", "видеоролик",
        "графика", "графики", "графику",
        "сроки", "сроков", "срока",
        "окно", "окна",
        "моды", "модов", "мода", "моддинг",
        "пк", "pc", "steam", "steamdeck", "steam deck",
        "ps5", "ps4", "ps3", "ps2", "ps1",
        "psvita",
        "xbox", "xbox360", "xboxone", "xbox series", "xboxs",
        "switch", "switch2", "switch 2",
        "playstation", "playstation4", "playstation5",
        "nintendo",
        "wii", "wiiu",
        "epic", "egs", "gog",
        "в", "и", "на", "с", "со", "из", "по", "за", "от", "до",
        "у", "о", "об", "во", "при", "про", "для", "без", "через",
        "ещё", "уже", "все", "как", "так", "что", "кто", "где",
        "это", "его", "её", "их", "нам", "вам", "когда", "пока",
        "после", "снова", "опять", "теперь", "после", "также",
        "будет", "будут", "был", "была", "было", "были",
        "есть", "нет", "ли", "не", "ни", "или", "то",
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
    game = _EX_GAME_COMPANY.sub("", game).strip()
    platform_names = {"PS5", "PS4", "PS3", "Xbox", "PC", "Nintendo", "Switch", "Steam", "PlayStation",
                      "Series", "One", "360", "Wii", "WiiU", "PSP", "PSVita", "EGS", "GOG"}
    parts = game.split()
    game = " ".join(p for p in parts if p not in platform_names).strip()
    game = re.sub(r"\bPlayStation\s*\d+\b", "", game, flags=re.I).strip()
    game = re.sub(r"\bNintendo\s+\w+\b", "", game, flags=re.I).strip()
    game = re.sub(r"\bXbox\s+(?:Series|One|360|)\b", "", game, flags=re.I).strip()
    game = re.sub(r"\bSwitch\s*2\b", "", game, flags=re.I).strip()
    game = re.sub(r"\bSteam\s*Deck\b", "", game, flags=re.I).strip()
    # Strip trailing standalone numbers that aren't part of a known game name pattern
    game = re.sub(r"\s+\d+(?:\.\d+)?$", "", game).strip()
    # Strip trailing junk matched by _EX_GAME_TRAIL
    game = _EX_GAME_TRAIL.sub("", game).strip()
    # Strip leading/trailing standalone single Cyrillic words (like "Кратоса", "Фэй")
    game = re.sub(r"\s+[А-ЯЁ][а-яё]+$", "", game).strip()
    game = re.sub(r"\s+", " ", game).strip()
    if re.match(r"^[А-ЯЁ][а-яё]+\s*$", game):
        game = title[:40] if title else game
    if not game:
        game = words[0] if words else ""
    if not game:
        game = title[:30] if title else ""
    if 3 < len(game) <= 50:
        return game
    if len(game) > 50:
        short = game[:game.rfind(" ", 0, 47)]
        return short + "..." if len(short) > 3 else game[:45] + "..."
    return game[:40] if game else title[:30]


def extract_numbers(text):
    found = []
    seen_raw = set()
    # Priority 1: numbers with explicit unit words (млн, тыс, копий, etc.)
    for m in re.finditer(
        r"(\d[\d\s]*(?:[.,]\d+)?)\s*(млн|тыс\.?|тысяч|миллион|миллиард|%|копий|копия|экземпляр|экз\.?)",
        text, flags=re.I,
    ):
        num = m.group(1).replace(" ", "").replace(",", ".")
        unit = m.group(2).lower().strip(".")
        key = f"{num} {unit}"
        if key not in seen_raw:
            seen_raw.add(key)
            found.append(f"{num} {unit}".strip())
    # Priority 2: standalone moderate numbers (skip years, skip <10 to avoid game version noise)
    if not found:
        for m in re.finditer(r"(\d{2,})", text):
            num_s = m.group(1)
            try:
                val = int(num_s)
            except ValueError:
                continue
            if 1000 < val < 2100:
                continue
            if val < 10:
                continue
            if num_s not in seen_raw:
                seen_raw.add(num_s)
                found.append(num_s)
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
        "sales": [
            f"Продажи {kw} бьют рекорды!", f"Народ раскупает {kw}", f"{kw} — успех!",
            f"Ого, {kw} продаётся отлично!", f"{kw} — кассовый успех.",
            f"А вы уже купили {kw} или ждёте скидку?",
            f"Коммерческий успех налицо.", f"Расходится как горячие пирожки.",
        ],
        "delay": [
            f"Релиз {kw} отложили. Ну такое.", f"{kw} задерживается. Снова.",
            f"Перенос {kw}. Ну вот опять.", f"{kw} перенесли. Классика.",
            f"Ждали {kw}? Потерпите ещё.", f"Не судьба {kw} пока.",
        ],
        "sequel": [
            f"Продолжение {kw} на подходе!", f"В мир {kw} вернёмся скоро.",
            f"Сиквел {kw} — будет жарко.", f"В {kw} поиграем снова.",
            f"Старые герои {kw}, новая история.",
        ],
        "console": [
            f"{kw} выходит на консолях!", f"Консольщики, {kw} ваша.",
            f"{kw} — теперь и на диване.", f"{kw} и на консолях тоже.",
            f"Поиграть в {kw} можно будет и на диване.",
        ],
        "drama": [
            f"Скандал вокруг {kw}!", f"Драма: {kw} снова в центре.",
            f"Шум вокруг {kw} нарастает.", f"Ой, {kw}... всё.",
            f"Скандалы, интриги, {kw}.",
        ],
        "rumor": [
            f"Слух: {kw}...", f"Говорят, {kw} готовит сюрприз.",
            f"Инсайд: {kw}.", f"Слухи вокруг {kw} сгущаются.",
            f"{kw} — соль недели.",
        ],
        "announce": [
            f"Анонс {kw}! Дождались.", f"{kw} официально анонсирована!",
            f"Ждали? {kw} в разработке.", f"Свершилось! {kw} анонсирована.",
            f"Ждали — получите. {kw}.",
        ],
        "generic": [
            f"Новость дня.", f"Вот это поворот.", f"Держите в курсе.",
            f"Вот такое дело.", f"Новости игропрома.", f"Будет интересно.",
            f"На заметку.", f"Понеслась душа в рай.", f"Ну, погнали!",
            f"Игровая индустрия не спит.", f"Интересный поворот.",
            f"А вы что думаете?", f"Тренд или случайность?", f"Ждём-с.",
            f"В мире игр ничего не меняется.", f"Без комментариев.",
        ],
    }
    return random.choice(ctx.get(theme, ctx["generic"]))


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


_BODIES = {
    "sales":    lambda s, title, game, numbers, platforms: f"Продажи достигли отметки в {numbers[0] if numbers else 'внушительное количество'} копий. {s}",
    "delay":    lambda s, title, game, numbers, platforms: f"Релиз перенесён. {s}",
    "sequel":   lambda s, title, game, numbers, platforms: f"Продолжение истории. {s}",
    "console":  lambda s, title, game, numbers, platforms: f"{title}. {s}" if s else title,
    "drama":    lambda s, title, game, numbers, platforms: f"Скандал разгорается. {s}",
    "generic":  lambda s, title, game, numbers, platforms: f"{title}. {s}" if s else title,
    "rumor":    lambda s, title, game, numbers, platforms: f"Слухи ходят разные. {s}",
    "announce": lambda s, title, game, numbers, platforms: f"Официально подтверждено. {s}",
}


def _build_template(theme, title, desc, game, numbers, platforms, genre, link):
    s = shorten(desc, MAX_DESC_LEN)
    commentary = smart_comment(theme, game, title)
    builder = _BODIES.get(theme, _BODIES["generic"])
    body = builder(s, title, game, numbers, platforms)
    return [commentary, _SEP * 7, embed_link(body, link)]


TEMPLATES = {
    "sales":    lambda t, d, g, n, p, ge, l: _build_template("sales",    t, d, g, n, p, ge, l),
    "delay":    lambda t, d, g, n, p, ge, l: _build_template("delay",    t, d, g, n, p, ge, l),
    "sequel":   lambda t, d, g, n, p, ge, l: _build_template("sequel",   t, d, g, n, p, ge, l),
    "console":  lambda t, d, g, n, p, ge, l: _build_template("console",  t, d, g, n, p, ge, l),
    "drama":    lambda t, d, g, n, p, ge, l: _build_template("drama",    t, d, g, n, p, ge, l),
    "rumor":    lambda t, d, g, n, p, ge, l: _build_template("rumor",    t, d, g, n, p, ge, l),
    "announce": lambda t, d, g, n, p, ge, l: _build_template("announce", t, d, g, n, p, ge, l),
    "generic":  lambda t, d, g, n, p, ge, l: _build_template("generic",  t, d, g, n, p, ge, l),
}


def send_audio_file(path, title, performer=None, chat_id=None):
    if not os.path.exists(path):
        log(f"  Audio file not found: {path}")
        return None
    ext = os.path.splitext(path)[1] or ".webm"
    mime_map = {
        ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".mp4": "audio/mp4",
        ".webm": "audio/webm", ".opus": "audio/opus",
        ".ogg": "audio/ogg", ".wav": "audio/wav",
    }
    mime = mime_map.get(ext.lower(), "audio/mpeg")
    payload = {"chat_id": chat_id or CHANNEL_ID, "title": title[:60]}
    if performer:
        payload["performer"] = performer
    for attempt in range(2):
        try:
            with open(path, "rb") as f:
                r = tg("sendAudio", data=payload,
                       files={"audio": (f"audio{ext}", f, mime)}, timeout=45)
            if r:
                try:
                    os.remove(path)
                except Exception as e:
                    log(f"  Audio file cleanup err: {e}")
                return r
            log(f"  Audio send attempt {attempt+1} failed, retrying...")
            time.sleep(3)
        except Exception as e:
            log(f"  Audio send attempt {attempt+1} error: {e}")
            time.sleep(3)
    log(f"  Audio send failed after retries: {title}")
    return None
