import sys, os, requests, time
import gaming_news_bot

BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "8879790921:AAE9hwgmrpSoa5wr7NCXA6H9CBDp6JgC3s0")
CHANNEL_ID = "@NektarinGaming"

def send_test():
    try:
        r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
            "chat_id": CHANNEL_ID,
            "text": f"\u2705 \u0411\u043e\u0442 \u0437\u0430\u043f\u0443\u0449\u0435\u043d \u043d\u0430 Bothost\n{time.strftime('%d.%m.%Y %H:%M')}",
        }, timeout=10)
        if r.status_code == 200:
            print(f"Test post sent: msg#{r.json()['result']['message_id']}")
        else:
            print(f"Test post failed: {r.status_code} {r.text[:150]}")
    except Exception as e:
        print(f"Test post error: {e}")

if __name__ == "__main__":
    if "--stats" in sys.argv:
        gaming_news_bot.main()
    else:
        send_test()
        while True:
            gaming_news_bot.main()
            print("Sleeping 2 hours...")
            time.sleep(7200)