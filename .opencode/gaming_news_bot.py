import os
import sys
import json
import feedparser
import requests
import time
import re
import random
import hashlib
from html import unescape
from datetime import datetime, timezone
from PIL import Image
import io
from deep_translator import GoogleTranslator

_TRANSLATOR = GoogleTranslator(source='en', target='ru')
_TRANSLATE_CACHE = {}

BOT_TOKEN = "8879790921:AAE9hwgmrpSoa5wr7NCXA6H9CBDp6JgC3s0"
TEST_MODE = False
CHANNEL_ID = "@SPVRTVN" if TEST_MODE else "@NektarinGaming"
ADMIN_CHAT = "@SPVRTVN"
ADMIN_CHAT_ID = 710307297
MAX_POSTS = 2
POST_DELAY = 18000  # секунд между постами (5 часов)
POST_DELAY_JITTER = 1800  # +-30 мин рандома
PRIORITY_KEYWORDS = [
    "gta 6", "gta vi", "grand theft auto",
    "elden ring", "witcher 4", "witcher",
    "half-life 3", "half life 3", "hl3",
    "the last of us", "god of war",
    "cyberpunk", "red dead",
    "nintendo switch 2", "switch 2",
    "playstation 6", "ps6",
    "xbox next", "xbox series",
    "respawn", "valve",
    "minecraft 2", "skyrim",
    "fallout 5", "tes 6", "elder scrolls",
    "mass effect", "dragon age",
    "silksong", "hollow knight",
    "секрет", "слух", "утечк", "слив",
]
STATE_FILE = os.path.expanduser("~/.opencode/bot_state.json")
LOG_FILE = os.path.expanduser("~/.opencode/bot.log")
SILENT_HOURS = range(0, 10)  # не постить с 00:00 до 09:59

TWITCH_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"

RSS_FEEDS = [
    ("https://www.igromania.ru/rss/news.xml", "igromania", 10),
    ("https://www.goha.ru/rss/news", "goha", 5),
    ("https://www.goha.ru/rss/videogames", "goha_videogames", 5),
    ("https://www.goha.ru/rss/industry", "goha_industry", 3),
    ("https://www.playground.ru/rss/news.xml", "playground", 10),
    ("https://stopgame.ru/news/rss.xml", "stopgame", 7),
    ("https://kanobu.ru/rss/main.rss", "kanobu", 5),
    ("https://vgtimes.ru/rss/news/", "vgtimes", 5),
    ("https://shazoo.ru/rss.xml", "shazoo", 5),
]

ANIME_FEEDS = [
    ("https://www.animenewsnetwork.com/news/rss.xml", "animenews", 5),
    ("https://shazoo.ru/rss.xml", "shazoo_anime", 3),
]

ROCK_FEEDS = [
    ("https://www.blabbermouth.net/feed/", "blabbermouth", 15),
    ("https://loudwire.com/feed/", "loudwire", 15),
    ("https://metalinjection.net/feed", "metalinjection", 15),
    ("https://rocknloadmag.com/feed/", "rocknload", 10),
]

ROCK_ARTISTS = [
    "slipknot", "green day", "hollywood undead", "korn",
    "disturbed", "linkin park", "system of a down", "three days grace",
    "breaking benjamin", "shinedown", "papa roach", "evanescence",
    "bring me the horizon", "avenged sevenfold", "metallica",
    "rammstein", "limp bizkit", "mudvayne", "seether",
    "stone sour", "theory of a deadman", "godsmack",
    "five finger death punch", "i prevail", "bad omens",
    "motionless in white", "ice nine kills", "architects",
    "the amity affliction", "memphis may fire", "asking alexandria",
]

ROCK_TRACKS = {
    "architects": [
        ("Animals", "Architects Animals"),
        ("Black Lungs", "Architects Black Lungs"),
        ("Gravedigger", "Architects Gravedigger"),
        ("Doomsday", "Architects Doomsday"),
        ("These Colours Don't Run", "Architects These Colours Dont Run"),
    ],
    "asking alexandria": [
        ("The Final Episode", "Asking Alexandria The Final Episode"),
        ("Moving On", "Asking Alexandria Moving On"),
        ("Alone in a Room", "Asking Alexandria Alone in a Room"),
        ("Break Down the Walls", "Asking Alexandria Break Down the Walls"),
        ("A Prophecy", "Asking Alexandria A Prophecy"),
    ],
    "avenged sevenfold": [
        ("Afterlife", "Avenged Sevenfold Afterlife"),
        ("Hail to the King", "Avenged Sevenfold Hail to the King"),
        ("Bat Country", "Avenged Sevenfold Bat Country"),
        ("Nightmare", "Avenged Sevenfold Nightmare"),
        ("Dear God", "Avenged Sevenfold Dear God"),
    ],
    "bad omens": [
        ("The Death of Peace of Mind", "Bad Omens The Death of Peace of Mind"),
        ("Just Pretend", "Bad Omens Just Pretend"),
        ("Artificial Suicide", "Bad Omens Artificial Suicide"),
        ("Like a Villain", "Bad Omens Like a Villain"),
        ("Never Know", "Bad Omens Never Know"),
    ],
    "breaking benjamin": [
        ("The Diary of Jane", "Breaking Benjamin The Diary of Jane"),
        ("So Cold", "Breaking Benjamin So Cold"),
        ("Breath", "Breaking Benjamin Breath"),
        ("I Will Not Bow", "Breaking Benjamin I Will Not Bow"),
        ("Polyamorous", "Breaking Benjamin Polyamorous"),
    ],
    "bring me the horizon": [
        ("Throne", "Bring Me the Horizon Throne"),
        ("Drown", "Bring Me the Horizon Drown"),
        ("Can You Feel My Heart", "Bring Me the Horizon Can You Feel My Heart"),
        ("Sleepwalking", "Bring Me the Horizon Sleepwalking"),
        ("Shadow Moses", "Bring Me the Horizon Shadow Moses"),
    ],
    "disturbed": [
        ("Down with the Sickness", "Disturbed Down with the Sickness"),
        ("Stricken", "Disturbed Stricken"),
        ("Indestructible", "Disturbed Indestructible"),
        ("The Sound of Silence", "Disturbed The Sound of Silence"),
        ("Inside the Fire", "Disturbed Inside the Fire"),
    ],
    "evanescence": [
        ("Bring Me to Life", "Evanescence Bring Me to Life"),
        ("My Immortal", "Evanescence My Immortal"),
        ("Going Under", "Evanescence Going Under"),
        ("Lithium", "Evanescence Lithium"),
        ("Call Me When You're Sober", "Evanescence Call Me When Youre Sober"),
    ],
    "five finger death punch": [
        ("Wrong Side of Heaven", "Five Finger Death Punch Wrong Side of Heaven"),
        ("Bad Company", "Five Finger Death Punch Bad Company"),
        ("The Bleeding", "Five Finger Death Punch The Bleeding"),
        ("Coming Down", "Five Finger Death Punch Coming Down"),
        ("Jekyll and Hyde", "Five Finger Death Punch Jekyll and Hyde"),
    ],
    "godsmack": [
        ("I Stand Alone", "Godsmack I Stand Alone"),
        ("Awake", "Godsmack Awake"),
        ("Voodoo", "Godsmack Voodoo"),
        ("Surrender", "Godsmack Surrender"),
        ("Bulletproof", "Godsmack Bulletproof"),
    ],
    "green day": [
        ("Boulevard of Broken Dreams", "Green Day Boulevard of Broken Dreams"),
        ("American Idiot", "Green Day American Idiot"),
        ("Wake Me Up When September Ends", "Green Day Wake Me Up When September Ends"),
        ("21 Guns", "Green Day 21 Guns"),
        ("Holiday", "Green Day Holiday"),
    ],
    "hollywood undead": [
        ("Undead", "Hollywood Undead Undead"),
        ("Everywhere I Go", "Hollywood Undead Everywhere I Go"),
        ("Hear Me Now", "Hollywood Undead Hear Me Now"),
        ("Comin' in Hot", "Hollywood Undead Comin in Hot"),
        ("Bullet", "Hollywood Undead Bullet"),
    ],
    "i prevail": [
        ("Hurricane", "I Prevail Hurricane"),
        ("Breaking Down", "I Prevail Breaking Down"),
        ("Every Time You Leave", "I Prevail Every Time You Leave"),
        ("Gasoline", "I Prevail Gasoline"),
        ("Bow Down", "I Prevail Bow Down"),
    ],
    "ice nine kills": [
        ("The Shower Scene", "Ice Nine Kills The Shower Scene"),
        ("The American Nightmare", "Ice Nine Kills The American Nightmare"),
        ("Your Numbers Up", "Ice Nine Kills Your Numbers Up"),
        ("Welcome to Horrorwood", "Ice Nine Kills Welcome to Horrorwood"),
        ("Stabbing in the Dark", "Ice Nine Kills Stabbing in the Dark"),
    ],
    "korn": [
        ("Freak on a Leash", "Korn Freak on a Leash"),
        ("Falling Away from Me", "Korn Falling Away from Me"),
        ("Blind", "Korn Blind"),
        ("Got the Life", "Korn Got the Life"),
        ("Here to Stay", "Korn Here to Stay"),
    ],
    "limp bizkit": [
        ("Nookie", "Limp Bizkit Nookie"),
        ("Take a Look Around", "Limp Bizkit Take a Look Around"),
        ("My Way", "Limp Bizkit My Way"),
        ("Chocolate Starfish", "Limp Bizkit Chocolate Starfish"),
        ("Behind Blue Eyes", "Limp Bizkit Behind Blue Eyes"),
    ],
    "linkin park": [
        ("In the End", "Linkin Park In the End"),
        ("Numb", "Linkin Park Numb"),
        ("Breaking the Habit", "Linkin Park Breaking the Habit"),
        ("What I've Done", "Linkin Park What Ive Done"),
        ("Faint", "Linkin Park Faint"),
    ],
    "memphis may fire": [
        ("The Sinner", "Memphis May Fire The Sinner"),
        ("Heavy Is the Weight", "Memphis May Fire Heavy Is the Weight"),
        ("Blood & Water", "Memphis May Fire Blood and Water"),
        ("Make It Out Alive", "Memphis May Fire Make It Out Alive"),
        ("Vices", "Memphis May Fire Vices"),
    ],
    "metallica": [
        ("Enter Sandman", "Metallica Enter Sandman"),
        ("Nothing Else Matters", "Metallica Nothing Else Matters"),
        ("Master of Puppets", "Metallica Master of Puppets"),
        ("One", "Metallica One"),
        ("The Unforgiven", "Metallica The Unforgiven"),
    ],
    "motionless in white": [
        ("Voices", "Motionless in White Voices"),
        ("Another Life", "Motionless in White Another Life"),
        ("Creatures X", "Motionless in White Creatures"),
        ("Cyberhex", "Motionless in White Cyberhex"),
        ("Masterpiece", "Motionless in White Masterpiece"),
    ],
    "mudvayne": [
        ("Dig", "Mudvayne Dig"),
        ("Happy?", "Mudvayne Happy"),
        ("Not Falling", "Mudvayne Not Falling"),
        ("World So Cold", "Mudvayne World So Cold"),
        ("Determined", "Mudvayne Determined"),
    ],
    "papa roach": [
        ("Last Resort", "Papa Roach Last Resort"),
        ("Scars", "Papa Roach Scars"),
        ("Help", "Papa Roach Help"),
        ("Between Angels and Insects", "Papa Roach Between Angels and Insects"),
        ("Getting Away with Murder", "Papa Roach Getting Away with Murder"),
    ],
    "rammstein": [
        ("Du Hast", "Rammstein Du Hast"),
        ("Sonne", "Rammstein Sonne"),
        ("Ich Will", "Rammstein Ich Will"),
        ("Feuer Frei!", "Rammstein Feuer Frei"),
        ("Mutter", "Rammstein Mutter"),
    ],
    "seether": [
        ("Broken", "Seether Broken"),
        ("Fake It", "Seether Fake It"),
        ("Rise Above This", "Seether Rise Above This"),
        ("Country Song", "Seether Country Song"),
        ("Remedy", "Seether Remedy"),
    ],
    "shinedown": [
        ("Second Chance", "Shinedown Second Chance"),
        ("Sound of Madness", "Shinedown Sound of Madness"),
        ("45", "Shinedown 45"),
        ("Monsters", "Shinedown Monsters"),
        ("Bully", "Shinedown Bully"),
    ],
    "slipknot": [
        ("Duality", "Slipknot Duality"),
        ("Psychosocial", "Slipknot Psychosocial"),
        ("Before I Forget", "Slipknot Before I Forget"),
        ("Snuff", "Slipknot Snuff"),
        ("The Devil in I", "Slipknot The Devil in I"),
    ],
    "stone sour": [
        ("Through Glass", "Stone Sour Through Glass"),
        ("Absolute Zero", "Stone Sour Absolute Zero"),
        ("Say You'll Haunt Me", "Stone Sour Say Youll Haunt Me"),
        ("Bother", "Stone Sour Bother"),
        ("30/30-150", "Stone Sour 30 30 150"),
    ],
    "system of a down": [
        ("Chop Suey!", "System of a Down Chop Suey"),
        ("Toxicity", "System of a Down Toxicity"),
        ("Aerials", "System of a Down Aerials"),
        ("B.Y.O.B.", "System of a Down BYOB"),
        ("Sugar", "System of a Down Sugar"),
    ],
    "the amity affliction": [
        ("Pittsburgh", "The Amity Affliction Pittsburgh"),
        ("Drag the Lake", "The Amity Affliction Drag the Lake"),
        ("Soak Me in Bleach", "The Amity Affliction Soak Me in Bleach"),
        ("All My Friends Are Dead", "The Amity Affliction All My Friends Are Dead"),
        ("It's Hell Down Here", "The Amity Affliction Its Hell Down Here"),
    ],
    "theory of a deadman": [
        ("Bad Girlfriend", "Theory of a Deadman Bad Girlfriend"),
        ("Rx (Medicate)", "Theory of a Deadman Rx Medicate"),
        ("Nothing Could Come Between Us", "Theory of a Deadman Nothing Could Come Between Us"),
        ("Lowlife", "Theory of a Deadman Lowlife"),
        ("Not Meant to Be", "Theory of a Deadman Not Meant to Be"),
    ],
    "three days grace": [
        ("I Hate Everything About You", "Three Days Grace I Hate Everything About You"),
        ("Animal I Have Become", "Three Days Grace Animal I Have Become"),
        ("Riot", "Three Days Grace Riot"),
        ("Pain", "Three Days Grace Pain"),
        ("Never Too Late", "Three Days Grace Never Too Late"),
    ],
}

