import os
import sys
import json
import feedparser
import requests
import time
import re
import random
from html import unescape

BOT_TOKEN = "8879790921:AAE9hwgmrpSoa5wr7NCXA6H9CBDp6JgC3s0"
CHANNEL_ID = "@NektarinGaming"
ADMIN_CHAT = "@SPVRTVN"
MAX_POSTS = 3
POST_DELAY = 1800  # секунд между постами (30 мин)
POST_DELAY_JITTER = 300  # +-5 мин рандома
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
STATE_FILE = os.environ.get("STATE_FILE", os.path.expanduser("~/.opencode/bot_state.json"))
SILENT_HOURS = range(0, 10)  # не постить с 00:00 до 09:59

TWITCH_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"

REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET", "")

RSS_FEEDS = [
    ("https://www.igromania.ru/rss/news.xml", "igromania", 10),
    ("https://www.goha.ru/rss/news", "goha", 5),
    ("https://www.goha.ru/rss/videogames", "goha_videogames", 5),
    ("https://www.goha.ru/rss/industry", "goha_industry", 3),
    ("https://www.playground.ru/rss/news.xml", "playground", 10),
    ("https://stopgame.ru/news/rss.xml", "stopgame", 7),
    ("https://kanobu.ru/rss/main.rss", "kanobu", 5),
]

WIKI_UA = "GamingNewsBot/1.0 (https://t.me/NektarinGaming)"

IRONIC_OUTROS = []

THEME_WORDS = {
    "sales": ["продаж", "тираж", "миллион", "копий", "рекорд", "миллиард", "выручк", "прибыл", "заработ"],
    "delay": ["отложен", "перенесен", "задержк", "отсрочк", "не выйдет", "перенос", "отмена"],
    "console": ["эксклюзив", "консоль", "PlayStation", "PS5", "Xbox", "Nintendo", "Switch"],
    "sequel": ["сиквел", "продолжение", "часть", "новая", "триквел", "ремейк"],
    "drama": ["скандал", "критик", "гнев", "недовольн", "петицию", "требуют", "кризис", "увольнени"],
}

GENRE_TAGS = {
    "шутер", "хоррор", "рогалик", "симулятор", "стратеги", "rpg", "экшн",
    "файтинг", "гонк", "платформер", "головоломк", "песочниц", "выживани",
}

PLATFORMS = ["PS5", "PS4", "Xbox Series", "Xbox", "Switch", "PC", "Steam"]

HASHTAGS = ""
CHANNEL_FOOTER = ""

WATCHED_GAMES = [
    "elden ring", "witcher", "gta", "cyberpunk",
    "red dead", "god of war", "silksong",
    "half-life", "mass effect", "dragon age",
    "disco elysium", "baldurs gate", "baldur's gate",
    "starfield", "stalker", "fallout",
]


def send_error(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
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


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"ids": {}}

