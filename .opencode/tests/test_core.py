import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bot.core import (
    escape_html, clean, clean_desc, shorten, is_gaming_related,
    extract_game, extract_numbers, extract_platforms, detect_theme,
    title_similarity, is_hot, is_trailer, detect_genre,
)
from bot.security import is_safe_url, detect_image_type


class TestEscapeHtml(unittest.TestCase):
    def test_plain_text(self):
        self.assertEqual(escape_html("hello"), "hello")

    def test_ampersand(self):
        self.assertEqual(escape_html("a&b"), "a&amp;b")

    def test_lt_gt(self):
        self.assertEqual(escape_html("<b>bold</b>"), "&lt;b&gt;bold&lt;/b&gt;")

    def test_non_string(self):
        self.assertEqual(escape_html(42), "42")


class TestClean(unittest.TestCase):
    def test_strip_html(self):
        self.assertEqual(clean("<p>hello</p>"), "hello")

    def test_unescape(self):
        self.assertEqual(clean("hello &amp; world"), "hello & world")

    def test_multi_whitespace(self):
        self.assertEqual(clean("hello   world"), "hello world")

    def test_null_byte(self):
        self.assertEqual(clean("hello\x00world"), "helloworld")

    def test_none_input(self):
        self.assertEqual(clean(None), "")


class TestCleanDesc(unittest.TestCase):
    def test_boilerplate_removal(self):
        result = clean_desc("Новость. Читать далее...")
        self.assertNotIn("Читать далее", result)

    def test_boilerplate_removal_2(self):
        result = clean_desc("Заголовок. Подробнее на сайте")
        self.assertNotIn("Подробнее", result)


class TestShorten(unittest.TestCase):
    def test_short_stays(self):
        self.assertEqual(shorten("hello", 200), "hello")

    def test_long_gets_cut(self):
        s = "a" * 300
        self.assertLessEqual(len(shorten(s, 200)), 200)

    def test_sentence_cut(self):
        s = ("word " * 50) + ". tail"
        result = shorten(s, 100)
        self.assertLessEqual(len(result), 100)

    def test_empty(self):
        self.assertEqual(shorten(""), "")

    def test_none(self):
        self.assertEqual(shorten(None), "")


class TestIsGamingRelated(unittest.TestCase):
    def test_gaming_title(self):
        self.assertTrue(is_gaming_related("Elden Ring sold 20 million copies", ""))

    def test_movie_title_filtered(self):
        result = is_gaming_related("Новый сериал Netflix", "про игру")
        self.assertTrue(result)

    def test_pure_movie(self):
        result = is_gaming_related("Новый сериал Netflix о актёрах", "описание фильма")
        self.assertFalse(result)


class TestExtractGame(unittest.TestCase):
    def test_simple_name(self):
        self.assertIn("Elden", extract_game("Elden Ring продажи рекорд"))

    def test_platform_stripped(self):
        result = extract_game("Cyberpunk 2077 на PS5")
        self.assertNotIn("PS5", result)

    def test_studio_stripped(self):
        result = extract_game("Bethesda анонсировала новую RPG")
        self.assertNotIn("Bethesda", result)

    def test_short_title(self):
        result = extract_game("The Witcher 3")
        self.assertTrue(len(result) > 2)


class TestExtractNumbers(unittest.TestCase):
    def test_finds_number(self):
        self.assertTrue(len(extract_numbers("продано 30 млн копий")) > 0)

    def test_empty_text(self):
        self.assertEqual(extract_numbers(""), [])

    def test_no_numbers(self):
        self.assertEqual(extract_numbers("привет мир"), [])


class TestExtractPlatforms(unittest.TestCase):
    def test_ps5(self):
        self.assertIn("PS5", extract_platforms("вышла на PS5"))

    def test_steam(self):
        self.assertIn("Steam", extract_platforms("Steam релиз"))

    def test_none(self):
        self.assertEqual(extract_platforms("привет"), [])


class TestDetectTheme(unittest.TestCase):
    def test_sales(self):
        self.assertEqual(detect_theme("Продажи", "миллион копий"), "sales")

    def test_delay(self):
        self.assertEqual(detect_theme("Перенос", "отложен релиз"), "delay")

    def test_rumor(self):
        self.assertEqual(detect_theme("Слух", "утечка"), "rumor")

    def test_generic(self):
        self.assertEqual(detect_theme("Какая-то новость", "просто текст"), "generic")


class TestTitleSimilarity(unittest.TestCase):
    def test_identical(self):
        s = title_similarity("hello world test", "hello world test")
        self.assertGreater(s, 0.9)

    def test_different(self):
        self.assertEqual(title_similarity("hello world test", "foo bar baz"), 0)

    def test_partial(self):
        s = title_similarity("elden ring new dlc", "elden ring news update")
        self.assertGreater(s, 0)
        self.assertLess(s, 1)


class TestIsHot(unittest.TestCase):
    def test_hot_keyword(self):
        self.assertTrue(is_hot({"title": "GTA 6 анонс", "desc": ""}))

    def test_not_hot(self):
        self.assertFalse(is_hot({"title": "обычная новость", "desc": ""}))


class TestIsTrailer(unittest.TestCase):
    def test_trailer(self):
        self.assertTrue(is_trailer("Новый трейлер игры"))

    def test_not_trailer(self):
        self.assertFalse(is_trailer("Обзор игры"))


class TestDetectGenre(unittest.TestCase):
    def test_shooter(self):
        self.assertEqual(detect_genre("шутер от первого лица"), "шутер")

    def test_no_genre(self):
        self.assertIsNone(detect_genre("обычный текст"))


class TestSafeUrl(unittest.TestCase):
    def test_https(self):
        self.assertTrue(is_safe_url("https://example.com/image.jpg"))

    def test_localhost(self):
        self.assertFalse(is_safe_url("http://localhost:8080"))

    def test_private_ip(self):
        self.assertFalse(is_safe_url("http://192.168.1.1/"))

    def test_empty(self):
        self.assertFalse(is_safe_url(""))

    def test_none(self):
        self.assertFalse(is_safe_url(None))

    def test_10_dot(self):
        self.assertFalse(is_safe_url("http://10.0.0.1/"))


class TestDetectImageType(unittest.TestCase):
    def test_png(self):
        ext, mime = detect_image_type(b"\x89PNG....")
        self.assertEqual(ext, "png")
        self.assertEqual(mime, "image/png")

    def test_jpg(self):
        ext, mime = detect_image_type(b"\xff\xd8....")
        self.assertEqual(ext, "jpg")

    def test_gif(self):
        ext, mime = detect_image_type(b"GIF8....")
        self.assertEqual(ext, "gif")

    def test_unknown_is_jpg(self):
        ext, mime = detect_image_type(b"\x00\x00\x00\x00")
        self.assertEqual(ext, "jpg")


if __name__ == "__main__":
    unittest.main()