WIKI_UA = "GamingNewsBot/1.0 (https://t.me/NektarinGaming)"
PINTEREST_SESSION = None

THEME_WORDS = {
    "sales": ["продаж", "тираж", "миллион", "копий", "рекорд", "миллиард", "выручк", "прибыл", "заработ"],
    "delay": ["отложен", "перенесен", "задержк", "отсрочк", "не выйдет", "перенос", "отмена"],
    "console": ["эксклюзив", "консоль", "PlayStation", "PS5", "Xbox", "Nintendo", "Switch"],
    "sequel": ["сиквел", "продолжение", "часть", "новая", "триквел", "ремейк"],
    "drama": ["скандал", "критик", "гнев", "недовольн", "петицию", "требуют", "кризис", "увольнени"],
    "rumor": ["слух", "утечк", "слив", "инсайд", "инсайдер", "слили", "подтвердил", "по слухам", "источник"],
    "announce": ["анонс", "анонсирова", "объявил", "представил", "раскрыл", "показал"],
}

GENRE_TAGS = {
    "шутер", "хоррор", "рогалик", "симулятор", "стратеги", "rpg", "экшн",
    "файтинг", "гонк", "платформер", "головоломк", "песочниц", "выживани",
}

PLATFORMS = ["PS5", "PS4", "Xbox Series", "Xbox", "Switch", "PC", "Steam"]

TG_API = "https://api.telegram.org/bot"
MODERATION_TTL = 86400  # 24h before dropping unapproved post
MODERATION_INTERVAL = 3600  # 1h between sending new previews
_PROXY_FILE = os.path.join(os.path.dirname(STATE_FILE), "bot_proxy.txt")
TG_PROXY = os.environ.get("TG_PROXY", "")
if not TG_PROXY and os.path.exists(_PROXY_FILE):
    with open(_PROXY_FILE, "r", encoding="utf-8") as _f:
        TG_PROXY = _f.read().strip()

MAX_CAPTION_LEN = 900
MAX_DESC_LEN = 250
SHORTEN_FALLBACK = 200

WATCHED_GAMES = [
    "elden ring", "witcher", "gta", "cyberpunk",
    "red dead", "god of war", "silksong",
    "half-life", "mass effect", "dragon age",
    "disco elysium", "baldurs gate", "baldur's gate",
    "starfield", "stalker", "fallout",
]

CHANNEL_SIGNATURE = "\n— @NektarinGaming"

NIKITA_PICKS = [
    {"title": "Elden Ring", "desc": "Шедевр, который нужно пройти каждому. Открытый мир, сложные боссы и атмосфера, от которой мурашки.", "tag": "game"},
    {"title": "Cyberpunk 2077", "desc": "После всех патчей — это совсем другая игра. Атмосферный киберпанк с отличным сюжетом.", "tag": "game"},
    {"title": "God of War Ragnarök", "desc": "История Кратоса и Атрея — лучший эксклюзив современности.", "tag": "game"},
    {"title": "Ванпанчмен", "desc": "Смешная и динамичная пародия на жанр супергероев. Рекомендую тем, кто хочет поржать и расслабиться.", "tag": "anime"},
    {"title": "Магическая битва", "desc": "Best анимация последних лет, эпичные битвы и харизматичные персонажи.", "tag": "anime"},
    {"title": "Клинок, рассекающий демонов", "desc": "Красивейшее аниме с невероятной рисовкой. История про семью и месть.", "tag": "anime"},
    {"title": "Атака титанов", "desc": "Легендарное аниме, которое обязательно к просмотру. Сюжетные повороты разрывают шаблон.", "tag": "anime"},
    {"title": "The Witcher 3", "desc": "Игра, в которую можно уйти с головой на сотни часов. Лучшее фэнтези в гейминге.", "tag": "game"},
    {"title": "Disco Elysium", "desc": "Если хочется чего-то необычного — этот детектив с RPG-элементами сносит крышу.", "tag": "game"},
    {"title": "Baldur's Gate 3", "desc": "Лучшая RPG последних лет. Можно потерять сон на недели, честно предупреждаю.", "tag": "game"},
]

NON_GAMING_TITLE_WORDS = {
    "сериал", "фильм", "актёр", "актер", "кино", "эпизод",
    "netflix", "сезон", "сериала", "фильма", "кинотеатр",
    "copilot", "futurama", "футурам",
    "забастовк", "tsmc",
}

GAMING_SIGNAL_WORDS = {
    "игра", "игр", "гейминг", "геймер", "игровой", "игру",
    "steam", "playstation", "xbox", "nintendo", "switch",
    "консоль", "приставк",
    "шутер", "хоррор", "rpg", "экшн", "стратеги", "гонк",
    "симулятор", "файтинг", "платформер",
    "dlc", "патч", "обновлени", "релиз", "трейлер", "геймплей",
    "киберспорт", "турнир", "пк", "pc",
    "графика", "производительн",
    "предзаказ", "скидк", "раздач",
}

GAME_DEDUP_HOURS = 48
TITLE_DEDUP_HOURS = 48
TITLE_DEDUP_MIN_WORDS = 3
TITLE_SIMILARITY_THRESHOLD = 0.65


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


def smart_comment(theme, game, title):
    kw = escape_md(game) if game else ""
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
    return random.choice(ctx.get(theme, COMMENTARIES["generic"]))


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


def translate_en_ru(text):
    if not text:
        return text
    key = text[:200]
    if key in _TRANSLATE_CACHE:
        return _TRANSLATE_CACHE[key]
    try:
        result = _TRANSLATOR.translate(text)
        _TRANSLATE_CACHE[key] = result
        return result
    except Exception as e:
        print(f"  Translation error: {e}")
        return text


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


def send_error(msg):
    try:
        tg("sendMessage", json={
            "chat_id": ADMIN_CHAT,
            "text": f"\U0001F6A8 **Bot Error**\n\n{msg[:500]}",
            "parse_mode": "Markdown",
        }, timeout=8)
    except Exception:
        pass


def escape_md(text):
    text = str(text)
    text = text.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[").replace("]", "\\]")
    return text


def tg(method, **kwargs):
    try:
        timeout = kwargs.pop("timeout", 10)
        proxies = {"https": TG_PROXY} if TG_PROXY else None
        r = requests.post(f"{TG_API}{BOT_TOKEN}/{method}", timeout=timeout, proxies=proxies, **kwargs)
        if r.status_code == 200:
            return r
        print(f"  TG {method} failed ({r.status_code}): {r.text[:80]}")
    except Exception as e:
        print(f"  TG {method} err: {e}")
    return None


def tg_get(method, params=None):
    try:
        proxies = {"https": TG_PROXY} if TG_PROXY else None
        r = requests.get(f"{TG_API}{BOT_TOKEN}/{method}", params=params, timeout=10, proxies=proxies)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"  TG GET {method} err: {e}")
    return None


def check_user_reply(state, reply_to_msg_id):
    offset = state.get("moderation_offset", 0)
    result = tg_get("getUpdates", {"offset": offset, "timeout": 0})
    if not result:
        return None
    for update in result.get("result", []):
        upd_id = update["update_id"]
        msg = update.get("message", {})
        if msg.get("chat", {}).get("id") != ADMIN_CHAT_ID:
            state["moderation_offset"] = upd_id + 1
            continue
        reply = msg.get("reply_to_message", {})
        if reply.get("message_id") == reply_to_msg_id:
            state["moderation_offset"] = upd_id + 1
            return msg.get("text", "").strip() or None
        state["moderation_offset"] = upd_id + 1
    return None


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"ids": {}}

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def clean(text):
    text = unescape(text or "")
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def is_hot(item):
    text = (item["title"] + " " + item.get("desc", "")).lower()
    for kw in PRIORITY_KEYWORDS:
        if kw in text:
            return True
    return False

BOILERPLATE = [
    r"Читать далее.*$", r"Читать дальше.*$", r"Читать полностью.*$",
    r"Подробнее.*$", r"Подробно.*$",
    r"Источник:.*$", r"Ссылка на источник.*$",
    r"Смотрите также.*$",
]

YOUTUBE_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})"
)

TRAILER_KEYWORDS = ["трейлер", "тизер", "gameplay", "trailer", "teaser", "геймплей"]

def extract_youtube(raw_html):
    m = YOUTUBE_RE.search(raw_html or "")
    if m:
        return f"https://www.youtube.com/watch?v={m.group(1)}"
    return None

def is_trailer(title):
    t = title.lower()
    return any(kw in t for kw in TRAILER_KEYWORDS)

def clean_desc(text):
    text = clean(text)
    for pat in BOILERPLATE:
        text = re.sub(pat, "", text, flags=re.I | re.M)
    return text.strip().strip(",").strip()[:300]


