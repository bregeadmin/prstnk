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


if __name__ == "__main__":
    unittest.main()
