"""Git filter-branch helper: replace hardcoded token in ALL files.

Usage:
    $env:PURGE_TOKEN = "bot123:abc..."; python scripts/purge_token.py
    # or pass via arg:
    python scripts/purge_token.py bot123:abc...
"""
import os
import sys

TOKEN = os.environ.get("PURGE_TOKEN") or (sys.argv[1] if len(sys.argv) > 1 else "")
if not TOKEN:
    print("ERROR: Set PURGE_TOKEN env var or pass token as argument")
    sys.exit(1)

EXTS = {".py", ".json", ".log", ".md", ".txt", ".ps1", ".yml", ".yaml", ".cfg", ".conf", ".ini", ".sh"}

for dirpath, _dirs, files in os.walk("."):
    for fn in files:
        ext = os.path.splitext(fn)[1].lower()
        if ext not in EXTS:
            continue
        path = os.path.join(dirpath, fn)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                data = f.read()
            if TOKEN in data:
                data = data.replace(TOKEN, "${BOT_TOKEN}")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(data)
        except Exception as e:
            print(f"  Error {path}: {e}")
