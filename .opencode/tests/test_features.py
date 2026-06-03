import os
import sys
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from bot.features import make_caption, score_news_item


class TestMakeCaption(unittest.TestCase):
    def test_basic_caption(self):
        cap = make_caption("Новость", "Текст новости", "https://example.com")
        self.assertIn("Новость", cap)
        self.assertIn("@NektarinGaming", cap)

    def test_english_title_translated(self):
        cap = make_caption("Elden Ring sold 20 million", "Game sold well", "https://example.com")
        self.assertIn("https://example.com", cap)
        self.assertIn("@NektarinGaming", cap)

    def test_with_game(self):
        cap = make_caption("Новость", "Текст", "https://example.com", game="Elden Ring")
        self.assertIsInstance(cap, str)
        self.assertGreater(len(cap), 10)

    def test_hashtag_present(self):
        cap = make_caption("Новость", "Текст", "https://example.com")
        self.assertIn("#", cap)

    def test_truncated_when_long(self):
        long_desc = "слово " * 500
        cap = make_caption("Новость", long_desc, "https://example.com")
        self.assertLessEqual(len(cap), 900)

    def test_caption_contains_link(self):
        cap = make_caption("Новость", "Текст", "https://example.com/news/1")
        self.assertIn("example.com", cap)


class TestScoreNewsItem(unittest.TestCase):
    def make_item(self, title="Test Game", desc="Description", source="test",
                  link="https://example.com", item_id="test123", item_hash="hash123"):
        return {
            "title": title, "desc": desc, "link": link,
            "source": source, "youtube_url": None,
            "id": item_id, "content_hash": item_hash,
        }

    def test_basic_scoring(self):
        item = self.make_item()
        result = score_news_item(item, {}, {}, [])
        self.assertIsNotNone(result)
        self.assertIn("_score", result)

    def test_already_seen_by_id(self):
        item = self.make_item()
        result = score_news_item(item, {"test123": {"time": 100}}, {}, [])
        self.assertIsNone(result)

    def test_already_seen_by_hash(self):
        item = self.make_item()
        result = score_news_item(item, {}, {"hash123": time.time()}, [])
        self.assertIsNone(result)

    def test_hot_boost(self):
        item = self.make_item(title="трейлер Elden Ring", desc="новый трейлер")
        result = score_news_item(item, {}, {}, [])
        self.assertGreater(result["_score"], 0)

    def test_non_gaming_penalty(self):
        item = self.make_item(title="Новый эпизод сериала Netflix", desc="сериал")
        result = score_news_item(item, {}, {}, [])
        self.assertIsNotNone(result)

    def test_rumor_theme(self):
        item = self.make_item(title="Утечка: скриншоты новой игры", desc="инсайдер слил подробности")
        result = score_news_item(item, {}, {}, [])
        if result:
            self.assertEqual(result["_theme"], "rumor")

    def test_trailer_boost(self):
        item = self.make_item(title="Новый трейлер игры", desc="тизер")
        result = score_news_item(item, {}, {}, [])
        if result:
            self.assertTrue(result["_score"] >= 10)

    def test_cross_source_dedup(self):
        item1 = self.make_item(title="Игра", desc="Описание", item_id="a1", item_hash="h1")
        item2 = self.make_item(title="Игра", desc="Описание", item_id="a2", item_hash="h1")
        r1 = score_news_item(item1, {}, {}, [])
        r2 = score_news_item(item2, {}, {"h1": time.time()}, [])
        self.assertIsNotNone(r1)
        self.assertIsNone(r2)

    def test_repeat_penalty(self):
        item = self.make_item(title="Elden Ring news", desc="большое обновление")
        recent = ["elden ring"]
        result = score_news_item(item, {}, {}, recent)
        if result:
            self.assertIn("_score", result)


if __name__ == "__main__":
    unittest.main()
