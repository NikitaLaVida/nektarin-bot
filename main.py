import os
import sys
import time
import signal


os.chdir(os.path.join(os.path.dirname(__file__), ".opencode"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".opencode"))

from gaming_news_bot import run_iteration


def main():
    interval = 1200
    for i, arg in enumerate(sys.argv):
        if arg == "--interval" and i + 1 < len(sys.argv):
            interval = int(sys.argv[i + 1])

    print(f"=== NektarinBot daemon, interval={interval}s ===")
    while True:
        try:
            run_iteration()
        except Exception as e:
            import traceback
            traceback.print_exc()
        print(f"Sleeping {interval}s...")
        time.sleep(interval)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    main()
