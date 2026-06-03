import sys
import time


LEVELS = {"DEBUG": 0, "INFO": 1, "WARN": 2, "ERROR": 3}
_LEVEL = LEVELS["DEBUG"]


def set_level(name):
    global _LEVEL
    _LEVEL = LEVELS.get(name.upper(), LEVELS["INFO"])


def log(msg, level="INFO"):
    if LEVELS.get(level, 1) < _LEVEL:
        return
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def info(msg):
    log(msg, "INFO")


def warn(msg):
    log(msg, "WARN")


def error(msg):
    log(msg, "ERROR")
