import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bot.learning import (
    init_learning, track_source_skip, track_source_post,
    source_score_mod, learn_game_override, apply_game_override,
)
from bot.config import _SCORING


class TestInitLearning(unittest.TestCase):
    def test_creates_keys(self):
        state = {}
        learning = init_learning(state)
        self.assertIn("learning", state)
        self.assertIn("source_quality", learning)
        self.assertIn("game_overrides", learning)

    def test_reuses_existing(self):
        state = {"learning": {"source_quality": {}, "game_overrides": {}}}
        learning = init_learning(state)
        self.assertIs(learning, state["learning"])


class TestSourceQuality(unittest.TestCase):
    def setUp(self):
        self.learning = {"source_quality": {}, "game_overrides": {}}

    def test_track_skip(self):
        track_source_skip(self.learning, "goha")
        sq = self.learning["source_quality"]["goha"]
        self.assertEqual(sq["skipped"], 1)
        self.assertEqual(sq["total"], 1)

    def test_track_post(self):
        track_source_post(self.learning, "igromania")
        sq = self.learning["source_quality"]["igromania"]
        self.assertEqual(sq["posted"], 1)
        self.assertEqual(sq["total"], 1)

    def test_no_mod_below_min_samples(self):
        track_source_skip(self.learning, "x")
        mod = source_score_mod(self.learning, "x")
        self.assertEqual(mod, 0)

    def test_mod_at_min_samples(self):
        for _ in range(_SCORING["source_quality_min_samples"]):
            track_source_skip(self.learning, "y")
        mod = source_score_mod(self.learning, "y")
        penalty = int(_SCORING["source_quality_max_penalty"] * 1.0)
        self.assertEqual(mod, penalty)

    def test_mod_half_skip(self):
        for _ in range(5):
            track_source_post(self.learning, "z")
            track_source_skip(self.learning, "z")
        mod = source_score_mod(self.learning, "z")
        self.assertEqual(mod, int(_SCORING["source_quality_max_penalty"] * 0.5))

    def test_mod_unknown_source(self):
        mod = source_score_mod(self.learning, "nonexistent")
        self.assertEqual(mod, 0)


class TestGameOverrides(unittest.TestCase):
    def setUp(self):
        self.learning = {"source_quality": {}, "game_overrides": {}}

    def test_learn_and_apply(self):
        raw = "Глава Take-Two объяснил продажи Red Dead Redemption 2"
        learn_game_override(self.learning, raw, "Red Dead Redemption 2")
        result = apply_game_override(self.learning, raw)
        self.assertEqual(result, "Red Dead Redemption 2")

    def test_case_insensitive_key(self):
        learn_game_override(self.learning, "GTA 6 NEWS", "GTA 6")
        result = apply_game_override(self.learning, "gta 6 news")
        self.assertEqual(result, "GTA 6")

    def test_short_game_ignored(self):
        learn_game_override(self.learning, "some title", "a")
        result = apply_game_override(self.learning, "some title")
        self.assertIsNone(result)

    def test_empty_title_ignored(self):
        learn_game_override(self.learning, "", "Game")
        learning = self.learning["game_overrides"]
        self.assertEqual(len([k for k in learning if not k.startswith("_")]), 0)

    def test_unchanged_override_not_duplicated(self):
        learn_game_override(self.learning, "title", "Game")
        learn_game_override(self.learning, "title", "Game")
        overrides = {k for k in self.learning["game_overrides"] if not k.startswith("_")}
        self.assertEqual(len(overrides), 1)

    def test_override_cooldown(self):
        learn_game_override(self.learning, "t", "Old")
        ts_key = "_t_ts"
        old_ts = time.time() - 86400 * 10
        self.learning["game_overrides"][ts_key] = old_ts
        learn_game_override(self.learning, "t", "New")
        self.assertEqual(self.learning["game_overrides"]["t"], "New")


if __name__ == "__main__":
    unittest.main()