def save_state(state):
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
                h = hash(norm)
                if h in seen_hashes:
                    continue
                seen_hashes.add(h)
                items.append({
                    "title": title,
                    "desc": desc,
                    "link": link,
                    "source": source,
                    "youtube_url": youtube_url,
                    "id": "".join(c for c in link if c.isalnum()),
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
        "стал", "стала", "отложен", "перенесен", "назван", "снова", "уже",
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
    game = re.sub(r"\s+\d+(?:\.\d+)?$", "", game).strip()
    game = _EX_GAME_TRAIL.sub("", game).strip()
    game = re.sub(r"\s+[А-ЯЁ][а-яё]+$", "", game).strip()
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
                    "pithumbsize": 800,
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
                            return f"https://commons.wikimedia.org/wiki/Special:FilePath/{img_name}?width=800"
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
                    return f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg"
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
        if r.status_code != 200:
            return None
        results = r.json().get("results", [])
        if not results:
            return None
        gid = results[0].get("id")
        if not gid:
            return None
        scr = requests.get(f"https://api.rawg.io/api/games/{gid}/screenshots",
            params={"key": key}, timeout=6)
        if scr.status_code == 200:
            shots = scr.json().get("results", [])
            if shots:
                return shots[0].get("image")
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


# ---- Templates ----

def pick(seq):
    return random.choice(seq) if seq else ""

def fmt_pf(platforms):
    if not platforms:
        return ""
    return " на " + "/".join(platforms[:3])

COMMENTS = [
    "Ну такое.", "2026, детка.", "Классика жанра.",
    "Без комментариев.", "Ждём-с.", "Обычные дела игропрома.",
    "Держитесь там.", "Ну а вы чего ждали?", "Патч уже в пути.",
    "Капитализм, детка.", "Жизнь боль.", "Денди надёжнее.",
]

def template_sales(title, desc, game, numbers, platforms, genre):
    s = shorten(desc, 250)
    n = numbers[0] if numbers else "внушительное количество"
    comment = pick(COMMENTS)
    body = pick([
        f"Продажи {game} достигли отметки в {n} копий. {s} {comment}",
        f"{s} За {game} уже отдали {n} копий. {comment}",
        f"Коммерческий успех: {game} разошлась тиражом в {n}. {s} {comment}",
    ])
    return [body.strip()]

def template_delay(title, desc, game, numbers, platforms, genre):
    s = shorten(desc, 250)
    comment = pick(COMMENTS)
    body = pick([
        f"Плохие новости: {game} отложили. {s} {comment}",
        f"Релиз {game} перенесён. {s} {comment}",
        f"{s} Когда выйдет {game} — пока неясно. {comment}",
    ])
    return [body.strip()]

def template_sequel(title, desc, game, numbers, platforms, genre):
    s = shorten(desc, 250)
    comment = pick(COMMENTS)
    body = pick([
        f"Продолжение: {game}. {s} {comment}",
        f"А вот и сиквел {game}. {s} {comment}",
        f"{game} — возвращение легенды. {s} {comment}",
    ])
    return [body.strip()]

def template_console(title, desc, game, numbers, platforms, genre):
    s = shorten(desc, 250)
    comment = pick(COMMENTS)
    body = pick([
        f"Консольные новости: {game}. {s} {comment}",
        f"{game}{fmt_pf(platforms)}. {s} {comment}",
        f"{s} Речь о {game}. {comment}",
    ])
    return [body.strip()]

def template_drama(title, desc, game, numbers, platforms, genre):
    s = shorten(desc, 250)
    comment = pick(COMMENTS)
    body = pick([
        f"Скандал: {game}. {s} {comment}",
        f"Вокруг {game} разгорается драма. {s} {comment}",
        f"{game} снова в центре внимания. {s} {comment}",
    ])
    return [body.strip()]

def template_generic(title, desc, game, numbers, platforms, genre):
    s = shorten(desc, 250)
    comment = pick(COMMENTS)
    body = pick([
        f"{title}. {s} {comment}",
        f"{s} Речь о {game}. {comment}",
        f"{game}. {s} {comment}",
        f"{s} {comment}",
    ])
    return [body.strip()]


TEMPLATES = {
    "sales": template_sales,
    "delay": template_delay,
    "sequel": template_sequel,
    "console": template_console,
    "drama": template_drama,
    "generic": template_generic,
}


def make_caption(title, desc, link, source):
    if not desc:
        desc = title

    title = escape_md(title)
    desc = escape_md(desc)

    game = extract_game(title)
    game = escape_md(game)
    numbers = extract_numbers(desc)
    platforms = extract_platforms(title + " " + desc)
    genre = detect_genre(desc)
    theme = detect_theme(title, desc)

    builder = TEMPLATES.get(theme, template_generic)
    caption = builder(title, desc, game, numbers, platforms, genre)[0]

    if len(caption) > 900:
        caption = caption[:897] + "..."
    return caption


# ---- Image lookup v2 ----

def find_image(title, desc, source):
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

    try:
        img = wiki_image(clean_name)
        if img:
            print(f"  Found Wikipedia image")
            return img
    except Exception as e:
        print(f"  Wiki error: {e}")

    return None


def send_post(title, desc, link, source, img_url, youtube_url=None):
    caption = make_caption(title, desc, link, source)
    caption += CHANNEL_FOOTER + HASHTAGS

    is_trailer_post = youtube_url and is_trailer(title)
    base = f"https://api.telegram.org/bot{BOT_TOKEN}/"

    # Trailer post — send YouTube link as video embed
    if is_trailer_post:
        try:
            r = requests.post(base + "sendVideo", json={
                "chat_id": CHANNEL_ID,
                "video": youtube_url,
                "caption": caption,
                "parse_mode": "Markdown",
            }, timeout=15)
            if r.status_code == 200:
                msg_id = r.json()["result"]["message_id"]
                print(f"  Sent trailer video: {title[:60]} (msg#{msg_id})")
                return msg_id
            print(f"  Trailer video send failed ({r.status_code})")
        except Exception as e:
            print(f"  Trailer video err: {e}")

    # Normal image
    if img_url:
        try:
            img_data = requests.get(img_url, timeout=10)
            if img_data.status_code == 200:
                files = {"photo": ("image.jpg", img_data.content, "image/jpeg")}
                payload = {
                    "chat_id": CHANNEL_ID,
                    "caption": caption,
                    "parse_mode": "Markdown",
                }
                r = requests.post(base + "sendPhoto", data=payload, files=files, timeout=20)
                if r.status_code == 200:
                    msg_id = r.json()["result"]["message_id"]
                    print(f"  Sent with image: {title[:60]} (msg#{msg_id})")
                    return msg_id
            print(f"  Image failed ({img_data.status_code}), sending text")
        except Exception as e:
            print(f"  Image err: {e}")

    payload = {
        "chat_id": CHANNEL_ID,
        "text": caption,
        "parse_mode": "Markdown",
    }
    r = requests.post(base + "sendMessage", json=payload, timeout=10)
    if r.status_code == 200:
        msg_id = r.json()["result"]["message_id"]
        print(f"  Sent: {title[:60]} (msg#{msg_id})")
        return msg_id
    print(f"  Send failed: {r.text[:150]}")
    return None


def send_live_notification(title, game):
    text = (
        f"\U0001F534 **Я В ЭФИРЕ!**\n\n"
        f"**{title}**\n"
        f"\u2500" * 20 + "\n"
        f"Игра: **{game}**\n\n"
        f"Смотреть: https://twitch.tv/NektarinGaming"
    )
    try:
        r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
            "chat_id": CHANNEL_ID,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        }, timeout=10)
        if r.status_code == 200:
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
                    from datetime import datetime, timezone
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
            t = g["title"]
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
            t = g["title"]
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
            lines.append(f"\U0001F539 [{d['title']} -{d['discount']}%](https://store.steampowered.com/app/{appid}/)")
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

    base = f"https://api.telegram.org/bot{BOT_TOKEN}/"
    r = requests.post(base + "sendMessage", json={
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }, timeout=12)
    if r.status_code == 200:
        msg_id = r.json()["result"]["message_id"]
        print(f"  Deals batch sent ({count} items, msg#{msg_id})")
        return msg_id
    print(f"  Deals batch failed: {r.text[:150]}")
    send_error(f"Deals batch failed: {r.text[:150]}")
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
                from datetime import datetime, timezone
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