def fetch_news():
    items = []
    seen_hashes = set()
    for url, source, limit in RSS_FEEDS:
        print(f"Loading: {url}")
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:limit]:
                raw_desc = entry.get("description", "") or ""
                title = clean(entry.get("title", ""))
                youtube_url = extract_youtube(raw_desc)
                desc = clean_desc(raw_desc)
                link = entry.get("link", "")
                norm = re.sub(r"[^a-zа-яё0-9]", "", (title + desc[:100]).lower())
                h = hashlib.md5(norm.encode()).hexdigest()
                if h in seen_hashes:
                    continue
                seen_hashes.add(h)
                items.append({
                    "title": title,
                    "desc": desc,
                    "link": link,
                    "source": source,
                    "youtube_url": youtube_url,
                    "rss_img": rss_image(entry),
                    "id": "".join(c for c in link if c.isalnum()),
                    "content_hash": h,
                })
            print(f"  OK: {len(feed.entries)} items")
        except Exception as e:
            print(f"  Error loading {url}: {e}")
    return items


def check_is_live():
    try:
        r = requests.post("https://gql.twitch.tv/gql",
            json={
                "query": "query($login: String) {user(login: $login) {stream {title type viewersCount game {name}}}}",
                "variables": {"login": "NektarinGaming"}
            },
            headers={"Client-ID": TWITCH_CLIENT_ID, "User-Agent": "Mozilla/5.0"},
            timeout=8)
        if r.status_code == 200:
            data = r.json()
            s = data.get("data", {}).get("user", {}).get("stream")
            if s:
                return s.get("title", ""), s.get("game", {}).get("name", "unknown")
        return None
    except Exception as e:
        print(f"  Twitch check error: {e}")
    return None

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
        # short Russian noise words
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


# ---- Image lookup ----

def wiki_image(game_name):
    def name_match(page_title, search_name):
        a = re.sub(r"[^a-zа-яё0-9 ]", "", page_title.lower()).strip()
        b = re.sub(r"[^a-zа-яё0-9 ]", "", search_name.lower()).strip()
        return len(a) > 3 and (a.startswith(b) or b.startswith(a) or any(w in a for w in b.split() if len(w) > 3))

    for lang, domain in [("ru", "ru.wikipedia.org"), ("en", "en.wikipedia.org")]:
        try:
            search = requests.get(
                f"https://{domain}/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": game_name + " (video game)" if lang == "en" else game_name + " (игра)",
                    "srlimit": 3,
                    "format": "json",
                },
                timeout=6,
                headers={"User-Agent": WIKI_UA},
            )
            pages = search.json().get("query", {}).get("search", [])
            if not pages:
                continue

            titles = [p["title"] for p in pages[:2]]
            img_query = requests.get(
                f"https://{domain}/w/api.php",
                params={
                    "action": "query",
                    "titles": "|".join(titles),
                    "prop": "pageprops|pageimages",
                    "ppprop": "wikibase_item",
                    "pithumbsize": 1920,
                    "format": "json",
                    "redirects": 1,
                },
                timeout=6,
                headers={"User-Agent": WIKI_UA},
            )
            data = img_query.json()
            for pid, info in data.get("query", {}).get("pages", {}).items():
                if pid == "-1":
                    continue
                page_title = info.get("title", "")
                if not name_match(page_title, game_name):
                    print(f"  Wiki page mismatch: '{page_title}' vs '{game_name}'")
                    continue
                qid = info.get("pageprops", {}).get("wikibase_item")
                if not qid:
                    continue

                wd = requests.get(
                    "https://www.wikidata.org/w/api.php",
                    params={
                        "action": "wbgetentities",
                        "ids": qid,
                        "props": "claims",
                        "format": "json",
                    },
                    timeout=6,
                    headers={"User-Agent": WIKI_UA},
                )
                claims = wd.json().get("entities", {}).get(qid, {}).get("claims", {})
                for prop in ("P18", "P154"):
                    if prop in claims:
                        img_name = claims[prop][0]["mainsnak"]["datavalue"]["value"]
                        ext = img_name.split(".")[-1].lower() if "." in img_name else ""
                        if ext in ("jpg", "jpeg", "png", "webp"):
                            img_name = img_name.replace(" ", "_")
                            return f"https://commons.wikimedia.org/wiki/Special:FilePath/{img_name}?width=1920"
        except Exception:
            continue

    return None


def steam_image(game_name):
    try:
        r = requests.get("https://store.steampowered.com/api/storesearch",
            params={"term": game_name[:40], "l": "english", "cc": "us"},
            timeout=8)
        if r.status_code == 200:
            items = r.json().get("items", [])
            for item in items:
                if item.get("type") == "app":
                    name = item.get("name", "").lower()
                    clean_name = game_name.lower()
                    if not (clean_name in name or name in clean_name):
                        continue
                    appid = item.get("id")
                    base = f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}"
                    for size in ("library_hero", "library_600x900", "header"):
                        img = requests.head(f"{base}/{size}.jpg", timeout=5)
                        if img.status_code == 200:
                            return f"{base}/{size}.jpg"
    except Exception:
        pass
    return None


def rawg_image(game_name):
    key = os.environ.get("RAWG_API_KEY", "")
    if not key:
        return None
    try:
        r = requests.get("https://api.rawg.io/api/games",
            params={"key": key, "search": game_name[:40], "page_size": 1},
            timeout=8)
        if r.status_code == 200:
            results = r.json().get("results", [])
            if results:
                bg = results[0].get("background_image")
                if bg:
                    return bg
    except Exception:
        pass
    return None


def steamgrid_image(game_name):
    key = os.environ.get("SGDB_API_KEY", "")
    if not key:
        return None
    try:
        r = requests.get(
            f"https://www.steamgriddb.com/api/v2/search/autocomplete/{game_name[:30]}",
            headers={"Authorization": f"Bearer {key}"},
            timeout=8)
        if r.status_code != 200:
            return None
        results = r.json().get("data", [])
        if not results:
            return None
        sgid = results[0].get("id")
        if not sgid:
            return None
        grids = requests.get(
            f"https://www.steamgriddb.com/api/v2/grids/game/{sgid}",
            headers={"Authorization": f"Bearer {key}"},
            params={"dimensions": "460x215,920x430", "mimes": "image/png,image/jpeg"},
            timeout=8)
        if grids.status_code == 200:
            items = grids.json().get("data", [])
            if items:
                return items[0].get("url")
    except Exception:
        pass
    return None


def goha_image(desc):
    m = re.search(r'https?://[^\s"<>]+\.(?:jpg|jpeg|png|webp)', desc)
    if m:
        return m.group(0)
    return None


def rss_image(entry):
    for mc in entry.get("media_content", []):
        url = mc.get("url", "")
        if url and re.search(r'\.(?:jpg|jpeg|png|webp)\b', url):
            return url
    for mt in entry.get("media_thumbnail", []):
        url = mt.get("url", "")
        if url:
            return url
    for link in entry.get("links", []):
        if link.get("type", "").startswith("image"):
            url = link.get("href", "")
            if url:
                return url
    raw = entry.get("description", "") or ""
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', raw)
    if m:
        url = m.group(1)
        if url.startswith("//"):
            url = "https:" + url
        return url
    return None


def pinterest_image(game_name):
    global PINTEREST_SESSION
    try:
        if PINTEREST_SESSION is None:
            s = requests.Session()
            s.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            })
            s.get('https://www.pinterest.com/', timeout=10)
            s.headers.update({
                'X-CSRFToken': s.cookies.get('csrftoken', ''),
                'X-Pinterest-AppState': 'active',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': 'https://www.pinterest.com/',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
            })
            PINTEREST_SESSION = s

        query = f"{game_name} game cover art"
        post_data = {
            'source_url': '/search/pins/?q=' + requests.utils.quote(query),
            'data': json.dumps({
                'options': {
                    'query': query,
                    'scope': 'pins',
                    'page_size': 3,
                    'bookmarks': [],
                },
                'context': {},
            }, ensure_ascii=False),
        }
        r = PINTEREST_SESSION.post(
            'https://www.pinterest.com/resource/SearchResource/get/',
            data=post_data,
            timeout=15,
        )
        if r.status_code != 200:
            PINTEREST_SESSION = None
            return None
        results = r.json().get('resource_response', {}).get('data', [])
        for pin in results:
            images = pin.get('images', {})
            for size in ('orig', 'originals', '736x'):
                if size in images:
                    url = images[size].get('url', '')
                    if url:
                        return url
    except Exception:
        PINTEREST_SESSION = None
    return None


# ---- Templates ----

def pick(seq):
    return random.choice(seq) if seq else ""

