"""Тесты track A — материалы из блоков. Запуск: python3 -m unittest tests.test_materials -v"""
import sys, unittest
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
import build


class TestRubrics(unittest.TestCase):
    def test_four_rubrics(self):
        self.assertEqual(set(build.RUBRICS), {"razgovory", "na-paltsakh", "istoriya", "kak-smotret"})

    def test_label(self):
        self.assertEqual(build.rubric_label("razgovory"), "Разговоры")
        self.assertEqual(build.rubric_label("nope"), "")

    def test_color(self):
        self.assertEqual(build.rubric_color("na-paltsakh"), "kobalt")
        self.assertEqual(build.rubric_color("nope"), "default")

    def test_reserved_slugs_include_rubrics(self):
        for r in ("razgovory", "na-paltsakh", "istoriya", "kak-smotret"):
            self.assertIn(r, build.RESERVED_SLUGS)


class TestTextBlocks(unittest.TestCase):
    def test_text_block_renders_markdown(self):
        html = build.render_block({"type": "text", "text": "Привет **мир**"})
        self.assertIn("bl-text", html)
        self.assertIn("<b>мир</b>", html)

    def test_heading_block(self):
        html = build.render_block({"type": "heading", "text": "Подзаголовок"})
        self.assertIn("bl-heading", html)
        self.assertIn("Подзаголовок", html)

    def test_quote_with_cite(self):
        html = build.render_block({"type": "quote", "text": "Фраза", "cite": "Автор"})
        self.assertIn("bl-quote", html)
        self.assertIn("<cite>Автор</cite>", html)

    def test_quote_without_cite(self):
        html = build.render_block({"type": "quote", "text": "Фраза"})
        self.assertNotIn("<cite>", html)

    def test_unknown_block_is_empty(self):
        self.assertEqual(build.render_block({"type": "wat"}), "")


if __name__ == "__main__":
    unittest.main()
