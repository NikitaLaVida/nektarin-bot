import os
import re
import json
import requests

from bot.config import WIKI_UA, STATE_FILE
from bot.security import safe_download_image, is_safe_url
from bot.core import is_hd, extract_game


_PINTEREST_SESSION = None


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


def goha_image(desc):
    m = re.search(r'https?://[^\s"<>]+\.(?:jpg|jpeg|png|webp)', desc)
    if m:
        return m.group(0)
    return None


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
                    "action": "query", "list": "search",
                    "srsearch": game_name + " (video game)" if lang == "en" else game_name + " (игра)",
                    "srlimit": 3, "format": "json",
                },
                timeout=6, headers={"User-Agent": WIKI_UA},
            )
            pages = search.json().get("query", {}).get("search", [])
            if not pages:
                continue
            titles = [p["title"] for p in pages[:2]]
            img_query = requests.get(
                f"https://{domain}/w/api.php",
                params={
                    "action": "query", "titles": "|".join(titles),
                    "prop": "pageprops|pageimages", "ppprop": "wikibase_item",
                    "pithumbsize": 1920, "format": "json", "redirects": 1,
                },
                timeout=6, headers={"User-Agent": WIKI_UA},
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
                        "action": "wbgetentities", "ids": qid,
                        "props": "claims", "format": "json",
                    },
                    timeout=6, headers={"User-Agent": WIKI_UA},
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
            params={"term": game_name[:40], "l": "english", "cc": "us"}, timeout=8)
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
            params={"key": key, "search": game_name[:40], "page_size": 1}, timeout=8)
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
            f"https://www.steamgriddb.com/api/v2/search/autocomplete/{requests.utils.quote(game_name[:30])}",
            headers={"Authorization": f"Bearer {key}"}, timeout=8)
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
            params={"dimensions": "460x215,920x430", "mimes": "image/png,image/jpeg"}, timeout=8)
        if grids.status_code == 200:
            items = grids.json().get("data", [])
            if items:
                return items[0].get("url")
    except Exception:
        pass
    return None


def pinterest_image(game_name):
    global _PINTEREST_SESSION
    try:
        if _PINTEREST_SESSION is None:
            s = requests.Session()
            s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
            s.get('https://www.pinterest.com/', timeout=10)
            s.headers.update({
                'X-CSRFToken': s.cookies.get('csrftoken', ''),
                'X-Pinterest-AppState': 'active',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': 'https://www.pinterest.com/',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
            })
            _PINTEREST_SESSION = s
        query = f"{game_name} game cover art"
        post_data = {
            'source_url': '/search/pins/?q=' + requests.utils.quote(query),
            'data': json.dumps({
                'options': {'query': query, 'scope': 'pins', 'page_size': 3, 'bookmarks': []},
                'context': {},
            }, ensure_ascii=False),
        }
        r = _PINTEREST_SESSION.post(
            'https://www.pinterest.com/resource/SearchResource/get/',
            data=post_data, timeout=15,
        )
        if r.status_code != 200:
            _PINTEREST_SESSION = None
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
        _PINTEREST_SESSION = None
    return None


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


def find_post_image(item):
    rss_img = item.get("rss_img")
    if rss_img and is_safe_url(rss_img):
        try:
            img_bytes = safe_download_image(rss_img, timeout=5)
            if img_bytes and is_hd(img_bytes):
                return rss_img
        except Exception:
            pass
    game = item.get("_game") or extract_game(item["title"])
    try:
        return find_image(item["title"], item.get("desc", ""), item["source"], game)
    except Exception:
        pass
    return None
