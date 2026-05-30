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


class TestMediaBlocks(unittest.TestCase):
    def test_photo_with_caption(self):
        html = build.render_block({"type": "photo", "image": "/u/a.jpg", "caption": "Подпись"})
        self.assertIn("bl-photo", html)
        self.assertIn('src="/u/a.jpg"', html)
        self.assertIn("Подпись", html)

    def test_split_image_side_left(self):
        html = build.render_block({"type": "split", "text": "т", "image": "/u/b.jpg", "imageSide": "left"})
        self.assertIn("bl-split--left", html)
        self.assertIn('src="/u/b.jpg"', html)

    def test_gallery_counts_images(self):
        html = build.render_block({"type": "gallery", "images": ["/1.jpg", "/2.jpg", "/3.jpg"]})
        self.assertIn('data-count="3"', html)
        self.assertEqual(html.count("<img"), 3)

    def test_embed_youtube_extracts_id(self):
        html = build.render_block({"type": "embed", "provider": "youtube",
                                   "url": "https://youtu.be/dQw4w9WgXcQ"})
        self.assertIn("youtube.com/embed/dQw4w9WgXcQ", html)

    def test_embed_vimeo_extracts_id(self):
        html = build.render_block({"type": "embed", "provider": "vimeo",
                                   "url": "https://vimeo.com/123456"})
        self.assertIn("player.vimeo.com/video/123456", html)

    def test_embed_bad_url_empty(self):
        self.assertEqual(build.render_block({"type": "embed", "provider": "youtube", "url": "x"}), "")


class TestPicksBlock(unittest.TestCase):
    def test_picks_renders_known_work(self):
        first = build.artworks[0]
        html = build.render_block({"type": "picks", "heading": "В продаже",
                                   "workIds": [first["id"]]})
        self.assertIn("bl-picks", html)
        self.assertIn("В продаже", html)
        self.assertIn(f'work-{first["slug"]}', html)
        self.assertIn(build.esc(first["title"]), html)

    def test_picks_skips_unknown_id(self):
        html = build.render_block({"type": "picks", "heading": "X", "workIds": ["no-such-id-xyz"]})
        self.assertIn("bl-picks", html)
        self.assertNotIn("pick-title", html)


class TestArticlesCollection(unittest.TestCase):
    def test_articles_loaded(self):
        self.assertTrue(any(a.get("slug") == "kak-travyat-tsink" for a in build.articles))

    def test_reserved_slug_guard_raises(self):
        with self.assertRaises(ValueError):
            build.check_article_slugs([{"slug": "istoriya"}])

    def test_reserved_slug_guard_ok(self):
        build.check_article_slugs([{"slug": "normalnyy-slug"}])  # не должно бросать


class TestMaterialPage(unittest.TestCase):
    def setUp(self):
        self.art = next(a for a in build.articles if a["slug"] == "kak-travyat-tsink")
        self.html = build.render_material_page(self.art)

    def test_has_title_and_em(self):
        self.assertIn("material-title", self.html)
        self.assertIn("<em>кислота и игла</em>", self.html)

    def test_has_rubric_label_and_class(self):
        self.assertIn("На пальцах", self.html)
        self.assertIn("rub-kobalt", self.html)

    def test_renders_blocks(self):
        self.assertIn("bl-quote", self.html)
        self.assertIn("Пётр Швецов", self.html)

    def test_links_journal_css(self):
        self.assertIn('href="journal.css"', self.html)

    def test_back_link_to_materials(self):
        self.assertIn("Все материалы", self.html)


class TestFeed(unittest.TestCase):
    def _arts(self, n):
        return [{"slug": f"m{i}", "rubric": "razgovory", "title": f"Заголовок {i}",
                 "lead": "лид", "readMins": 5, "date": "2026-05-10"} for i in range(n)]

    def test_rhythm_starts_with_hero(self):
        html = build._feed_rhythm(self._arts(1))
        self.assertIn("feed-hero", html)

    def test_rhythm_second_module_is_split(self):
        html = build._feed_rhythm(self._arts(3))
        self.assertIn("feed-split", html)

    def test_rhythm_consumes_all_items(self):
        html = build._feed_rhythm(self._arts(11))
        for i in range(11):
            self.assertIn(f"journal/m{i}", html)

    def test_materials_index_structure(self):
        html = build.render_materials_index()
        self.assertIn("Все", html)
        self.assertIn('href="journal.css"', html)
        self.assertIn("materials-feed", html)


class TestRubricPage(unittest.TestCase):
    def test_rubric_page_lists_only_its_rubric(self):
        html = build.render_rubric_page("na-paltsakh")
        self.assertIn("На пальцах", html)
        self.assertIn("journal/kak-travyat-tsink", html)  # этот материал — na-paltsakh

    def test_rubric_page_links_css(self):
        html = build.render_rubric_page("razgovory")
        self.assertIn('href="journal.css"', html)


if __name__ == "__main__":
    unittest.main()
