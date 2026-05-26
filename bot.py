import sys, os, requests, time
import gaming_news_bot

BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "8879790921:AAE9hwgmrpSoa5wr7NCXA6H9CBDp6JgC3s0")
CHANNEL_ID = "@NektarinGaming"

LOG_FILE = "/app/data/bot.log"

def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    print(msg)

def send_test():
    log("send_test() started")
    log(f"BOT_TOKEN len={len(BOT_TOKEN)}, CHANNEL_ID={CHANNEL_ID}")
    try:
        r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
            "chat_id": CHANNEL_ID,
            "text": f"\u2705 \u0411\u043e\u0442 \u0437\u0430\u043f\u0443\u0449\u0435\u043d \u043d\u0430 Bothost\n{time.strftime('%d.%m.%Y %H:%M')}",
        }, timeout=15)
        log(f"Telegram response: {r.status_code} {r.text[:200]}")
        if r.status_code == 200:
            log(f"Test post sent: msg#{r.json()['result']['message_id']}")
        else:
            log(f"Test post failed: {r.status_code} {r.text[:150]}")
    except Exception as e:
        log(f"Test post error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    os.makedirs("/app/data", exist_ok=True)
    log("=== BOT STARTED ===")
    log(f"Python: {sys.version}")
    log(f"STATE_FILE env: {os.environ.get('STATE_FILE', 'not set')}")
    log(f"TG_BOT_TOKEN env set: {'yes' if os.environ.get('TG_BOT_TOKEN') else 'no (using default)'}")
    if "--stats" in sys.argv:
        gaming_news_bot.main()
    else:
        send_test()
        while True:
            gaming_news_bot.main()
            log("Sleeping 2 hours...")
            time.sleep(7200)