import os
import sys
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from unittest.mock import patch, MagicMock


class TestPostWatchedAuto(unittest.TestCase):
    def setUp(self):
        self.state = {"last_posted_themes": []}
        self.ids = {}

    def make_scored_item(self, title="Elden Ring news", game="elden ring", score=50, theme="generic"):
        return {
            "title": title, "desc": "desc", "link": "https://example.com",
            "_game": game, "_score": score, "_theme": theme,
            "id": "test123", "content_hash": "hash123",
            "source": "test", "youtube_url": None,
        }

    @patch("bot.moderation.tg")
    @patch("bot.moderation.send_post")
    @patch("bot.moderation.find_post_image")
    def test_posts_watched_game(self, mock_find, mock_send, mock_tg):
        from bot.moderation import _post_watched_auto
        mock_send.return_value = 100
        item = self.make_scored_item()
        result = _post_watched_auto(self.state, self.ids, [item])
        self.assertEqual(result, 1)
        mock_send.assert_called_once()

    @patch("bot.moderation.tg")
    @patch("bot.moderation.send_post")
    @patch("bot.moderation.find_post_image")
    def test_skips_low_score(self, mock_find, mock_send, mock_tg):
        from bot.moderation import _post_watched_auto
        item = self.make_scored_item(score=10)
        result = _post_watched_auto(self.state, self.ids, [item])
        self.assertEqual(result, 0)
        mock_send.assert_not_called()

    @patch("bot.moderation.tg")
    @patch("bot.moderation.send_post")
    @patch("bot.moderation.find_post_image")
    def test_skips_recent_theme(self, mock_find, mock_send, mock_tg):
        from bot.moderation import _post_watched_auto
        self.state["last_posted_themes"] = ["generic"]
        item = self.make_scored_item()
        result = _post_watched_auto(self.state, self.ids, [item])
        self.assertEqual(result, 0)
        mock_send.assert_not_called()

    @patch("bot.moderation.tg")
    @patch("bot.moderation.send_post")
    @patch("bot.moderation.find_post_image")
    def test_only_first_item_posted(self, mock_find, mock_send, mock_tg):
        from bot.moderation import _post_watched_auto
        item1 = self.make_scored_item(title="Game 1", game="elden ring")
        item2 = self.make_scored_item(title="Game 2", game="witcher")
        result = _post_watched_auto(self.state, self.ids, [item1, item2])
        self.assertEqual(result, 1)
        mock_send.assert_called_once()


class TestProcessModeration(unittest.TestCase):
    def test_expired_items_filtered(self):
        from bot.moderation import _process_moderation
        state = {
            "pending_moderation": [
                {"title": "old", "time": time.time() - 90000, "msg_id": 1},
            ],
        }
        with patch("bot.moderation.process_updates", return_value={}):
            with patch("bot.moderation.tg"):
                result = _process_moderation(state, {}, [])
        self.assertEqual(result, 0)
        self.assertEqual(len(state.get("pending_moderation", [])), 0)

    def test_keeps_active_items(self):
        from bot.moderation import _process_moderation
        state = {
            "pending_moderation": [
                {"title": "fresh", "time": time.time(), "msg_id": 1, "id": "a1"},
            ],
        }
        with patch("bot.moderation.process_updates", return_value={}):
            with patch("bot.moderation.tg"):
                result = _process_moderation(state, {}, [])
        self.assertEqual(len(state.get("pending_moderation", [])), 1)


if __name__ == "__main__":
    unittest.main()
