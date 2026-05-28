import os
import time
import sys
import requests
import signal

from bot.config import (
    STATE_FILE, LOG_FILE, MAX_IMAGE_SIZE, ADMIN_CHAT_ID, _CFG, _LOCK_FILE,
    get_global_state,
)
from bot.core import tg, save_state


_IMAGE_SIGNATURES = {
    b"\x89PNG": ("png", "image/png"),
    b"\xff\xd8": ("jpg", "image/jpeg"),
    b"GIF8": ("gif", "image/gif"),
    b"RIFF": ("webp", "image/webp"),
    b"BM": ("bmp", "image/bmp"),
}


def detect_image_type(data):
    for sig, (ext, mime) in _IMAGE_SIGNATURES.items():
        if data[:len(sig)] == sig:
            return ext, mime
    return "jpg", "image/jpeg"


IS_SAFE_URL_CACHE = {}
SAFE_URL_CACHE_MAX = 200


def is_safe_url(url):
    if not url:
        return False
    if url in IS_SAFE_URL_CACHE:
        return IS_SAFE_URL_CACHE[url]
    if len(IS_SAFE_URL_CACHE) >= SAFE_URL_CACHE_MAX:
        IS_SAFE_URL_CACHE.clear()
    import urllib.parse
    host = urllib.parse.urlparse(url).hostname
    if not host:
        return False
    safe = True
    if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        safe = False
    elif host.startswith("10.") or host.startswith("172.16.") or host.startswith("192.168."):
        safe = False
    elif host == "[::1]" or host == "0.0.0.0":
        safe = False
    IS_SAFE_URL_CACHE[url] = safe
    return safe


def safe_download_image(url, timeout=10, max_size=MAX_IMAGE_SIZE):
    if not is_safe_url(url):
        return None
    try:
        resp = requests.get(url, stream=True, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return None
        size = 0
        chunks = []
        for chunk in resp.iter_content(chunk_size=65536):
            chunks.append(chunk)
            size += len(chunk)
            if size > max_size:
                print(f"  Image too large ({size} bytes), skipping")
                return None
        content = b"".join(chunks)
        return content
    except Exception as e:
        print(f"  Image download err: {e}")
        return None


SECURITY_STATE_KEY = "_last_security_check"


def security_check(state, force=False):
    now = time.time()
    last = state.get(SECURITY_STATE_KEY, 0)
    if not force and now - last < 86400:
        return
    issues = []
    info = []

    token_src = os.environ.get("TG_BOT_TOKEN", "")
    if token_src:
        info.append("Токен из TG_BOT_TOKEN ✅")
    elif _CFG.get("bot_token"):
        info.append("Токен из bot_config.json ⚠️ (храни в env)")

    state_size = os.path.getsize(STATE_FILE) if os.path.exists(STATE_FILE) else 0
    if state_size > 1024 * 1024:
        issues.append(f"bot_state.json: {state_size // 1024}KB ⚠️")
    else:
        info.append(f"State: {state_size // 1024}KB ✅")

    tmpdir = os.path.join(os.path.dirname(STATE_FILE), "audio_tmp")
    tmp_count = 0
    if os.path.exists(tmpdir):
        tmp_count = len([f for f in os.listdir(tmpdir) if os.path.isfile(os.path.join(tmpdir, f))])
    if tmp_count > 10:
        issues.append(f"audio_tmp/: {tmp_count} файлов ⚠️")
    else:
        info.append(f"audio_tmp/: {tmp_count} файлов ✅")

    log_size = os.path.getsize(LOG_FILE) / (1024 * 1024) if os.path.exists(LOG_FILE) else 0
    if log_size > 10:
        issues.append(f"bot.log: {log_size:.1f}MB ⚠️")
    else:
        info.append(f"Log: {log_size:.1f}MB ✅")

    text = "\U0001F6E1 **Проверка безопасности**"
    if issues:
        text += f"\n\n\U0001F525 **Проблемы:**\n" + "\n".join(f"\U0001F539 {i}" for i in issues)
    if info:
        text += f"\n\n\U0001F4A1 **Статус:**\n" + "\n".join(f"\U0001F539 {i}" for i in info)
    if not issues:
        text += "\n\n\U00002705 Всё чисто!"

    try:
        tg("sendMessage", json={
            "chat_id": ADMIN_CHAT_ID,
            "text": text,
        }, timeout=10)
    except Exception as e:
        print(f"  Security check send err: {e}")
    state[SECURITY_STATE_KEY] = now
    print(f"  Security check done ({len(issues)} issues)")


def _acquire_lock():
    if os.path.exists(_LOCK_FILE):
        try:
            with open(_LOCK_FILE, "r") as f:
                pid = int(f.read().strip())
            try:
                os.kill(pid, 0)
                print(f"  Lockfile alive (pid {pid}) — another instance running. Exiting.")
                sys.exit(0)
            except ProcessLookupError:
                print(f"  Stale lockfile (pid {pid}) — removing.")
                os.remove(_LOCK_FILE)
            except PermissionError:
                print(f"  Lock owned by pid {pid} (no permission) — using anyway.")
        except (ValueError, OSError, Exception):
            try:
                os.remove(_LOCK_FILE)
            except Exception:
                pass
    with open(_LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    print(f"  Lock acquired (pid {os.getpid()})")


def _release_lock():
    try:
        if os.path.exists(_LOCK_FILE):
            with open(_LOCK_FILE, "r") as f:
                pid = int(f.read().strip())
            if pid == os.getpid():
                os.remove(_LOCK_FILE)
                print("  Lock released")
    except Exception:
        pass


def _safe_exit(*args):
    state = get_global_state("state")
    if state is not None:
        try:
            save_state(state)
            print("  State saved on exit")
        except Exception:
            pass
    _release_lock()
    if args:
        sys.exit(0)


def _disk_space_check(path=None, min_mb=200):
    import shutil
    try:
        target = path or os.path.dirname(os.path.abspath(STATE_FILE))
        usage = shutil.disk_usage(target)
        free_mb = usage.free / (1024 * 1024)
        if free_mb < min_mb:
            print(f"  WARN: only {free_mb:.0f}MB free on disk (< {min_mb}MB)")
            return False
        return True
    except Exception:
        return True