# ---- Reddit Meme ----


REDDIT_SUBS = ["gaming", "gamecollecting", "pcgaming"]


def _reddit_token():
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        return None
    try:
        r = requests.post("https://www.reddit.com/api/v1/access_token",
            auth=(REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET),
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": "GamingNewsBot/1.0"},
            timeout=8)
        if r.status_code == 200:
            return r.json().get("access_token")
    except Exception as e:
        print(f"  Reddit token err: {e}")
    return None


def fetch_meme():
    token = _reddit_token()
    if not token:
        print("  Reddit: no token (set REDDIT_CLIENT_ID/CLIENT_SECRET)")
        return None
    seen_ids = set()
    for sub in REDDIT_SUBS:
        try:
            r = requests.get(
                f"https://oauth.reddit.com/r/{sub}/hot",
                params={"limit": 15},
                timeout=8,
                headers={"User-Agent": "GamingNewsBot/1.0", "Authorization": f"Bearer {token}"},
            )
            if r.status_code != 200:
                continue
            for post in r.json().get("data", {}).get("children", []):
                data = post.get("data", {})
                pid = data.get("id", "")
                if pid in seen_ids:
                    continue
                seen_ids.add(pid)
                url = data.get("url", "")
                ext = url.split(".")[-1].lower().split("?")[0] if "." in url else ""
                if ext not in ("jpg", "jpeg", "png", "gif"):
                    continue
                title = data.get("title", "")
                permalink = data.get("permalink", "")
                post_url = f"https://reddit.com{permalink}" if permalink else ""
                score = data.get("score", 0)
                return {
                    "image_url": url,
                    "title": title,
                    "post_url": post_url,
                    "score": score,
                    "subreddit": sub,
                }
        except Exception as e:
            print(f"  Reddit {sub} error: {e}")
    return None


