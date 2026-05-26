import sys
import gaming_news_bot

if __name__ == "__main__":
    if "--stats" in sys.argv:
        gaming_news_bot.main()
    else:
        import time
        while True:
            gaming_news_bot.main()
            print("Sleeping 2 hours...")
            time.sleep(7200)