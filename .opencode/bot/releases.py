import time
from datetime import datetime, timedelta, date

import requests

from bot.core import tg, log


_MONTHS_RU = ["", "янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]


def fetch_steam_coming_soon() -> list[dict]:
    try:
        r = requests.get(
            "https://store.steampowered.com/api/featuredcategories",
            params={"cc": "RU", "l": "russian"},
            timeout=10,
        )
        if r.status_code != 200:
            log(f"  Steam coming_soon: HTTP {r.status_code}")
            return []
        data = r.json()
        items = data.get("coming_soon", {}).get("items", [])
        result = []
        for item in items:
            name = item.get("name", "")
            appid = item.get("id", 0)
            if not name or not appid:
                continue
            release_date = None
            rd = item.get("release_date", {})
            if isinstance(rd, dict):
                date_str = rd.get("coming_soon_date", "") or rd.get("date", "")
                if date_str:
                    try:
                        release_date = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
                    except ValueError:
                        pass
            result.append({
                "name": name,
                "date": release_date,
                "appid": appid,
                "url": f"https://store.steampowered.com/app/{appid}",
            })
        return result
    except Exception as e:
        log(f"  Steam coming_soon err: {e}")
        return []


def fetch_curated_releases() -> list[dict]:
    from bot.config import UPCOMING_RELEASES
    today = date.today()
    result = []
    for entry in UPCOMING_RELEASES:
        try:
            d = datetime.strptime(entry["date"], "%Y-%m-%d").date()
            if d >= today - timedelta(days=1):
                result.append({
                    "name": entry["name"],
                    "date": d,
                    "url": entry.get("url", ""),
                    "platform": entry.get("platform", ""),
                })
        except (ValueError, KeyError):
            log(f"  Curated release misformat: {entry}")
    return result


def _format_calendar(steam_items: list[dict], curated: list[dict], today: date) -> str | None:
    end = today + timedelta(days=7)
    releases = []
    seen = set()

    for item in steam_items:
        if item["date"] and today <= item["date"] <= end:
            key = item["name"].lower()
            if key not in seen:
                seen.add(key)
                releases.append({
                    "name": item["name"],
                    "date": item["date"],
                    "link": item["url"],
                    "platform": "Steam",
                })
    for item in curated:
        key = item["name"].lower()
        if key not in seen:
            seen.add(key)
            releases.append({
                "name": item["name"],
                "date": item["date"],
                "link": item.get("url", ""),
                "platform": item.get("platform", ""),
            })

    if not releases:
        return None

    releases.sort(key=lambda x: x["date"])
    lines = ["\U0001F4C5 <b>Релизы этой недели</b>", ""]
    prev_date = None
    for r in releases:
        d = r["date"]
        label = f"{d.day} {_MONTHS_RU[d.month]}"
        if d != prev_date:
            lines.append(f"\n\u2501 <b>{label}</b> \u2501")
            prev_date = d
        name = r["name"]
        plat = f" ({r['platform']})" if r.get("platform") else ""
        link = f" <a href=\"{r['link']}\">\u2139</a>" if r.get("link") else ""
        lines.append(f"\U0001F539 {name}{plat}{link}")
    return "\n".join(lines)


def post_release_calendar() -> bool:
    today = date.today()
    steam = fetch_steam_coming_soon()
    curated = fetch_curated_releases()
    log(f"  Release calendar: {len(steam)} steam + {len(curated)} curated")
    msg = _format_calendar(steam, curated, today)
    if not msg:
        log("  Release calendar: nothing this week")
        return False
    try:
        from bot.config import CHANNEL_ID
        tg("sendMessage", json={
            "chat_id": CHANNEL_ID, "text": msg,
            "parse_mode": "HTML", "disable_web_page_preview": False,
        }, timeout=10)
        log("  Release calendar posted")
        return True
    except Exception as e:
        log(f"  Release calendar post err: {e}")
        return False
