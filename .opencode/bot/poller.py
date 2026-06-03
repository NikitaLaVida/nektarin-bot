import sys
import time
import threading
from bot.config import LOG_FILE


def _get_last_run_time():
    import gaming_news_bot as gnb
    return gnb._LAST_RUN_TIME


def _set_last_run_time(t):
    import gaming_news_bot as gnb
    gnb._LAST_RUN_TIME = t


def _healthcheck(interval):
    import socket as _socket
    s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    s.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", 8080))
    s.listen(1)
    s.settimeout(1)
    while True:
        try:
            conn, _ = s.accept()
            stale = time.time() - _get_last_run_time() > interval * 2.5
            if stale:
                body = f"stale last_run={int(_get_last_run_time())}"
                conn.sendall(f"HTTP/1.1 503 Service Unavailable\r\nContent-Length: {len(body)}\r\n\r\n{body}".encode())
            else:
                conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
            conn.close()
        except _socket.timeout:
            continue
        except Exception:
            break


def run_poller(interval=1200):
    from gaming_news_bot import main, _handle_crash
    print(f"=== Daemon mode, interval={interval}s ===")
    t = threading.Thread(target=_healthcheck, args=(interval,), daemon=True)
    t.start()
    print(f"  Healthcheck on http://0.0.0.0:8080/healthz")
    while True:
        try:
            main()
        except Exception as e:
            _handle_crash(e, fatal=False)
        print(f"Sleeping {interval}s...")
        time.sleep(interval)


def run_cli():
    from gaming_news_bot import main, _handle_crash
    if "--stats" in sys.argv:
        from gaming_news_bot import print_stats
        print_stats()
    elif "--mod" in sys.argv:
        from bot.moderation import force_moderation
        n = 3
        for i, arg in enumerate(sys.argv):
            if arg == "--mod" and i + 1 < len(sys.argv) and sys.argv[i + 1].isdigit():
                n = int(sys.argv[i + 1])
        force_moderation(n)
    elif "--daemon" in sys.argv:
        interval = 1200
        for i, arg in enumerate(sys.argv):
            if arg == "--interval" and i + 1 < len(sys.argv):
                interval = int(sys.argv[i + 1])
        run_poller(interval)
    else:
        try:
            main()
        except Exception as e:
            _handle_crash(e, fatal=True)
