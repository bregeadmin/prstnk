import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
import fetch_lenta

FIX = (Path(__file__).parent / "fixtures" / "tg_channel.html").read_text()

class TestParse(unittest.TestCase):
    def test_returns_list(self):
        posts = fetch_lenta.parse_channel_html(FIX)
        self.assertIsInstance(posts, list)

    def test_posts_have_fields(self):
        posts = fetch_lenta.parse_channel_html(FIX)
        self.assertTrue(posts, "ожидался хотя бы 1 пост в фикстуре")
        p = posts[0]
        for k in ("title", "date", "url", "tag", "photo"):
            self.assertIn(k, p)
        self.assertTrue(p["url"].startswith("https://t.me/"))

    def test_limit_respected(self):
        posts = fetch_lenta.parse_channel_html(FIX, limit=2)
        self.assertLessEqual(len(posts), 2)

    def test_empty_html_no_crash(self):
        self.assertEqual(fetch_lenta.parse_channel_html(""), [])
