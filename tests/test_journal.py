"""
Тесты для журнального раздела build.py.
Запуск: python3 -m pytest tests/test_journal.py -v
   или: python3 -m unittest tests.test_journal -v
"""
import sys, unittest
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))

import build

class TestIssueCoverSvg(unittest.TestCase):

    def _issue(self, color):
        return {"number": "04", "period": "весна 2026",
                "title": "Пётр Швецов", "subtitle": "о болоте",
                "coverColor": color}

    def test_alyi_background(self):
        svg = build.issue_cover_svg(self._issue("alyi"))
        self.assertIn("#FA2A22", svg)
        self.assertIn("ЁPRST", svg)

    def test_kobalt_background(self):
        svg = build.issue_cover_svg(self._issue("kobalt"))
        self.assertIn("#2A4BFF", svg)

    def test_fuxia_background(self):
        svg = build.issue_cover_svg(self._issue("fuxia"))
        self.assertIn("#FF3DA0", svg)

    def test_hvoya_background(self):
        svg = build.issue_cover_svg(self._issue("hvoya"))
        self.assertIn("#2E5A2A", svg)

    def test_limon_uses_dark_text(self):
        """Лимон — светлый фон, текст должен быть тёмным."""
        svg = build.issue_cover_svg(self._issue("limon"))
        self.assertIn("#161614", svg)

    def test_unknown_color_falls_back_to_alyi(self):
        svg = build.issue_cover_svg(self._issue("nonexistent"))
        self.assertIn("#FA2A22", svg)

    def test_contains_issue_number(self):
        svg = build.issue_cover_svg(self._issue("kobalt"))
        self.assertIn("04", svg)


class TestHeadExtraCss(unittest.TestCase):

    def test_extra_css_link_present(self):
        html = build.head("T", "D", "https://prstnk.ru/journal",
                          extra_css="journal.css")
        self.assertIn('href="journal.css"', html)

    def test_no_extra_css_by_default(self):
        html = build.head("T", "D", "https://prstnk.ru/journal")
        self.assertNotIn("journal.css", html)


class TestRenderJournalIndex(unittest.TestCase):

    def setUp(self):
        self.html = build.render_journal_index()

    def test_contains_hero_section(self):
        self.assertIn('class="hero"', self.html)

    def test_contains_rubric_bar(self):
        self.assertIn('class="rubric-bar"', self.html)

    def test_contains_issues_section(self):
        self.assertIn('class="issues-section"', self.html)

    def test_contains_lenta_section(self):
        self.assertIn('class="lenta-section"', self.html)

    def test_contains_journal_css_link(self):
        self.assertIn('href="journal.css"', self.html)

    def test_no_html_extensions_in_internal_links(self):
        import re
        # Внутренние href не должны оканчиваться на .html
        bad = re.findall(r'href="(?!http)[^"]+\.html"', self.html)
        self.assertEqual(bad, [], f"Найдены .html ссылки: {bad}")


if __name__ == "__main__":
    unittest.main()