COMMENTARIES = {
    "sales": [
        "Ого, неплохо продаётся!",
        "Народ знает толк.",
        "Миллионеры, блин.",
        "Кассовый успех на лицо.",
        "А вы уже купили или ждёте скидку?",
    ],
    "delay": [
        "Ну вот, опять перенос...",
        "Ждали? Потерпите ещё.",
        "Классика жанра — очередной перенос.",
        "Видимо, решили допилить до ума.",
        "Не судьба пока.",
    ],
    "sequel": [
        "О, а вот это интересно.",
        "Продолжение следует!",
        "Надо будет обязательно глянуть.",
        "Вернуться во вселенную — отличная идея.",
        "Сиквел, которого все ждали.",
    ],
    "console": [
        "Консольщики, внимание.",
        "Эксклюзивчик подвезли.",
        "На консолях тоже праздник.",
        "Поиграть можно будет и на диване.",
    ],
    "drama": [
        "Ой, всё...",
        "Скандалы, интриги, расследования.",
        "Драма на ровном месте.",
        "Без хайпа никак.",
        "И снова вокруг игры шум.",
    ],
    "generic": [
        "Вот такое дело.",
        "Новости игропрома.",
        "Держите в курсе.",
        "Будет интересно.",
        "На заметку.",
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

def embed_link(text, link):
    if not link or link in text:
        return text
    return f"{text}\n\nПодробнее: {link}"

def template_sales(title, desc, game, numbers, platforms, genre, link):
    s = shorten(desc, MAX_DESC_LEN)
    n = numbers[0] if numbers else "внушительное количество"
    commentary = smart_comment("sales", game, title)
    body = f"Продажи {game} достигли отметки в {n} копий. {s}"
    return [commentary, "\u2581" * 7, embed_link(body, link)]

def template_delay(title, desc, game, numbers, platforms, genre, link):
    s = shorten(desc, MAX_DESC_LEN)
    commentary = smart_comment("delay", game, title)
    body = f"Релиз {game} перенесён. {s}"
    return [commentary, "\u2581" * 7, embed_link(body, link)]

def template_sequel(title, desc, game, numbers, platforms, genre, link):
    s = shorten(desc, MAX_DESC_LEN)
    commentary = smart_comment("sequel", game, title)
    body = f"{game} — продолжение истории. {s}"
    return [commentary, "\u2581" * 7, embed_link(body, link)]

def template_console(title, desc, game, numbers, platforms, genre, link):
    s = shorten(desc, MAX_DESC_LEN)
    commentary = smart_comment("console", game, title)
    body = f"{game}{' на ' + '/'.join(platforms[:3]) if platforms else ''}. {s}"
    return [commentary, "\u2581" * 7, embed_link(body, link)]

def template_drama(title, desc, game, numbers, platforms, genre, link):
    s = shorten(desc, MAX_DESC_LEN)
    commentary = smart_comment("drama", game, title)
    body = f"Скандал вокруг {game}. {s}"
    return [commentary, "\u2581" * 7, embed_link(body, link)]

def template_generic(title, desc, game, numbers, platforms, genre, link):
    s = shorten(desc, MAX_DESC_LEN)
    commentary = smart_comment("generic", game, title)
    body = f"{title}. {s}" if s else title
    return [commentary, "\u2581" * 7, embed_link(body, link)]

def template_rumor(title, desc, game, numbers, platforms, genre, link):
    s = shorten(desc, MAX_DESC_LEN)
    commentary = smart_comment("rumor", game, title)
    body = f"Говорят, что {game}. {s}"
    return [commentary, "\u2581" * 7, embed_link(body, link)]

def template_announce(title, desc, game, numbers, platforms, genre, link):
    s = shorten(desc, MAX_DESC_LEN)
    commentary = smart_comment("announce", game, title)
    body = f"Анонс! {game}. {s}"
    return [commentary, "\u2581" * 7, embed_link(body, link)]

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


def make_caption(title, desc, link, game=None):
    if not desc:
        desc = title

    title = escape_md(title)
    desc = escape_md(desc)

    if not game:
        game = extract_game(title)
    game = escape_md(game)
    numbers = extract_numbers(desc)
    platforms = extract_platforms(title + " " + desc)
    genre = detect_genre(desc)
    theme = detect_theme(title, desc)

    builder = TEMPLATES.get(theme, template_generic)
    parts = builder(title, desc, game, numbers, platforms, genre, link)
    caption = "\n".join(parts)

    emoji = THEME_EMOJI.get(theme, "\U0001F4F0")
    caption = f"{emoji} {caption}"

    caption += CHANNEL_SIGNATURE

    hashtag = THEME_HASHTAGS.get(theme, "#игровыеновости")
    caption += f"\n{hashtag}"

    if len(caption) > MAX_CAPTION_LEN:
        caption = caption[:MAX_CAPTION_LEN - 3] + "..."
        # remove broken Markdown at truncation point
        caption = re.sub(r'(\*{1,2}|_{1,2}|`+)\s*$', '', caption)
    return caption


# ---- Image lookup ----

def find_image(title, desc, source, game=None):
    if not game:
        game = extract_game(title)
    clean_name = re.sub(r"\s*[….!?,;:]+\s*$", "", game).strip()
    if len(clean_name) < 3:
        clean_name = title.split()[0] if title.split() else ""

    print(f"  Looking up image for: {clean_name}")

    known_platforms = {"playstation", "xbox", "nintendo", "switch", "ps5", "ps4", "ps3", "steam"}
    if clean_name.lower() in known_platforms or re.match(r"^(playstation|nintendo|xbox)\s*\d*$", clean_name, re.I):
        print(f"  Skipped — known platform name")
        return None

    if source == "goha":
        img = goha_image(desc)
        if img:
            print(f"  Found GoHa image")
            return img

    try:
        img = pinterest_image(clean_name)
        if img:
            print(f"  Found Pinterest image (highest quality): {clean_name}")
            return img
    except Exception as e:
        print(f"  Pinterest error: {e}")

    try:
        img = wiki_image(clean_name)
        if img:
            print(f"  Found Wikipedia image")
            return img
    except Exception as e:
        print(f"  Wiki error: {e}")

    try:
        img = steam_image(clean_name)
        if img:
            print(f"  Found Steam image: {clean_name}")
            return img
    except Exception as e:
        print(f"  Steam error: {e}")

    try:
        img = rawg_image(clean_name)
        if img:
            print(f"  Found RAWG image: {clean_name}")
            return img
    except Exception as e:
        print(f"  RAWG error: {e}")

    try:
        img = steamgrid_image(clean_name)
        if img:
            print(f"  Found SteamGridDB image: {clean_name}")
            return img
    except Exception as e:
        print(f"  SGDB error: {e}")

    return None


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

def find_post_image(item):
    rss_img = item.get("rss_img")
    if rss_img:
        try:
            resp = requests.get(rss_img, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200 and is_hd(resp.content):
                return rss_img
        except Exception:
            pass
    game = item.get("_game") or extract_game(item["title"])
    try:
        return find_image(item["title"], item.get("desc", ""), item["source"], game)
    except Exception:
        pass
    return None


def send_post(title, desc, link, img_url, youtube_url=None, game=None, custom_caption=None):
    caption = custom_caption or make_caption(title, desc, link, game)

    is_trailer_post = youtube_url and is_trailer(title)

    # Trailer post — send message with YouTube link (Telegram auto-embeds)
    if is_trailer_post:
        try:
            text = f"{caption}\n\n{youtube_url}"
            r = tg("sendMessage", json={
                "chat_id": CHANNEL_ID,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False,
            }, timeout=15)
            if r:
                msg_id = r.json()["result"]["message_id"]
                print(f"  Sent trailer: {title[:60]} (msg#{msg_id})")
                return msg_id
            print(f"  Trailer send failed ({r.status_code if r else 'no response'})")
        except Exception as e:
            print(f"  Trailer err: {e}")

    # Normal image
    if img_url:
        try:
            img_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            img_data = requests.get(img_url, headers=img_headers, timeout=10)
            if img_data.status_code == 200 and is_hd(img_data.content):
                ct = img_data.headers.get("content-type", "").lower()
                if "png" in ct:
                    ext, mime = "png", "image/png"
                elif "webp" in ct:
                    ext, mime = "webp", "image/webp"
                elif "gif" in ct:
                    ext, mime = "gif", "image/gif"
                else:
                    ext, mime = "jpg", "image/jpeg"
                files = {"photo": (f"image.{ext}", img_data.content, mime)}
                payload = {
                    "chat_id": CHANNEL_ID,
                    "caption": caption,
                    "parse_mode": "Markdown",
                }
                r = tg("sendPhoto", data=payload, files=files, timeout=20)
                if r:
                    msg_id = r.json()["result"]["message_id"]
                    print(f"  Sent with image: {title[:60]} (msg#{msg_id})")
                    return msg_id
            print(f"  Image failed or too small, sending text")
        except Exception as e:
            print(f"  Image err: {e}")

    r = tg("sendMessage", json={
        "chat_id": CHANNEL_ID,
        "text": caption,
        "parse_mode": "Markdown",
    }, timeout=10)
    if r:
        msg_id = r.json()["result"]["message_id"]
        print(f"  Sent: {title[:60]} (msg#{msg_id})")
        return msg_id
    print(f"  Send failed")
    return None


def send_live_notification(title, game):
    text = (
        f"\U0001F534 **Я В ЭФИРЕ!**\n\n"
        f"**{escape_md(title)}**\n"
        f"\u2500" * 20 + "\n"
        f"Игра: **{escape_md(game)}**\n\n"
        f"Смотреть: https://twitch.tv/NektarinGaming"
    )
    try:
        r = tg("sendMessage", json={
            "chat_id": CHANNEL_ID,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        }, timeout=10)
        if r:
            print(f"  Live notification sent: {title[:50]}")
            return True
        print(f"  Live notification failed: {r.text[:100]}")
    except Exception as e:
        print(f"  Live notification err: {e}")
    return False


# ---- Free Games ----


def fetch_epic_free_games():
    try:
        r = requests.get(
            "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions",
            params={"locale": "ru-RU", "country": "RU"},
            timeout=12,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        games = []
        for el in data.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", []):
            if not el.get("promotions"):
                continue
            title = el.get("title", "")
            if not title or title.lower().startswith("mystery game"):
                continue
            promos = el["promotions"]
            offer = None
            source = None
            for offer_list, src in [
                (promos.get("promotionalOffers"), "current"),
                (promos.get("upcomingPromotionalOffers"), "upcoming"),
            ]:
                if not offer_list:
                    continue
                po = offer_list[0].get("promotionalOffers", [{}])[0]
                ds = po.get("discountSetting") or {}
                if ds.get("discountPercentage") == 0:
                    offer = po
                    source = src
                    break
            if not offer:
                continue
            slug = el.get("productSlug", "")
            if slug in (None, "", "[]"):
                slug = el.get("urlSlug", "") or ""
            if slug in (None, "", "[]"):
                slug = ""
            else:
                for attr in el.get("customAttributes") or []:
                    if attr.get("key") == "com.epicgames.app.productSlug" and attr.get("value") not in (None, "", "[]"):
                        slug = attr["value"]
                        break
            url = f"https://store.epicgames.com/ru/p/{slug}" if slug else ""
            desc = clean(el.get("description", "") or "")
            desc = re.sub(r"^Get ", "", desc, flags=re.I)
            key_images = el.get("keyImages", [])
            image = None
            for t in ("Thumbnail", "DieselGameBoxTall", "DieselGameBoxWide"):
                for img in key_images:
                    if img.get("type") == t:
                        image = img.get("url")
                        break
                if image:
                    break
            if not image and key_images:
                image = key_images[0].get("url")
            end_str = offer.get("endDate", "")
            end_readable = ""
            if end_str:
                try:
                    dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                    end_readable = dt.astimezone().strftime("%d.%m.%Y %H:%M МСК")
                except Exception:
                    end_readable = end_str[:10]
            games.append({
                "title": title,
                "desc": desc[:200],
                "image": image,
                "url": url,
                "end_date": end_readable,
                "source": source,
            })
        return games
    except Exception as e:
        print(f"  Epic free games error: {e}")
        return []


# ---- GOG Free Games ----


def fetch_gog_free_games():
    try:
        r = requests.get("https://www.gog.com/games/ajax/filtered",
            params={"mediaType": "game", "price": "free", "limit": 10},
            timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
        games = []
        for product in data.get("products", []):
            title = product.get("title", "")
            if not title:
                continue
            url = f"https://www.gog.com{product.get('url', '')}" if product.get("url") else ""
            image = product.get("image") or product.get("image_facebook") or ""
            games.append({
                "title": title,
                "url": url,
                "image": image,
            })
        return games
    except Exception as e:
        print(f"  GOG free games error: {e}")
        return []


def send_deals_batch(steam_deals, epic_free, gog_free):
    lines = ["\U0001F4F0 **Акции и раздачи**", ""]
    count = 0

    if epic_free:
        lines.append("\U0001F381 **Epic Games**")
        for g in epic_free:
            url = g.get("url", "")
            t = escape_md(g["title"])
            if url:
                lines.append(f"\U0001F539 [{t}]({url})")
            else:
                lines.append(f"\U0001F539 {t}")
            if g.get("end_date"):
                lines.append(f"   \U0001F512 до {g['end_date']}")
            count += 1
        lines.append("")

    if gog_free:
        lines.append("\U0001F4F0 **GOG**")
        for g in gog_free:
            url = g.get("url", "")
            t = escape_md(g["title"])
            if url:
                lines.append(f"\U0001F539 [{t}]({url})")
            else:
                lines.append(f"\U0001F539 {t}")
            count += 1
        lines.append("")

    if steam_deals:
        lines.append("\U0001F3AE **Steam**")
        for d in steam_deals:
            appid = d["appid"]
            title = escape_md(d["title"])
            lines.append(f"\U0001F539 [{title} -{d['discount']}%](https://store.steampowered.com/app/{appid}/)")
            lines.append(f"   \u20BD {d['final_price']:.0f} вместо {d['original_price']:.0f}")
            if d.get("expires"):
                lines.append(f"   \U0001F512 до {d['expires']}")
            count += 1
        lines.append("")

    if count == 0:
        return None

    text = "\n".join(lines).strip()
    if len(text) > 4000:
        text = text[:3997] + "..."

    r = tg("sendMessage", json={
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }, timeout=12)
    if r:
        msg_id = r.json()["result"]["message_id"]
        print(f"  Deals batch sent ({count} items, msg#{msg_id})")
        return msg_id
    print(f"  Deals batch failed")
    send_error(f"Deals batch failed")
    return None


# ---- Steam Deals ----


def fetch_steam_deals(min_discount=70):
    try:
        r = requests.get("https://store.steampowered.com/api/featuredcategories",
            params={"cc": "RU", "l": "russian"}, timeout=10)
        if r.status_code != 200:
            print(f"  Steam categories API: {r.status_code}")
            return []
        data = r.json()
        deals = []
        for item in data.get("specials", {}).get("items", []):
            dp = item.get("discount_percent", 0)
            if dp < min_discount:
                continue
            appid = item.get("id")
            name = item.get("name", "")
            if not appid or not name:
                continue
            orig = (item.get("original_price") or 0) / 100
            final = (item.get("final_price") or 0) / 100
            expires = item.get("discount_expiration")
            if expires:
                expires_dt = datetime.fromtimestamp(expires, tz=timezone.utc).astimezone()
                expires_str = expires_dt.strftime("%d.%m.%Y %H:%M МСК")
            else:
                expires_str = ""
            deals.append({
                "appid": appid,
                "title": name,
                "discount": dp,
                "original_price": orig,
                "final_price": final,
                "image": item.get("large_capsule_image") or item.get("small_capsule_image"),
                "expires": expires_str,
            })
        return deals
    except Exception as e:
        print(f"  Steam deals error: {e}")
        return []


# ---- Feature Content ----


def fetch_steam_top_sellers():
    try:
        r = requests.get("https://store.steampowered.com/api/featuredcategories",
            params={"cc": "RU", "l": "russian"}, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
        items = data.get("top_sellers", {}).get("items", [])[:10]
        top = []
        for item in items:
            name = item.get("name", "")
            appid = item.get("id")
            dp = item.get("discount_percent", 0)
            if not name or not appid:
                continue
            if dp:
                final = (item.get("final_price") or 0) / 100
                orig = (item.get("original_price") or 0) / 100
                price = f"\u20BD{final:.0f} (-{dp}%)"
            else:
                orig = (item.get("original_price") or 0) / 100
                price = f"\u20BD{orig:.0f}" if orig else "?"
            top.append({"title": name, "appid": appid, "price": price, "discount": dp})
        return top
    except Exception as e:
        print(f"  Top sellers error: {e}")
        return []


def make_top_sellers_post(top):
    lines = ["\U0001F3C6 **Топ продаж Steam за неделю**", ""]
    for i, game in enumerate(top, 1):
        medal = "\U0001F947" if i == 1 else "\U0001F948" if i == 2 else "\U0001F949" if i == 3 else "\U0001F539"
        lines.append(f"{medal} [{game['title']}](https://store.steampowered.com/app/{game['appid']}/)")
        lines.append(f"   {game['price']}")
    lines.append("")
    lines.append("_\u0427\u0442\u043E \u0431\u0440\u0430\u0442\u044C \u0431\u0443\u0434\u0435\u043C?_\u200E")
    return "\n".join(lines)


def fetch_on_this_day():
    try:
        month = time.localtime().tm_mon
        day = time.localtime().tm_mday
        r = requests.get(
            f"https://en.wikipedia.org/api/rest_v1/feed/onthisday/events/{month}/{day}",
            timeout=8)
        if r.status_code != 200:
            return []
        data = r.json()
        games = []
        for event in data.get("events", []):
            text = event.get("text", "")
            year = event.get("year", "")
            if not text or not year:
                continue
            t = text.lower()
            if any(w in t for w in ("video game", "released", "published", "launched")):
                pages = event.get("pages", [])
                img = ""
                for p in pages:
                    if p.get("thumbnail"):
                        img = p["thumbnail"].get("source", "")
                        break
                games.append({"text": text, "year": year, "image": img})
            if len(games) >= 3:
                break
        return games
    except Exception as e:
        print(f"  On this day error: {e}")
        return []


def make_on_this_day_post(events):
    lines = ["\U0001F4C5 **\u0412 \u044D\u0442\u043E\u0442 \u0434\u0435\u043D\u044C \u0432 \u0438\u0433\u0440\u043E\u043F\u0440\u043E\u043C\u0435**", ""]
    for ev in events:
        lines.append(f"\u2022 **{ev['year']}** \u2014 {ev['text']}")
    lines.append("")
    lines.append("_\u041D\u043E\u0441\u0442\u0430\u043B\u044C\u0433\u0438\u044F, \u043E\u0434\u043D\u0430\u043A\u043E._")
    return "\n".join(lines), events[0]["image"] if events and events[0]["image"] else None


def fetch_upcoming_releases():
    try:
        r = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": f"upcoming video games {time.localtime().tm_year}",
                "srlimit": 3,
                "format": "json",
            },
            timeout=8,
            headers={"User-Agent": WIKI_UA},
        )
        data = r.json()
        pages = data.get("query", {}).get("search", [])
        releases = []
        for p in pages:
            title = p.get("title", "")
            snippet = clean(p.get("snippet", ""))
            if title:
                releases.append({"title": title, "desc": snippet[:200]})
        return releases
    except Exception as e:
        print(f"  Upcoming releases error: {e}")
        return []


def make_releases_post(releases):
    lines = ["\U0001F4C5 **\u0420\u0435\u043B\u0438\u0437\u044B \u043D\u0435\u0434\u0435\u043B\u0438**", ""]
    today = time.strftime("%d.%m")
    lines.append(f"\u0412\u044B\u0445\u043E\u0434\u0438\u0442 \u043D\u0430 \u044D\u0442\u043E\u0439 \u043D\u0435\u0434\u0435\u043B\u0435 ({today}):")
    lines.append("")
    for r in releases:
        lines.append(f"\U0001F539 **{r['title']}**")
        if r["desc"]:
            lines.append(f"   {r['desc']}")
        lines.append("")
    lines.append("_\u041F\u043E\u043B\u043D\u044B\u0439 \u0441\u043F\u0438\u0441\u043E\u043A \u043D\u0430 Wiki._")
    return "\n".join(lines)


def post_nikita_recommendation(state):
    today = time.strftime("%Y-%m-%d")
    last = state.get("nikita_posted", "")
    if last == today:
        return False
    pick = random.choice(NIKITA_PICKS)
    tag_emoji = "\U0001F3AE" if pick["tag"] == "game" else "\U0001F48C"
    tag_label = "\u0418\u0433\u0440\u0430" if pick["tag"] == "game" else "\u0410\u043D\u0438\u043C\u0435"
    text = (
        f"{tag_emoji} **\u0420\u0435\u043A\u043E\u043C\u0435\u043D\u0434\u0430\u0446\u0438\u044F \u043E\u0442 \u041D\u0438\u043A\u0438\u0442\u044B**\n\n"
        f"**{pick['title']}** ({tag_label})\n"
        f"{pick['desc']}\n"
        f"\u2581" * 7 + "\n"
        f"\u041B\u0438\u0447\u043D\u043E \u043C\u043D\u0435 \u043E\u0447\u0435\u043D\u044C \u0437\u0430\u0448\u043B\u043E, \u043C\u043E\u0436\u0435\u0442 \u0438 \u0432\u0430\u043C \u0437\u0430\u0439\u0434\u0451\u0442."
        f"{CHANNEL_SIGNATURE}"
    )
    try:
        r = tg("sendMessage", json={
            "chat_id": CHANNEL_ID,
            "text": text,
            "parse_mode": "Markdown",
        }, timeout=10)
        if r:
            state["nikita_posted"] = today
            print(f"  Nikita recommendation posted: {pick['title']}")
            return True
        print(f"  Recommendation failed")
    except Exception as e:
        print(f"  Recommendation err: {e}")
    return False


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
    emoji = THEME_EMOJI.get(theme, "\U0001F48C")
    commentary = pick(COMMENTARIES.get(theme, COMMENTARIES["generic"]))
    ru_title = translate_en_ru(title)
    ru_desc = translate_en_ru(shorten(desc, 200))
    body = f"{ru_title}. {ru_desc}" if ru_desc else ru_title
    return f"{emoji} {commentary}\n{"\u2581" * 7}\n{body}\n\nПодробнее: {link}{CHANNEL_SIGNATURE}\n#аниме"


def post_anime_news(state):
    today = time.strftime("%Y-%m-%d")
    last = state.get("anime_posted", "")
    if last == today:
        return False
    interests = state.get("anime_interests", {})

    candidates = []
    for url, source, limit in ANIME_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:limit + 10]:
                raw_title = entry.get("title", "")
                title = clean(raw_title)
                raw_desc = entry.get("description", "") or ""
                desc = clean_desc(raw_desc)
                if not title:
                    continue
                sc = score_anime_entry(title, desc, interests)
                link = entry.get("link", "")
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
    msg_id = None
    if img:
        try:
            img_data = requests.get(img, timeout=8)
            if img_data.status_code == 200 and is_hd(img_data.content):
                r = tg("sendPhoto", data={
                    "chat_id": CHANNEL_ID, "caption": caption, "parse_mode": "Markdown",
                }, files={"photo": ("anime.jpg", img_data.content, "image/jpeg")}, timeout=15)
                if r:
                    msg_id = r.json()["result"]["message_id"]
        except Exception:
            pass
    if not msg_id:
        r = tg("sendMessage", json={
            "chat_id": CHANNEL_ID, "text": caption, "parse_mode": "Markdown",
        }, timeout=10)
        if r:
            msg_id = r.json()["result"]["message_id"]
    if msg_id:
        state["anime_posted"] = today
        print(f"  Anime news posted: {title[:50]}")
        return True
    return False


_YT_CACHE = {}

def youtube_search(query):
    if query in _YT_CACHE:
        return _YT_CACHE[query]
    try:
        q = requests.utils.quote(query)
        r = requests.get(f"https://www.youtube.com/results?search_query={q}",
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        if r.status_code == 200:
            ids = re.findall(r"watch\?v=([a-zA-Z0-9_-]{11})", r.text)
            if ids:
                url = f"https://youtu.be/{ids[0]}"
                _YT_CACHE[query] = url
                return url
    except Exception as e:
        print(f"  YT search err: {e}")
    return None


def rock_track_urls(artist):
    tracks = ROCK_TRACKS.get(artist.lower())
    if not tracks or len(tracks) < 2:
        return []
    picked = random.sample(tracks, 2)
    urls = []
    for name, query in picked:
        url = youtube_search(query)
        if url:
            urls.append((name, url))
    return urls


def extract_album_name(title, desc):
    text = title + " " + desc
    patterns = [
        r"album\s+(?:«|'|\")(.*?)(?:»|'|\")",
        r"(?:«|'|\")(.*?)(?:»|'|\")\s*(?:album|LP)",
        r"new\s+(?:album|LP|record|single)\s+(?:«|'|\")(.*?)(?:»|'|\")",
        r"(?:«|'|\")(.*?)(?:»|'|\")\s*(?:out|released|drops|arrives)",
        r"(?:album|LP)\s+(?:called|titled|named)\s+(?:«|'|\")(.*?)(?:»|'|\")",
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            return m.group(1).strip()
    return None


def album_cover_url(artist, album_name):
    try:
        q = requests.utils.quote(f"{artist} {album_name}")
        r = requests.get(f"https://itunes.apple.com/search?term={q}&entity=album&limit=3",
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        if r.status_code == 200:
            for result in r.json().get("results", []):
                art = result.get("artworkUrl100", "")
                if art:
                    return art.replace("100x100", "1200x1200").replace("100x100bb", "1200x1200bb")
    except Exception as e:
        print(f"  Album cover err: {e}")
    return None


def download_audio(query, output_dir, max_results=1):
    try:
        import yt_dlp
        opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(output_dir, "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "default_search": "ytsearch",
            "max_filesize": 15000000,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=True)
            entries = info.get("entries", [info])
            results = []
            for entry in entries:
                fn = ydl.prepare_filename(entry)
                title = entry.get("title", query)
                if os.path.exists(fn):
                    results.append((fn, title))
            if results:
                return results
    except Exception as e:
        print(f"  Audio download err: {e}")
    return None


def game_ost_tracks(game_name, output_dir):
    import re
    clean_name = re.sub(r"[^a-zA-Z0-9 \-\']", "", game_name).strip()
    if not clean_name:
        return []
    query = f"{clean_name} OST"
    print(f"  Searching OST for: {query}")
    results = download_audio(query, output_dir, max_results=5)
    if not results or len(results) < 2:
        print(f"  Not enough OST results for {game_name}, trying broader...")
        results = download_audio(f"{clean_name} soundtrack", output_dir, max_results=5)
    if results and len(results) >= 2:
        picked = random.sample(results, 2) if len(results) > 2 else results
        print(f"  Got {len(results)} OST results for {game_name}, picked 2")
        return picked
    elif results:
        print(f"  Only 1 OST result for {game_name}")
        return results
    return []


def post_rock_news(state):
    today = time.strftime("%Y-%m-%d")
    last = state.get("rock_posted", "")
    if last == today:
        return False
    artists_lower = [a.lower() for a in ROCK_ARTISTS]
    for url, source, limit in ROCK_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:limit]:
                raw_title = entry.get("title", "")
                title = clean(raw_title)
                raw_desc = entry.get("description", "") or ""
                desc = clean_desc(raw_desc)
                combined = (title + " " + desc).lower()
                matched = [a for a in artists_lower if a in combined]
                if not matched:
                    continue
                link = entry.get("link", "")
                img = rss_image(entry)
                artists_str = ", ".join(matched[:3])

                # Translate to Russian
                ru_title = translate_en_ru(title)
                ru_desc = translate_en_ru(shorten(desc, MAX_DESC_LEN))
                safe_title = escape_md(ru_title)
                safe_desc = escape_md(ru_desc)
                tags = " #" + " #".join(a.replace(" ", "_") for a in matched[:3])
                artist = matched[0]

                # Album detection
                album_name = extract_album_name(title, desc)
                album_line = ""
                if album_name:
                    album_line = f" — новый альбом «{escape_md(album_name)}»"
                    print(f"  Album detected: {album_name}")

                # Build caption
                caption = f"\U0001F3B8 **{safe_title}**{album_line}\n\n{safe_desc}\n\n[\u041F\u043E\u0434\u0440\u043E\u0431\u043D\u0435\u0435]({link})"
                caption += f"{CHANNEL_SIGNATURE}\n{tags}"
                caption_photo = None

                # Album cover first
                if album_name:
                    cover_url = album_cover_url(artist, album_name)
                    if cover_url:
                        try:
                            resp = requests.get(cover_url, timeout=8)
                            if resp.status_code == 200 and is_hd(resp.content):
                                caption_photo = resp.content
                        except Exception:
                            pass

                # Fallback to RSS image
                if not caption_photo and img:
                    try:
                        img_data = requests.get(img, timeout=8)
                        if img_data.status_code == 200 and is_hd(img_data.content):
                            caption_photo = img_data.content
                    except Exception:
                        pass

                msg_id = None
                if caption_photo:
                    r = tg("sendPhoto", data={
                        "chat_id": CHANNEL_ID, "caption": caption, "parse_mode": "Markdown",
                    }, files={"photo": ("rock.jpg", caption_photo, "image/jpeg")}, timeout=15)
                    if r:
                        msg_id = r.json()["result"]["message_id"]
                if not msg_id:
                    r = tg("sendMessage", json={
                        "chat_id": CHANNEL_ID, "text": caption, "parse_mode": "Markdown",
                    }, timeout=10)
                    if r:
                        msg_id = r.json()["result"]["message_id"]

                # Download and send 2 random tracks as audio
                if msg_id:
                    tracks = ROCK_TRACKS.get(artist, [])
                    if len(tracks) >= 2:
                        picked = random.sample(tracks, 2)
                        tmpdir = os.path.join(os.path.dirname(STATE_FILE), "audio_tmp")
                        os.makedirs(tmpdir, exist_ok=True)
                        for tname, tquery in picked:
                            results = download_audio(tquery, tmpdir)
                            path = None
                            if results:
                                path, real_title = results[0]
                            if path and os.path.exists(path):
                                safe_tname = escape_md(tname)
                                ext = os.path.splitext(path)[1] or ".webm"
                                mime_map = {
                                    ".mp3": "audio/mpeg",
                                    ".m4a": "audio/mp4",
                                    ".webm": "audio/webm",
                                    ".opus": "audio/opus",
                                    ".ogg": "audio/ogg",
                                    ".wav": "audio/wav",
                                }
                                mime = mime_map.get(ext.lower(), "audio/mpeg")
                                with open(path, "rb") as audio_f:
                                    r = tg("sendAudio", data={
                                        "chat_id": CHANNEL_ID,
                                        "title": tname,
                                        "performer": artist.title(),
                                    }, files={"audio": (f"{tname}{ext}", audio_f, mime)}, timeout=30)
                                try:
                                    os.remove(path)
                                except Exception:
                                    pass
                                if r:
                                    print(f"  Audio sent: {tname} (msg#{r.json()['result']['message_id']})")

                if msg_id:
                    state["rock_posted"] = today
                    print(f"  Rock news posted: {title[:50]} [{artists_str}]")
                    return True
        except Exception as e:
            print(f"  Rock feed {source} err: {e}")
    return False


def make_channel_stats(state):
    all_msgs = state.get("posted_msgs", {})
    now_t = time.time()
    week_ago = now_t - 604800
    recent = [(mid, data) for mid, data in all_msgs.items() if data.get("time", 0) >= week_ago]
    if len(recent) < 3:
        return None
    total_week = len(recent)
    # Count games
    game_counts = {}
    for mid, data in recent:
        game = data.get("game", "")
        if game:
            game_counts[game] = game_counts.get(game, 0) + 1
    top_games = sorted(game_counts.items(), key=lambda x: -x[1])[:5]
    # Count sources
    source_counts = {}
    for mid, data in recent:
        src = data.get("source", "other")
        source_counts[src] = source_counts.get(src, 0) + 1
    top_sources = sorted(source_counts.items(), key=lambda x: -x[1])[:3]
    lines = ["\U0001F4CA **Статистика недели**", ""]
    lines.append(f"\U0001F4F0 Всего постов: **{total_week}**")
    if top_games:
        lines.append("")
        lines.append("\U0001F3AE **Топ игр:**")
        for g, c in top_games:
            lines.append(f"\U0001F539 {g} — {c}")
    if top_sources:
        lines.append("")
        lines.append("\U0001F4E1 **Источники:**")
        for s, c in top_sources:
            lines.append(f"\U0001F539 {s} — {c}")
    lines.append("")
    lines.append("_Спасибо, что читаете!_")
    return "\n".join(lines)


QUIZZES = [
    {"q": "\u041A\u0430\u043A\u0430\u044F \u0438\u0433\u0440\u0430 \u043F\u0440\u043E\u0434\u0430\u043B\u0430\u0441\u044C \u0442\u0438\u0440\u0430\u0436\u043E\u043C \u0431\u043E\u043B\u0435\u0435 30 \u043C\u0438\u043B\u043B\u0438\u043E\u043D\u043E\u0432 \u043A\u043E\u043F\u0438\u0439?", "opts": ["Minecraft", "GTA V", "Tetris", "Wii Sports"], "ans": 2},
    {"q": "\u041A\u0442\u043E \u0440\u0430\u0437\u0440\u0430\u0431\u043E\u0442\u0430\u043B \u043F\u0435\u0440\u0432\u0443\u044E \u0438\u0433\u0440\u0443 \u0432 \u0441\u0435\u0440\u0438\u0438 Souls?", "opts": ["Hideki Kamiya", "Hidetaka Miyazaki", "Tomoyuki Hoshino", "Fumito Ueda"], "ans": 1},
    {"q": "\u041A\u0430\u043A\u043E\u0439 \u0433\u043E\u0434 \u0432\u044B\u0448\u043B\u0430 \u043F\u0435\u0440\u0432\u0430\u044F \u0447\u0430\u0441\u0442\u044C The Witcher?", "opts": ["2005", "2007", "2009", "2011"], "ans": 1},
    {"q": "\u0427\u0442\u043E \u043E\u0437\u043D\u0430\u0447\u0430\u0435\u0442 \u0430\u0431\u0431\u0440\u0435\u0432\u0438\u0430\u0442\u0443\u0440\u0430 RPG?", "opts": ["Realistic Physics Game", "Role-Playing Game", "Random Puzzle Game", "Rapid Platforming Game"], "ans": 1},
    {"q": "\u041A\u0430\u043A\u043E\u0439 \u043F\u0435\u0440\u0441\u043E\u043D\u0430\u0436 \u043D\u0435 \u044F\u0432\u043B\u044F\u0435\u0442\u0441\u044F \u043F\u043B\u0435\u0439\u043C\u0435\u0439\u043A\u0435\u0440\u043E\u043C \u0432 Super Smash Bros. Ultimate?", "opts": ["Sans", "Steve", "Doomguy", "Waluigi"], "ans": 3},
    {"q": "\u0412 \u043A\u0430\u043A\u043E\u0439 \u0438\u0433\u0440\u0435 \u043C\u043E\u0436\u043D\u043E \u043A\u043E\u0440\u043C\u0438\u0442\u044C \u044F\u0431\u043B\u043E\u043A\u0438 \u043F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u0442\u0435\u043B\u044F\u043C?", "opts": ["Minecraft", "Animal Crossing", "The Sims", "Among Us"], "ans": 0},
]

POST_POLLS = [
    {"q": "\u0427\u0435\u043C \u0437\u0430\u043D\u0438\u043C\u0430\u0435\u0448\u044C\u0441\u044F \u043D\u0430 \u0432\u044B\u0445\u043E\u0434\u043D\u044B\u0445?", "opts": ["\u0418\u0433\u0440\u0430\u044E \u0432 \u0438\u0433\u0440\u044B", "\u0421\u043C\u043E\u0442\u0440\u044E \u0430\u043D\u0438\u043C\u0435", "\u0427\u0438\u043B\u043B\u044E", "\u0420\u0430\u0431\u043E\u0442\u0430\u044E"]},
    {"q": "\u041A\u0430\u043A\u0443\u044E \u0436\u0430\u043D\u0440 \u043F\u0440\u0435\u0434\u043F\u043E\u0447\u0438\u0442\u0430\u0435\u0448\u044C?", "opts": ["RPG", "\u0428\u0443\u0442\u0435\u0440\u044B", "\u0425\u043E\u0440\u0440\u043E\u0440\u044B", "\u0421\u0442\u0440\u0430\u0442\u0435\u0433\u0438\u0438"]},
    {"q": "\u0427\u0435\u0433\u043E \u0436\u0434\u0451\u0448\u044C \u0431\u043E\u043B\u044C\u0448\u0435 \u0432\u0441\u0435\u0433\u043E?", "opts": ["GTA 6", "The Witcher 4", "Half-Life 3", "\u041D\u043E\u0432\u0443\u044E \u0447\u0430\u0441\u0442\u044C Souls"]},
    {"q": "\u041D\u0430 \u0447\u0451\u043C \u0438\u0433\u0440\u0430\u0435\u0448\u044C?", "opts": ["PC", "PlayStation", "Xbox", "Nintendo Switch"]},
]


def post_quiz(state):
    today = time.strftime("%Y-%m-%d")
    key = f"quiz_{today}"
    if key in state.get("features_posted", {}):
        return False
    q = QUIZZES[int(hashlib.md5(today.encode()).hexdigest(), 16) % len(QUIZZES)]
    try:
        r = tg("sendPoll", json={
            "chat_id": CHANNEL_ID,
            "question": f"\U0001F3B2 **\u0412\u0438\u043A\u0442\u043E\u0440\u0438\u043D\u0430:** {q['q']}",
            "options": q["opts"],
            "type": "quiz",
            "correct_option_id": q["ans"],
            "is_anonymous": False,
            "parse_mode": "Markdown",
        }, timeout=10)
        if r:
            print(f"  Quiz posted")
            state.setdefault("features_posted", {})[key] = {"time": time.time()}
            return True
    except Exception as e:
        print(f"  Quiz err: {e}")
    return False


def post_poll(state):
    today = time.strftime("%Y-%m-%d")
    key = f"poll_{today}"
    if key in state.get("features_posted", {}):
        return False
    p = random.choice(POST_POLLS)
    try:
        r = tg("sendPoll", json={
            "chat_id": CHANNEL_ID,
            "question": f"\U0001F4CA {p['q']}",
            "options": p["opts"],
            "type": "regular",
            "is_anonymous": False,
        }, timeout=10)
        if r:
            print(f"  Poll posted: {p['q'][:40]}")
            state.setdefault("features_posted", {})[key] = {"time": time.time()}
            return True
    except Exception as e:
        print(f"  Poll err: {e}")
    return False


def fetch_top_weekly(state):
    msgs = state.get("posted_msgs", {})
    now_t = time.time()
    week_ago = now_t - 604800
    recent = [(mid, data) for mid, data in msgs.items() if data.get("time", 0) >= week_ago]
    if len(recent) < 3:
        return None
    recent.sort(key=lambda x: -x[1].get("time", 0))
    lines = ["\U0001F525 **\u0414\u0430\u0439\u0434\u0436\u0435\u0441\u0442 \u043D\u0435\u0434\u0435\u043B\u0438**", ""]
    for i, (mid, _) in enumerate(recent[:7], 1):
        link = f"https://t.me/NektarinGaming/{mid}"
        lines.append(f"{i}. [\u041F\u043E\u0441\u0442 #{mid}]({link})")
    return "\n".join(lines)


def post_feature(feature_key, text, image_url=None, state=None):
    features_posted = state.setdefault("features_posted", {})
    if feature_key in features_posted:
        return None
    if image_url:
        try:
            img = requests.get(image_url, timeout=8)
            if img.status_code == 200:
                r = tg("sendPhoto", data={
                    "chat_id": CHANNEL_ID, "caption": text, "parse_mode": "Markdown",
                }, files={"photo": ("feature.jpg", img.content, "image/jpeg")}, timeout=15)
                if r:
                    features_posted[feature_key] = {"time": time.time()}
                    print(f"  Feature posted: {feature_key}")
                    return r.json()["result"]["message_id"]
        except Exception:
            pass
    r = tg("sendMessage", json={
        "chat_id": CHANNEL_ID, "text": text, "parse_mode": "Markdown",
    }, timeout=10)
    if r:
        features_posted[feature_key] = {"time": time.time()}
        print(f"  Feature posted (text): {feature_key}")
        return r.json()["result"]["message_id"]
    return None


REPLY_TEMPLATES = [
    "В точку! \U0001F44D",
    "Согласен на все 100%",
    "Мнение засчитано \U0001F91D",
    "Спорно, но достойно уважения",
    "Инсайдерская информация подтверждает",
    "Добавлю себе в цитатник",
    "Ты читаешь мои мысли",
    "Лучший комментарий недели",
    "Проверял — так и есть",
    "Ты слишком далеко зашёл \U0001F480",
    "Бот молчит — значит одобряет \u2705",
    "Задокументировано в архивах канала",
]


def reply_to_comments(state):
    bot_id = state.get("_bot_id", 0)
    if not bot_id:
        try:
            me = tg("getMe", json={})
            if me:
                bot_id = me.json()["result"]["id"]
                state["_bot_id"] = bot_id
        except Exception:
            pass
    try:
        chat_info = tg("getChat", json={"chat_id": CHANNEL_ID})
        if not chat_info:
            return 0
        data = chat_info.json()
        linked_group = data.get("result", {}).get("linked_chat_id")
        if not linked_group:
            return 0
    except Exception:
        return 0

    offset_key = "comment_offset"
    offset = state.get(offset_key, 0)
    replied = 0
    try:
        updates = tg("getUpdates", json={
            "offset": offset,
            "timeout": 0,
            "allowed_updates": ["message"],
        })
        if updates:
            results = updates.json().get("result", [])
            for upd in results:
                msg = upd.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                if chat_id != linked_group:
                    offset = upd["update_id"] + 1
                    continue
                text = msg.get("text", "").strip()
                from_id = msg.get("from", {}).get("id", 0)
                if not text or from_id == bot_id:
                    offset = upd["update_id"] + 1
                    continue
                # Listener track detection
                text_lower = text.lower()
                track_patterns = [
                    r" — ", r" – ", r" - ", r"–", r"—",
                    r"youtube\.com", r"youtu\.be",
                ]
                is_track_suggestion = any(re.search(p, text) for p in track_patterns) or \
                    text_lower.startswith("трек ") or \
                    text_lower.startswith("песня ") or \
                    text_lower.startswith("музыка ")
                if is_track_suggestion:
                    state["listener_track"] = {
                        "text": text,
                        "from": msg.get("from", {}).get("first_name", "Подписчик"),
                        "time": time.time(),
                        "week": time.strftime("%Y-W%V"),
                    }
                    print(f"  Listener track saved: {text[:60]}")
                reply = random.choice(REPLY_TEMPLATES)
                tg("sendMessage", json={
                    "chat_id": linked_group,
                    "text": reply,
                    "reply_to_message_id": msg.get("message_id"),
                }, timeout=10)
                replied += 1
                offset = upd["update_id"] + 1
    except Exception as e:
        print(f"  Comment reply err: {e}")
        return replied
    state[offset_key] = offset
    if replied:
        print(f"  Replied to {replied} comments")
    return replied


def post_listener_track(state):
    track = state.get("listener_track")
    if not track:
        return False
    current_week = time.strftime("%Y-W%V")
    if track.get("week") != current_week:
        del state["listener_track"]
        return False
    text = track["text"]
    from_name = track.get("from", "Подписчик")
    tmpdir = os.path.join(os.path.dirname(STATE_FILE), "audio_tmp")
    os.makedirs(tmpdir, exist_ok=True)
    results = download_audio(text, tmpdir)
    path = None
    real_title = text
    if results:
        path, real_title = results[0]
    if path and os.path.exists(path):
        ext = os.path.splitext(path)[1] or ".webm"
        mime_map = {
            ".mp3": "audio/mpeg", ".m4a": "audio/mp4",
            ".webm": "audio/webm", ".opus": "audio/opus",
            ".ogg": "audio/ogg", ".wav": "audio/wav",
        }
        mime = mime_map.get(ext.lower(), "audio/mpeg")
        caption = f"\U0001F3B5 **Трек недели от {escape_md(from_name)}**\n\n_{escape_md(text)}_\n\n_Хочешь предложить свой трек? Пиши в комментарии_ {CHANNEL_SIGNATURE}"
        with open(path, "rb") as f:
            r = tg("sendAudio", data={
                "chat_id": CHANNEL_ID,
                "title": text[:60],
                "performer": from_name,
            }, files={"audio": (f"listener_track{ext}", f, mime)}, timeout=30)
        try:
            os.remove(path)
        except Exception:
            pass
        if not r:
            return False
        del state["listener_track"]
        print(f"  Listener track posted: {text[:50]}")
        return True
    else:
        print(f"  Could not download listener track: {text[:60]}")
        return False


def main():
    token = os.environ.get("TG_BOT_TOKEN", BOT_TOKEN)
    if not token:
        print("Error: no bot token")
        return
    globals()["BOT_TOKEN"] = token

    # Log to file
    class Tee:
        def __init__(self):
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
    print("=== Gaming News Bot v3 (info-style) ===\n")
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"Started at {ts}")
    log_path = os.path.abspath(LOG_FILE)
    print(f"Logging to {log_path}")

    state = load_state()
    ids = state.get("ids", {})

    # --- Twitch live check ---
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

    # --- Time vars ---
    now_h = time.localtime().tm_hour
    now_wday = time.localtime().tm_wday
    today = time.strftime("%Y-%m-%d")
    week = time.strftime("%Y-W%V")

    # --- Night mode check ---
    if now_h in SILENT_HOURS:
        print(f"Night mode ({now_h}:00 — {max(SILENT_HOURS)+1}:00), skipping news")
        save_state(state)
        return

    posted = 0

    # --- Deals & free games (steam sales once/day, free games immediately) ---
    deals_date = state.setdefault("last_deals_date", "")
    deals_posted = state.setdefault("deals_posted", {})
    steam_deals = fetch_steam_deals()
    epic_free = fetch_epic_free_games()
    gog_free = fetch_gog_free_games()

    # Free games — post immediately whenever new
    new_free = []
    for src_name, fg_list in [("Epic", epic_free), ("GOG", gog_free)]:
        for fg in fg_list:
            key = f"{src_name.lower()}_{fg['title'].lower().replace(' ', '_')}"
            if key not in deals_posted:
                deals_posted[key] = {"title": fg["title"], "time": time.time()}
                new_free.append((src_name, fg))

    for src_name, fg in new_free:
        url = fg.get("url", "")
        end = fg.get("end_date", "")
        title_escaped = escape_md(fg["title"])
        text = f"\U0001F381 **\u041D\u043E\u0432\u0430\u044F \u0440\u0430\u0437\u0434\u0430\u0447\u0430 \u0432 {src_name}!**\n\n**{title_escaped}**"
        if end:
            text += f"\n\U0001F512 \u0434\u043E {end}"
        if url:
            text += f"\n\n[Забрать]({url})"
        text += CHANNEL_SIGNATURE
        try:
            r = tg("sendMessage", json={
                "chat_id": CHANNEL_ID, "text": text, "parse_mode": "Markdown",
                "disable_web_page_preview": False,
            }, timeout=10)
            if r:
                print(f"  New free game posted: {fg['title']} ({src_name})")
                posted += 1
        except Exception as e:
            print(f"  Free game post err: {e}")

    # Steam sales — post once per day (only if no free game was just posted)
    if today != deals_date:
        new_steam = []
        for deal in steam_deals:
            key = f"st_{deal['appid']}_{deal['discount']}"
            if key not in deals_posted:
                deals_posted[key] = {"title": deal["title"], "time": time.time()}
                new_steam.append(deal)
        if new_steam:
            msg_id = send_deals_batch(steam_deals, epic_free, gog_free)
            if msg_id:
                posted += 1
            state["last_deals_date"] = today

    # --- Watched games on sale ---
    watched_alerted = state.setdefault("watched_alerted", {})
    watched_matched = []
    for deal in steam_deals:
        key = f"st_{deal['appid']}_{deal['discount']}"
        if key in watched_alerted:
            continue
        t = deal["title"].lower()
        for w in WATCHED_GAMES:
            if w.lower() in t:
                watched_alerted[key] = {"title": deal["title"], "time": time.time()}
                watched_matched.append(deal)
                break
    if watched_matched:
        lines = ["\U0001F525 **Игра из списка ожидания в продаже!**", ""]
        for d in watched_matched:
            appid = d["appid"]
            title = escape_md(d["title"])
            lines.append(f"\U0001F539 [{title} -{d['discount']}%](https://store.steampowered.com/app/{appid}/)")
            lines.append(f"   \u20BD {d['final_price']:.0f} вместо {d['original_price']:.0f}")
            if d.get("expires"):
                lines.append(f"   \U0001F512 до {d['expires']}")
        text = "\n".join(lines)
        try:
            tg("sendMessage", json={
                "chat_id": ADMIN_CHAT,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False,
            }, timeout=8)
            print(f"  Watched game alert sent ({len(watched_matched)} items)")
        except Exception as e:
            print(f"  Watched alert err: {e}")

    # --- Scheduled features ---

    # Monday: releases of the week
    if now_wday == 0:
        releases = fetch_upcoming_releases()
        if releases:
            text = make_releases_post(releases)
            post_feature(f"releases_{today}", text, state=state)

    # Friday: weekend picks
    if now_wday == 4:
        picks_lines = ["\U0001F3AE **\u0427\u0442\u043E \u043F\u043E\u0438\u0433\u0440\u0430\u0442\u044C \u043D\u0430 \u0432\u044B\u0445\u043E\u0434\u043D\u044B\u0445**", ""]
        if steam_deals:
            picks_lines.append(f"\U0001F4B0 \u0421\u043A\u0438\u0434\u043A\u0438 \u043D\u0435\u0434\u0435\u043B\u0438 \u0432 Steam:")
            for d in steam_deals[:5]:
                picks_lines.append(f"\U0001F539 {d['title']} -{d['discount']}%")
            picks_lines.append("")
        if epic_free:
            picks_lines.append(f"\U0001F381 \u0411\u0435\u0441\u043F\u043B\u0430\u0442\u043D\u043E \u0432 Epic Games:")
            for g in epic_free:
                picks_lines.append(f"\U0001F539 {g['title']} \u2014 \u0434\u043E {g['end_date']}")
            picks_lines.append("")
        picks_lines.append("_\u0425\u043E\u0440\u043E\u0448\u0438\u0445 \u0432\u044B\u0445\u043E\u0434\u043D\u044B\u0445!_")
        post_feature(f"weekend_{today}", "\n".join(picks_lines), state=state)

    # Daily: on this day
    on_day = fetch_on_this_day()
    if on_day:
        text, img = make_on_this_day_post(on_day)
        post_feature(f"onthisday_{today}", text, image_url=img, state=state)

    # Weekly: top sellers (Monday)
    if now_wday == 0:
        top = fetch_steam_top_sellers()
        if top:
            text = make_top_sellers_post(top)
            post_feature(f"topsellers_{week}", text, state=state)

    # Weekly: channel stats (Sunday)
    if now_wday == 6:
        stats_text = make_channel_stats(state)
        if stats_text:
            post_feature(f"stats_{today}", stats_text, state=state)
        top_text = fetch_top_weekly(state)
        if top_text:
            post_feature(f"top_{today}", top_text, state=state)

    # Saturday: poll + listener track
    if now_wday == 5:
        post_poll(state)
        post_listener_track(state)

    # Daily: quiz
    post_quiz(state)

    # 14:00 slot: anime news
    if now_h == 14:
        post_anime_news(state)

    # 12:00, 15:00, 18:00 slots: rock music news
    if now_h in (12, 15, 18):
        post_rock_news(state)

    # --- Fetch & score news ---
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

        # non-gaming content penalty
        game = extract_game(item["title"])
        game_lower = game.lower()
        if not is_gaming_related(item["title"], item.get("desc", "")):
            score -= 50
        elif game and len(game_lower) > 3:
            score += 10  # bonus for having a named game

        # duplicate game name penalty (harder block)
        if game_lower and len(game_lower) > 3 and game_lower in recent_games:
            score -= 500

        # theme bonus (announce/sequel/drama = more interesting)
        theme = detect_theme(item["title"], item.get("desc", ""))
        if theme in ("announce", "sequel", "drama"):
            score += 30

        # duplicate title penalty (cross-source similar articles)
        item_title_lower = item["title"].lower()
        for rt in recent_titles:
            sim = title_similarity(item_title_lower, rt)
            if sim >= TITLE_SIMILARITY_THRESHOLD:
                score -= 300
                break

        item["_score"] = score
        item["_desc_len"] = desc_len
        item["_game"] = game
        unseen.append(item)

    for item in unseen:
        if is_hot(item):
            item["_score"] += 1000

    unseen.sort(key=lambda x: (-x["_score"], -x["_desc_len"]))
    print(f"Unseen: {len(unseen)}")

    # --- Moderation flow: send for approval instead of posting directly ---
    pending = state.get("pending_moderation")
    if pending:
        elapsed = time.time() - pending.get("time", 0)
        if elapsed > MODERATION_TTL:
            print(f"  Moderation TTL expired for: {pending.get('title', '?')[:60]}")
            state.pop("pending_moderation", None)
        else:
            reply = check_user_reply(state, pending.get("msg_id"))
            if reply is not None and reply.lower() in ("skip", "пропуск", "-", "нет", "no"):
                print(f"  Skipped by user: {pending.get('title', '?')[:60]}")
                state.pop("pending_moderation", None)
            elif reply is not None:
                cap = pending.get("caption", "")
                if reply:
                    sig = CHANNEL_SIGNATURE
                    before, after = cap.rsplit(sig, 1)
                    cap = f"{before}\n\U0001F4AC _{escape_md(reply)}_{sig}{after}"
                msg_id = send_post(
                    pending["title"], pending.get("desc", ""), pending["link"],
                    pending.get("img_url"), youtube_url=pending.get("youtube_url"),
                    game=pending.get("game", ""), custom_caption=cap,
                )
                if msg_id:
                    ids[pending.get("id")] = True
                    content_hashes[str(pending.get("content_hash"))] = True
                    posted_msgs[str(msg_id)] = {
                        "time": time.time(),
                        "title": pending.get("title", "?")[:60],
                        "source": pending.get("source", ""),
                        "game": pending.get("game", ""),
                    }
                    posted += 1
                    print(f"  Approved with comment: {pending.get('title', '?')[:60]}")
                    # Gaming OST — 2 random tracks
                    game = pending.get("game", "")
                    if game:
                        tmpdir = os.path.join(os.path.dirname(STATE_FILE), "audio_tmp")
                        os.makedirs(tmpdir, exist_ok=True)
                        ost_results = game_ost_tracks(game, tmpdir)
                        for path, real_title in ost_results:
                            if os.path.exists(path):
                                ext = os.path.splitext(path)[1] or ".webm"
                                mime_map = {
                                    ".mp3": "audio/mpeg", ".m4a": "audio/mp4",
                                    ".webm": "audio/webm", ".opus": "audio/opus",
                                    ".ogg": "audio/ogg", ".wav": "audio/wav",
                                }
                                mime = mime_map.get(ext.lower(), "audio/mpeg")
                                with open(path, "rb") as audio_f:
                                    r = tg("sendAudio", data={
                                        "chat_id": CHANNEL_ID,
                                        "title": f"{game} OST",
                                        "performer": game,
                                    }, files={"audio": (f"{game}_ost{ext}", audio_f, mime)}, timeout=30)
                                try:
                                    os.remove(path)
                                except Exception:
                                    pass
                                if r:
                                    print(f"  OST audio sent: {real_title[:50]} (msg#{r.json()['result']['message_id']})")
                state.pop("pending_moderation", None)
            else:
                print(f"  Waiting for approval: {pending.get('title', '?')[:60]}")
    else:
        # No pending — send best unseen to admin for moderation (max once per hour)
        last_sent = state.get("last_moderation_sent", 0)
        if time.time() - last_sent < MODERATION_INTERVAL:
            print(f"  Moderation cooldown ({MODERATION_INTERVAL}s), next preview in {int(MODERATION_INTERVAL - (time.time() - last_sent))}s")
        else:
            best = None
            for item in unseen[:1]:
                best = item
                break
            if best:
                best["game"] = best.get("_game") or extract_game(best["title"])
                cap = make_caption(best["title"], best.get("desc", ""), best["link"], best["game"])
                preview = f"\u23F3 **Пре-вью**\n\n{cap}\n\n_Напиши комментарий к этому посту — он пойдёт в канал_"
                img_url = find_post_image(best)
                if img_url:
                    try:
                        resp = requests.get(img_url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
                        if resp.status_code == 200 and is_hd(resp.content):
                            r = tg("sendPhoto", data={
                                "chat_id": ADMIN_CHAT_ID, "caption": preview, "parse_mode": "Markdown",
                            }, files={"photo": ("preview.jpg", resp.content, "image/jpeg")}, timeout=15)
                        else:
                            r = None
                    except Exception:
                        r = None
                else:
                    r = None
                if r is None:
                    r = tg("sendMessage", json={
                        "chat_id": ADMIN_CHAT_ID, "text": preview, "parse_mode": "Markdown",
                    }, timeout=10)
                if r:
                    msg_id = r.json()["result"]["message_id"]
                    state["pending_moderation"] = {
                        "msg_id": msg_id,
                        "title": best["title"],
                        "desc": best.get("desc", ""),
                        "link": best["link"],
                        "caption": cap,
                        "img_url": img_url,
                        "youtube_url": best.get("youtube_url"),
                        "id": best["id"],
                        "content_hash": best["content_hash"],
                        "source": best["source"],
                        "game": best["game"],
                        "time": time.time(),
                    }
                    state["last_moderation_sent"] = time.time()
                    print(f"  Sent for moderation: {best['title'][:60]}")
                    ids[best["id"]] = True
                    content_hashes[str(best["content_hash"])] = True

    # --- Daily digest ---
    last_digest = state.get("last_digest", "")
    unseen_count = len(unseen)
    if today != last_digest and unseen_count >= 5:
        state["last_digest"] = today
        digest_posts = unseen[:min(unseen_count, 5)]
        lines = [f"\U0001F4F0 **Дайджест**", ""]
        for i, d in enumerate(digest_posts, 1):
            header = shorten(d["title"], 55)
            snippet = shorten(d.get("desc", ""), 200)
            lines.append(f"{i}. **{header}**")
            if snippet:
                lines.append(f"   {snippet}")
            if d.get("link"):
                lines.append(f"   [\u041F\u043E\u0434\u0440\u043E\u0431\u043D\u0435\u0435]({d['link']})")
            lines.append("")
        lines.append("_\u0425\u043E\u0440\u043E\u0448\u0435\u0439 \u0438\u0433\u0440\u043E\u0432\u043E\u0439 \u043D\u0435\u0434\u0435\u043B\u0438!_")
        text = "\n".join(lines).strip()
        if len(text) > 1000:
            text = text[:997] + "..."
        try:
            r = tg("sendMessage", json={
                "chat_id": CHANNEL_ID,
                "text": text,
                "parse_mode": "Markdown",
            }, timeout=10)
            if r:
                print(f"  Digest sent ({len(digest_posts)} items)")
                posted += 1
        except Exception as e:
            print(f"  Digest failed: {e}")

    # --- Nikita's recommendation (once per day) ---
    post_nikita_recommendation(state)

    # --- Reply to channel comments ---
    reply_to_comments(state)

    # --- Cleanup old ids ---
    if len(ids) > 500:
        keep = set()
        for item in raw:
            keep.add(item["id"])
        for item in unseen:
            keep.add(item["id"])
        ids = {k: v for k, v in ids.items() if k in keep}

    # Trim posted_msgs to last 200
    if len(posted_msgs) > 200:
        sorted_msgs = sorted(posted_msgs.items(), key=lambda x: x[1].get("time", 0), reverse=True)
        state["posted_msgs"] = {k: v for k, v in sorted_msgs[:200]}

    # Trim deals_posted to last 100
    dp = state.get("deals_posted", {})
    if len(dp) > 100:
        sorted_dp = sorted(dp.items(), key=lambda x: x[1].get("time", 0), reverse=True)
        state["deals_posted"] = {k: v for k, v in sorted_dp[:100]}

    state["ids"] = ids
    keep_keys = {"ids", "stream_live_posted", "last_digest", "posted_msgs", "deals_posted", "features_posted", "watched_alerted", "nikita_posted", "anime_posted", "rock_posted", "last_deals_date", "content_hashes", "comment_offset", "_bot_id", "listener_track", "last_moderation_sent"}
    for k in list(state.keys()):
        if k not in keep_keys:
            del state[k]
    save_state(state)
    print(f"\nNew posts: {posted}")
    print(f"History: {len(ids)}")

if __name__ == "__main__":
    if "--stats" in sys.argv:
        state = load_state()
        posted = state.get("posted_msgs", {})
        print(f"=== Stats: {len(posted)} messages posted ===")
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
                bot = BOT_TOKEN
                requests.post(f"{TG_API}{bot}/sendMessage", json={
                    "chat_id": ADMIN_CHAT,
                    "text": f"\U0001F4A5 Bot crashed:\n\n{str(e)[:200]}",
                }, timeout=8)
            except Exception:
                pass
