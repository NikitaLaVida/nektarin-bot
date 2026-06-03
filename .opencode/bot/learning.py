import time
from typing import Any, Optional
from bot.config import _SCORING


def init_learning(state: dict) -> dict:
    learning: dict = state.setdefault("learning", {})
    learning.setdefault("source_quality", {})
    learning.setdefault("game_overrides", {})
    return learning


def track_source_skip(learning: dict, source: str) -> None:
    sq: dict = learning["source_quality"].setdefault(source, {"posted": 0, "skipped": 0, "total": 0})
    sq["skipped"] = sq.get("skipped", 0) + 1
    sq["total"] = sq.get("total", 0) + 1


def track_source_post(learning: dict, source: str) -> None:
    sq: dict = learning["source_quality"].setdefault(source, {"posted": 0, "skipped": 0, "total": 0})
    sq["posted"] = sq.get("posted", 0) + 1
    sq["total"] = sq.get("total", 0) + 1


def source_score_mod(learning: dict, source: str) -> int:
    sq: dict = learning["source_quality"].get(source, {})
    total: int = sq.get("total", 0)
    if total < _SCORING["source_quality_min_samples"]:
        return 0
    skip_ratio: float = sq.get("skipped", 0) / total
    return int(_SCORING["source_quality_max_penalty"] * skip_ratio)


def learn_game_override(learning: dict, raw_title: str, extracted_game: str) -> None:
    if not raw_title or not extracted_game or len(extracted_game) < 2:
        return
    key: str = raw_title.lower().strip()
    existing: str = learning["game_overrides"].get(key, "")
    if existing == extracted_game:
        return
    if existing:
        ts: float = learning["game_overrides"].get(f"_{key}_ts", 0)
        if time.time() - ts < 86400 * 7:
            return
    learning["game_overrides"][key] = extracted_game
    learning["game_overrides"][f"_{key}_ts"] = time.time()


def apply_game_override(learning: dict, raw_title: str) -> Optional[str]:
    overrides: dict = learning.get("game_overrides", {})
    key: str = raw_title.lower().strip()
    return overrides.get(key, None)