def send_meme_post(meme):
    text = f"{meme['title']}\n\n\U0001F517 [{meme['subreddit']}]({meme['post_url']}) \u2022 \u2B50 {meme['score']}"
    if len(text) > 1000:
        text = text[:997] + "..."
    try:
        img = requests.get(meme["image_url"], timeout=10)
        if img.status_code != 200:
            return None
        ext = meme["image_url"].split(".")[-1].split("?")[0] or "jpg"
        base = f"https://api.telegram.org/bot{BOT_TOKEN}/"
        r = requests.post(base + "sendPhoto", data={
            "chat_id": CHANNEL_ID,
            "caption": text,
            "parse_mode": "Markdown",
        }, files={"photo": (f"meme.{ext}", img.content, f"image/{ext}")}, timeout=15)
        if r.status_code == 200:
            msg_id = r.json()["result"]["message_id"]
            print(f"  Meme posted: {meme['title'][:50]} (msg#{msg_id})")
            return msg_id
    except Exception as e:
        print(f"  Meme post err: {e}")
    return None


def fetch_upcoming_releases():
    try:
        r = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": "upcoming video games 2026",
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


def make_channel_stats(state):
    all_msgs = state.get("posted_msgs", {})
    total = len(all_msgs)
    if total == 0:
        return None
    times = [v.get("time", 0) for v in all_msgs.values()]
    first = time.strftime("%d.%m", time.localtime(min(times))) if times else "?"
    lines = [
        f"\U0001F4CA **\u0421\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043A\u0430 \u043A\u0430\u043D\u0430\u043B\u0430**",
        "",
        f"\U0001F4F0 \u0412\u0441\u0435\u0433\u043E \u043F\u043E\u0441\u0442\u043E\u0432: {total}",
        f"\U0001F4C5 \u0421 \u043F\u0435\u0440\u0432\u043E\u0433\u043E \u043F\u043E\u0441\u0442\u0430: {first}",
    ]
    return "\n".join(lines)


def post_feature(feature_key, text, image_url=None, state=None):
    features_posted = state.setdefault("features_posted", {})
    if feature_key in features_posted:
        return None
    base = f"https://api.telegram.org/bot{BOT_TOKEN}/"
    if image_url:
        try:
            img = requests.get(image_url, timeout=8)
            if img.status_code == 200:
                r = requests.post(base + "sendPhoto", data={
                    "chat_id": CHANNEL_ID, "caption": text, "parse_mode": "Markdown",
                }, files={"photo": ("feature.jpg", img.content, "image/jpeg")}, timeout=15)
                if r.status_code == 200:
                    features_posted[feature_key] = {"time": time.time()}
                    print(f"  Feature posted: {feature_key}")
                    return r.json()["result"]["message_id"]
        except Exception:
            pass
    r = requests.post(base + "sendMessage", json={
        "chat_id": CHANNEL_ID, "text": text, "parse_mode": "Markdown",
    }, timeout=10)
    if r.status_code == 200:
        features_posted[feature_key] = {"time": time.time()}
        print(f"  Feature posted (text): {feature_key}")
        return r.json()["result"]["message_id"]
    return None


