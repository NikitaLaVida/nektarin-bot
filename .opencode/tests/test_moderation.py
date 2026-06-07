import os
import sys
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from unittest.mock import patch


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
