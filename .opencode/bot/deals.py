import re
import time
from datetime import datetime, timezone
import requests
from bot.config import CHANNEL_ID, CHANNEL_SIGNATURE
from bot.core import tg, escape_html, clean


def fetch_epic_free_games():
    try:
        r = requests.get(
            "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions",
            params={"locale": "ru-RU", "country": "RU"}, timeout=12,
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
                except Exception as e:
                    print(f"  Epic date parse err: {e}")
                    end_readable = end_str[:10]
            games.append({
                "title": title, "desc": desc[:200], "image": image,
                "url": url, "end_date": end_readable, "source": source,
            })
        return games
    except Exception as e:
        print(f"  Epic free games error: {e}")
        return []


def fetch_gog_free_games():
    try:
        r = requests.get("https://www.gog.com/games/ajax/filtered",
            params={"mediaType": "game", "price": "free", "limit": 10}, timeout=10)
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
            games.append({"title": title, "url": url, "image": image})
        return games
    except Exception as e:
        print(f"  GOG free games error: {e}")
        return []


def send_deals_batch(steam_deals, epic_free, gog_free):
    lines = ["\U0001F4F0 <b>Акции и раздачи</b>", ""]
    count = 0
    if epic_free:
        lines.append("\U0001F381 <b>Epic Games</b>")
        for g in epic_free:
            if g.get("url"):
                lines.append(f'\U0001F539 <a href="{g["url"]}">{escape_html(g["title"])}</a>')
            else:
                lines.append(f"\U0001F539 {escape_html(g['title'])}")
            if g.get("end_date"):
                lines.append(f"   \U0001F512 до {g['end_date']}")
            count += 1
        lines.append("")
    if gog_free:
        lines.append("\U0001F4F0 <b>GOG</b>")
        for g in gog_free:
            if g.get("url"):
                lines.append(f'\U0001F539 <a href="{g["url"]}">{escape_html(g["title"])}</a>')
            else:
                lines.append(f"\U0001F539 {escape_html(g['title'])}")
            count += 1
        lines.append("")
    if steam_deals:
        lines.append("\U0001F3AE <b>Steam</b>")
        for d in sorted(steam_deals, key=lambda x: -x["discount"]):
            app_link = f'https://store.steampowered.com/app/{d["appid"]}/'
            emoji = "\U0001F525" if d["discount"] >= 90 else "\U0001F539"
            lines.append(f'{emoji} <a href="{app_link}">{escape_html(d["title"])} -{d["discount"]}%</a>')
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
        "chat_id": CHANNEL_ID, "text": text,
        "parse_mode": "HTML", "disable_web_page_preview": False,
    }, timeout=12)
    if r:
        msg_id = r.json()["result"]["message_id"]
        print(f"  Deals batch sent ({count} items, msg#{msg_id})")
        return msg_id
    print(f"  Deals batch failed")
    from bot.core import send_error
    send_error("Deals batch failed")
    return None


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
                "appid": appid, "title": name, "discount": dp,
                "original_price": orig, "final_price": final,
                "image": item.get("large_capsule_image") or item.get("small_capsule_image"),
                "expires": expires_str,
            })
        return deals
    except Exception as e:
        print(f"  Steam deals error: {e}")
        return []