def main():
    token = os.environ.get("TG_BOT_TOKEN", BOT_TOKEN)
    if not token:
        print("Error: no bot token")
        return
    globals()["BOT_TOKEN"] = token

    print("=== Gaming News Bot v3 (info-style) ===\n")

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

    # --- Night mode check ---
    now_h = time.localtime().tm_hour
    if now_h in SILENT_HOURS:
        print(f"Night mode ({now_h}:00 — {max(SILENT_HOURS)+1}:00), skipping news")
        save_state(state)
        return

    posted = 0

    # --- Deals & free games (posted immediately, outside queue) ---
    deals_posted = state.setdefault("deals_posted", {})
    steam_deals = fetch_steam_deals()
    epic_free = fetch_epic_free_games()
    gog_free = fetch_gog_free_games()

    any_new = False
    for deal in steam_deals:
        key = f"st_{deal['appid']}_{deal['discount']}"
        if key not in deals_posted:
            deals_posted[key] = {"title": deal["title"], "time": time.time()}
            any_new = True
    for fg in epic_free:
        key = f"ep_{fg['title'].lower().replace(' ', '_')}"
        if key not in deals_posted:
            deals_posted[key] = {"title": fg["title"], "time": time.time()}
            any_new = True
    for fg in gog_free:
        key = f"gog_{fg['title'].lower().replace(' ', '_')}"
        if key not in deals_posted:
            deals_posted[key] = {"title": fg["title"], "time": time.time()}
            any_new = True

    if any_new:
        msg_id = send_deals_batch(steam_deals, epic_free, gog_free)
        if msg_id:
            posted += 1

    # --- Watched games on sale ---
    watched_matched = []
    for deal in steam_deals:
        t = deal["title"].lower()
        for w in WATCHED_GAMES:
            if w.lower() in t:
                watched_matched.append(deal)
                break
    if watched_matched:
        lines = ["\U0001F525 **Игра из списка ожидания в продаже!**", ""]
        for d in watched_matched:
            appid = d["appid"]
            lines.append(f"\U0001F539 [{d['title']} -{d['discount']}%](https://store.steampowered.com/app/{appid}/)")
            lines.append(f"   \u20BD {d['final_price']:.0f} вместо {d['original_price']:.0f}")
            if d.get("expires"):
                lines.append(f"   \U0001F512 до {d['expires']}")
        text = "\n".join(lines)
        try:
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                "chat_id": ADMIN_CHAT,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False,
            }, timeout=8)
            print(f"  Watched game alert sent ({len(watched_matched)} items)")
        except Exception as e:
            print(f"  Watched alert err: {e}")

    # --- Scheduled features ---
    now_wday = time.localtime().tm_wday
    today = time.strftime("%Y-%m-%d")
    week = time.strftime("%Y-W%V")

    # Monday: releases of the week
    if now_wday == 0:
        releases = fetch_upcoming_releases()
        if releases:
            text = make_releases_post(releases)
            post_feature(f"releases_{today}", text, state=state)

    # Friday: weekend picks
    if now_wday == 4:
        steam_deals = fetch_steam_deals()
        epic_free = fetch_epic_free_games()
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

    # Daily: reddit meme
    features_posted = state.setdefault("features_posted", {})
    meme_key = f"meme_{today}"
    if meme_key not in features_posted:
        meme = fetch_meme()
        if meme:
            msg_id = send_meme_post(meme)
            if msg_id:
                features_posted[meme_key] = {"time": time.time()}
                posted += 1

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

    # --- Fetch & score news ---
    raw = fetch_news()
    print(f"\nTotal raw items: {len(raw)}")

    unseen = []
    for item in raw:
        if item["id"] in ids:
            continue
        score = 0
        desc_len = len(item.get("desc", ""))
        score += min(desc_len / 5, 20)
        if extract_numbers(item.get("desc", "")):
            score += 5
        if extract_platforms(item["title"] + " " + item.get("desc", "")):
            score += 3
        item["_score"] = score
        item["_desc_len"] = desc_len
        unseen.append(item)

    for item in unseen:
        if is_hot(item):
            item["_score"] += 1000

    unseen.sort(key=lambda x: (-x["_score"], -x["_desc_len"]))
    print(f"Unseen: {len(unseen)}")

    posted_msgs = state.setdefault("posted_msgs", {})
    for item in unseen[:MAX_POSTS]:
        img_url = find_image(item["title"], item.get("desc", ""), item["source"])
        msg_id = send_post(
            item["title"], item["desc"], item["link"],
            item["source"], img_url, item.get("youtube_url"),
        )
        if msg_id:
            ids[item["id"]] = True
            posted_msgs[str(msg_id)] = {
                "title": item["title"][:50],
                "time": time.time(),
                "source": item["source"],
            }
            posted += 1
            if posted < MAX_POSTS:
                remaining = unseen[posted:MAX_POSTS]
                if any(is_hot(r) for r in remaining):
                    print(f"  Hot item in queue, skipping delay!")
                else:
                    delay = POST_DELAY + random.randint(-POST_DELAY_JITTER, POST_DELAY_JITTER)
                    print(f"  Waiting {delay}s before next post...")
                    time.sleep(delay)

    # --- Daily digest ---
    today = time.strftime("%Y-%m-%d")
    last_digest = state.get("last_digest", "")
    unseen_count = len(unseen)
    if today != last_digest and unseen_count >= 5:
        state["last_digest"] = today
        digest_posts = unseen[:min(unseen_count, 5)]
        lines = [f"\U0001F4F0 **Дайджест**", ""]
        for i, d in enumerate(digest_posts, 1):
            header = shorten(d["title"], 55)
            snippet = shorten(d.get("desc", ""), 120)
            lines.append(f"{i}. **{header}**")
            if snippet:
                lines.append(f"   {snippet}")
            lines.append("")
        lines.append(f"_\u0421\u043F\u0430\u0441\u0438\u0431\u043E \u0437\u0430 \u0432\u043D\u0438\u043C\u0430\u043D\u0438\u0435. \u0418\u0433\u0440\u0430\u0439\u0442\u0435 \u0432 \u0445\u043E\u0440\u043E\u0448\u0435\u0435._")
        text = "\n".join(lines).strip()
        if len(text) > 1000:
            text = text[:997] + "..."
        try:
            r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                "chat_id": CHANNEL_ID,
                "text": text,
                "parse_mode": "Markdown",
            }, timeout=10)
            if r.status_code == 200:
                print(f"  Digest sent ({len(digest_posts)} items)")
                posted += 1
        except Exception as e:
            print(f"  Digest failed: {e}")

    # --- Cleanup old ids ---
    if len(ids) > 500:
        keep = set()
        for item in raw:
            keep.add(item["id"])
        for item in unseen:
            keep.add(item["id"])
        ids = {k: v for k, v in ids.items() if k in keep}

    # Trim posted_msgs to last 200
    posted_msgs = state.get("posted_msgs", {})
    if len(posted_msgs) > 200:
        sorted_msgs = sorted(posted_msgs.items(), key=lambda x: x[1].get("time", 0), reverse=True)
        state["posted_msgs"] = {k: v for k, v in sorted_msgs[:200]}

    # Trim deals_posted to last 100
    dp = state.get("deals_posted", {})
    if len(dp) > 100:
        sorted_dp = sorted(dp.items(), key=lambda x: x[1].get("time", 0), reverse=True)
        state["deals_posted"] = {k: v for k, v in sorted_dp[:100]}

    state["ids"] = ids
    keep_keys = {"ids", "stream_live_posted", "last_digest", "posted_msgs", "deals_posted", "features_posted"}
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
    elif "--once" in sys.argv:
        main()
    else:
        import time
        while True:
            main()
            print("Sleeping 2 hours...")
            time.sleep(7200)
