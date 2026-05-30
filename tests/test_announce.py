import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
import announce_materials as ann


class TestAnnounce(unittest.TestCase):
    def test_new_materials_filters_announced(self):
        arts = [{"slug": "a"}, {"slug": "b"}, {"slug": "c"}]
        fresh = ann.new_materials(arts, {"a", "c"})
        self.assertEqual([x["slug"] for x in fresh], ["b"])

    def test_new_materials_skips_no_slug(self):
        arts = [{"slug": ""}, {"title": "no slug"}, {"slug": "x"}]
        fresh = ann.new_materials(arts, set())
        self.assertEqual([x["slug"] for x in fresh], ["x"])

    def test_build_message_has_title_lead_link(self):
        msg = ann.build_message({"slug": "shvetsov-boloto",
                                 "title": "Пётр Швецов", "lead": "Большой разговор."})
        self.assertIn("Пётр Швецов", msg)
        self.assertIn("Большой разговор.", msg)
        self.assertIn("https://prstnk.ru/journal/shvetsov-boloto", msg)

    def test_build_message_without_lead(self):
        msg = ann.build_message({"slug": "x", "title": "Заголовок"})
        self.assertIn("Заголовок", msg)
        self.assertIn("https://prstnk.ru/journal/x", msg)


if __name__ == "__main__":
    unittest.main()
