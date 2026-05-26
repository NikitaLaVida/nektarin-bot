import os, sys, time, socket

PORT = int(os.environ.get("PORT", 8080))

LOG_FILE = "/app/data/bot.log"
os.makedirs("/app/data", exist_ok=True)

def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    print(msg, flush=True)

log("=== BOT STARTED (minimal test) ===")
log(f"Python: {sys.version}")
log(f"PORT={PORT}")

import threading

def health_server():
    import http.server
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        def log_message(self, *a):
            pass
    s = http.server.HTTPServer(("0.0.0.0", PORT), H)
    log(f"Health server listening on 0.0.0.0:{PORT}")
    s.serve_forever()

t = threading.Thread(target=health_server, daemon=True)
t.start()

# Test Telegram
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "8879790921:AAE9hwgmrpSoa5wr7NCXA6H9CBDp6JgC3s0")
CHANNEL_ID = "@NektarinGaming"

import requests
log("Sending test message...")
try:
    r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
        "chat_id": CHANNEL_ID,
        "text": f"✅ Бот запущен на Bothost (test)\n{time.strftime('%d.%m.%Y %H:%M')}",
    }, timeout=15)
    log(f"TG response: {r.status_code} {r.text[:200]}")
except Exception as e:
    log(f"TG error: {type(e).__name__}: {e}")

log("Sleeping...")
while True:
    time.sleep(3600)
