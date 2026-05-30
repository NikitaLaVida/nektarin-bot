import os
import json

BOT_TOKEN = ""
TEST_MODE = False
CHANNEL_ID = "@NektarinGaming"
ADMIN_CHAT = "@SPVRTVN"
ADMIN_CHAT_ID = 710307297

_CFG = {}
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bot_config.json")
if os.path.exists(_CONFIG_PATH):
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as _f:
            _CFG = json.load(_f)
        BOT_TOKEN = _CFG.get("bot_token", BOT_TOKEN)
        TEST_MODE = _CFG.get("test_mode", TEST_MODE)
        CHANNEL_ID = _CFG.get("channel_id", CHANNEL_ID)
        ADMIN_CHAT = _CFG.get("admin_chat", ADMIN_CHAT)
        ADMIN_CHAT_ID = _CFG.get("admin_chat_id", ADMIN_CHAT_ID)
    except Exception as _e:
        print(f"  Config load err: {_e}")

MAX_POSTS = 2
_SEP = '\u2581'
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
_DATA_DIR = os.environ.get("DATA_DIR", "")
if not _DATA_DIR:
    _DATA_DIR = os.path.expanduser("~/.opencode")
STATE_FILE = os.path.join(_DATA_DIR, "bot_state.json")
LOG_FILE = os.path.join(_DATA_DIR, "bot.log")
SILENT_HOURS = range(0, 10)

RSS_FEEDS = [
    ("https://www.igromania.ru/rss/news.xml", "igromania", 10),
    ("https://www.goha.ru/rss/news", "goha", 5),
    ("https://www.goha.ru/rss/videogames", "goha_videogames", 5),
    ("https://www.goha.ru/rss/industry", "goha_industry", 3),
    ("https://www.goha.ru/rss/articles", "goha_articles", 3),
    ("https://www.playground.ru/rss/news.xml", "playground", 10),
    ("https://kanobu.ru/rss/articles.full.xml", "kanobu", 5),
    ("https://dtf.ru/rss/all", "dtf", 5),
    ("https://app2top.ru/feed/", "app2top", 5),
    ("https://habr.com/ru/rss/hubs/games/news/", "habr_games", 5),
    ("https://mmorpg-blog.ru/feed/", "mmorpgblog", 3),
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
MODERATION_TTL = 86400
MODERATION_INTERVAL = 3600
_PROXY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bot_proxy.txt")
TG_PROXY = os.environ.get("TG_PROXY", "")
if not TG_PROXY and os.path.exists(_PROXY_FILE):
    with open(_PROXY_FILE, "r", encoding="utf-8") as _f:
        TG_PROXY = _f.read().strip()

MAX_CAPTION_LEN = 900
MAX_DESC_LEN = 250
MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_RSS_TEXT_LEN = 2000

WATCHED_GAMES = [
    "elden ring", "witcher", "gta", "cyberpunk",
    "red dead", "god of war", "silksong",
    "half-life", "mass effect", "dragon age",
    "disco elysium", "baldurs gate", "baldur's gate",
    "starfield", "stalker", "fallout",
]

CHANNEL_SIGNATURE = _CFG.get("channel_signature", "\n— @NektarinGaming")

_LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".bot.lock")
_GLOBAL_STATE = {}

def set_global_state(key, value):
    _GLOBAL_STATE[key] = value

def get_global_state(key, default=None):
    return _GLOBAL_STATE.get(key, default)

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

BOILERPLATE = [
    r"Читать далее.*$", r"Читать дальше.*$", r"Читать полностью.*$",
    r"Подробнее.*$", r"Подробно.*$",
    r"Источник:.*$", r"Ссылка на источник.*$",
    r"Смотрите также.*$",
]

YOUTUBE_RE_SRC = r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})"

TRAILER_KEYWORDS = ["трейлер", "тизер", "gameplay", "trailer", "teaser", "геймплей"]
