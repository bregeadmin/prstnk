# ЁPRST Материалы из блоков (track A) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Запустить поток «материалов» журнала ЁPRST — самостоятельные статьи из блоков, редактируемые в Sveltia, со страницами материала/рубрик/«Все материалы» и починенным рубрикатором.

**Architecture:** Каждый материал = отдельный JSON в `data/articles/` с типизированным списком `blocks`. `build.py` получает диспетчер `render_block()`, страницы материала/рубрик/ленты и общий хелпер ритм-ленты `_feed_rhythm()`. Рубрики фиксируются словарём `RUBRICS`. Стили добавляются в существующий `journal.css`. Статьи выпуска 04 переносятся в новый формат.

**Tech Stack:** Python 3.9 stdlib, f-strings (без вложенных одинаковых кавычек), CSS Grid, Sveltia CMS (YAML config), `python3 -m unittest`.

**Спек:** `docs/superpowers/specs/2026-05-30-eprst-materials-blocks-design.md`
**Эталоны вёрстки:** `_blocks-preview.html` (страница материала), `_materials-feed-v3.html` (ритм-лента).

---

## File map

| Действие | Файл | Ответственность |
|----------|------|-----------------|
| Modify | `build.py` (~947) | `RUBRICS` словарь + хелперы рубрик |
| Modify | `build.py` (~1480, после `render_journal_index`) | блоки, ритм-лента, страницы материала/рубрик/«Все материалы» |
| Modify | `build.py` (~1726, главный цикл) | загрузка `articles`, запись новых страниц, guard slug'ов |
| Modify | `build.py` `render_journal_index` (~1298) | «Свежие материалы» и рубрикатор — из `articles` |
| Modify | `journal.css` | стили блоков (`.bl-*`) и модулей ленты (`.feed-*`) |
| Modify | `admin/config.yml` | коллекция «Материалы» + переименование ленты в «Лента» |
| Create | `data/articles/*.json` | материалы (перенос из выпуска 04 + 1 пример) |
| Create | `tests/test_materials.py` | тесты блоков, рубрик, ленты, страниц |
| Delete | `_blocks-preview.html`, `_materials-feed*.html` | макеты-эталоны (в конце) |

**Соглашения по именам (во избежание коллизий):**
- Новая функция страницы материала — **`render_material_page(article)`** (существует `render_article(issue, art, idx)` — НЕ трогать, это zine).
- CSS-классы модулей ленты — **`.feed-hero/.feed-split/.feed-band/.feed-split2/.feed-textband`** (на `/journal` уже занят `.hero`).
- Страницы материалов и рубрик пишутся в подпапку `journal/`: `journal/<slug>.html`, `journal/<rubric>.html`.

---

## Task 1: Словарь рубрик и хелперы

**Files:**
- Modify: `build.py` (после `PALETTE`, ~строка 953)
- Test: `tests/test_materials.py`

- [ ] **Шаг 1: Написать тесты**

Создать `tests/test_materials.py`:

```python
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
```

- [ ] **Шаг 2: Запустить — убедиться что падает**

Run: `python3 -m unittest tests.test_materials -v`
Expected: FAIL/ERROR — `AttributeError: module 'build' has no attribute 'RUBRICS'`.

- [ ] **Шаг 3: Реализовать**

Вставить в `build.py` сразу после словаря `PALETTE` (около строки 953):

```python
RUBRICS = {
    "razgovory":   {"label": "Разговоры",    "color": "alyi"},
    "na-paltsakh": {"label": "На пальцах",   "color": "kobalt"},
    "istoriya":    {"label": "История",      "color": "hvoya"},
    "kak-smotret": {"label": "Как смотреть", "color": "fuxia"},
}
RESERVED_SLUGS = set(RUBRICS) | {"all"}

def rubric_label(slug):
    return RUBRICS.get(slug, {}).get("label", "")

def rubric_color(slug):
    return RUBRICS.get(slug, {}).get("color", "default")
```

- [ ] **Шаг 4: Запустить — убедиться что проходит**

Run: `python3 -m unittest tests.test_materials -v`
Expected: PASS (4 теста).

- [ ] **Шаг 5: Commit**

```bash
git add build.py tests/test_materials.py
git commit -m "feat: add RUBRICS dict and rubric helpers"
```

---

## Task 2: Текстовые блоки — text, heading, quote

**Files:**
- Modify: `build.py` (после `render_journal_index`, ~строка 1480)
- Test: `tests/test_materials.py`

- [ ] **Шаг 1: Написать тесты** — добавить класс в `tests/test_materials.py`:

```python
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
```

- [ ] **Шаг 2: Запустить — FAIL** (`render_block` не существует).

Run: `python3 -m unittest tests.test_materials.TestTextBlocks -v`

- [ ] **Шаг 3: Реализовать** — вставить в `build.py` после функции `render_journal_index()` (около строки 1480):

```python
# ═══════════════════════════════════════════════════════════
#  МАТЕРИАЛЫ ИЗ БЛОКОВ (track A)
# ═══════════════════════════════════════════════════════════

def _blk_text(b):
    return f'<div class="bl bl-text">{md_to_html(b.get("text", ""))}</div>'

def _blk_heading(b):
    return f'<div class="bl bl-heading"><h2>{esc(b.get("text", ""))}</h2></div>'

def _blk_quote(b):
    cite = b.get("cite", "")
    cite_html = f'<cite>{esc(cite)}</cite>' if cite else ""
    return (f'<div class="bl bl-quote"><blockquote>{esc(b.get("text", ""))}'
            f'{cite_html}</blockquote></div>')

_BLOCK_RENDERERS = {
    "text": _blk_text,
    "heading": _blk_heading,
    "quote": _blk_quote,
}

def render_block(block):
    """Диспетчер блока материала по полю type. Неизвестный тип → пустая строка."""
    fn = _BLOCK_RENDERERS.get(block.get("type", ""))
    return fn(block) if fn else ""
```

- [ ] **Шаг 4: Запустить — PASS.**

Run: `python3 -m unittest tests.test_materials.TestTextBlocks -v`
Expected: PASS (5 тестов).

- [ ] **Шаг 5: Commit**

```bash
git add build.py tests/test_materials.py
git commit -m "feat: text/heading/quote material blocks + render_block dispatcher"
```

---

## Task 3: Медиа-блоки — photo, split, gallery, embed

**Files:**
- Modify: `build.py` (рядом с блоками из Task 2)
- Test: `tests/test_materials.py`

- [ ] **Шаг 1: Написать тесты:**

```python
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
```

- [ ] **Шаг 2: Запустить — FAIL.**

Run: `python3 -m unittest tests.test_materials.TestMediaBlocks -v`

- [ ] **Шаг 3: Реализовать** — добавить функции рядом с блоками Task 2 и дополнить `_BLOCK_RENDERERS`:

```python
def _blk_photo(b):
    img = esc(b.get("image", ""))
    cap = b.get("caption", "")
    cap_html = f'<figcaption class="bl-cap">{esc(cap)}</figcaption>' if cap else ""
    return (f'<figure class="bl bl-photo"><img src="{img}" loading="lazy" alt="{esc(cap)}"/>'
            f'{cap_html}</figure>')

def _blk_split(b):
    side = "left" if b.get("imageSide") == "left" else "right"
    img_html = f'<div class="bl-split-img"><img src="{esc(b.get("image", ""))}" loading="lazy" alt=""/></div>'
    txt_html = f'<div class="bl-split-text">{md_to_html(b.get("text", ""))}</div>'
    inner = (img_html + txt_html) if side == "left" else (txt_html + img_html)
    return f'<div class="bl bl-split bl-split--{side}"><div class="bl-split-grid">{inner}</div></div>'

def _blk_gallery(b):
    imgs = b.get("images") or []
    cells = "".join(f'<img src="{esc(i)}" loading="lazy" alt=""/>' for i in imgs)
    return f'<div class="bl bl-gallery" data-count="{len(imgs)}">{cells}</div>'

def _embed_id(provider, url):
    url = url or ""
    if provider == "youtube":
        m = re.search(r"(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})", url)
        return m.group(1) if m else ""
    if provider == "vimeo":
        m = re.search(r"vimeo\.com/(?:video/)?(\d+)", url)
        return m.group(1) if m else ""
    return ""

def _blk_embed(b):
    provider = b.get("provider", "")
    vid = _embed_id(provider, b.get("url", ""))
    if not vid:
        return ""
    if provider == "youtube":
        src = f'https://www.youtube.com/embed/{vid}'
    else:
        src = f'https://player.vimeo.com/video/{vid}'
    cap = b.get("caption", "")
    cap_html = f'<div class="bl-cap">{esc(cap)}</div>' if cap else ""
    return (f'<div class="bl bl-embed"><div class="bl-embed-frame">'
            f'<iframe src="{src}" loading="lazy" allowfullscreen '
            f'referrerpolicy="strict-origin-when-cross-origin"></iframe></div>{cap_html}</div>')
```

Дополнить словарь `_BLOCK_RENDERERS` (заменить его целиком на):

```python
_BLOCK_RENDERERS = {
    "text": _blk_text,
    "heading": _blk_heading,
    "quote": _blk_quote,
    "photo": _blk_photo,
    "split": _blk_split,
    "gallery": _blk_gallery,
    "embed": _blk_embed,
}
```

- [ ] **Шаг 4: Запустить — PASS** (6 тестов).

Run: `python3 -m unittest tests.test_materials.TestMediaBlocks -v`

- [ ] **Шаг 5: Commit**

```bash
git add build.py tests/test_materials.py
git commit -m "feat: photo/split/gallery/embed material blocks"
```

---

## Task 4: Блок подборки работ (picks)

**Files:**
- Modify: `build.py`
- Test: `tests/test_materials.py`

Блок `picks` берёт работы из глобального `artworks` (загружен в начале build.py) по полю `id`. Поля работы: `id`, `slug`, `title`, `artistName`, `price`, `priceFormatted`, `mainImage`.

- [ ] **Шаг 1: Написать тест** (использует реальные данные каталога — берём первый существующий id):

```python
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
```

- [ ] **Шаг 2: Запустить — FAIL** (`picks` не зарегистрирован).

Run: `python3 -m unittest tests.test_materials.TestPicksBlock -v`

- [ ] **Шаг 3: Реализовать** — добавить функцию и зарегистрировать тип:

```python
def _blk_picks(b):
    heading = esc(b.get("heading", ""))
    by_id = {w.get("id"): w for w in artworks}
    cards = ""
    for wid in (b.get("workIds") or []):
        w = by_id.get(wid)
        if not w:
            continue
        price = w.get("priceFormatted") or (str(w.get("price", "")) + " ₽")
        img = esc(w.get("mainImage", ""))
        cards += (f'<a class="pick" href="work-{w.get("slug", "")}.html" data-analytics="material-pick">'
                  f'<div class="pick-img"><img src="{img}" loading="lazy" alt="{esc(w.get("title", ""))}"/></div>'
                  f'<div class="pick-title">{esc(w.get("title", ""))}</div>'
                  f'<div class="pick-artist">{esc(w.get("artistName", ""))}</div>'
                  f'<div class="pick-row"><span class="pick-price">{esc(price)}</span>'
                  f'<span class="pick-buy">в магазин →</span></div></a>')
    head_html = f'<div class="picks-head">{heading}</div>' if heading else ""
    return f'<div class="bl bl-picks">{head_html}<div class="picks-grid">{cards}</div></div>'
```

Добавить в `_BLOCK_RENDERERS` строку `"picks": _blk_picks,`.

- [ ] **Шаг 4: Запустить — PASS** (2 теста).

Run: `python3 -m unittest tests.test_materials.TestPicksBlock -v`

- [ ] **Шаг 5: Commit**

```bash
git add build.py tests/test_materials.py
git commit -m "feat: picks block — shop works lookup by id"
```

---

## Task 5: Коллекция материалов + guard зарезервированных slug'ов + пример

**Files:**
- Create: `data/articles/kak-travyat-tsink.json`
- Modify: `build.py` (загрузка `articles`, функция проверки slug'ов)
- Test: `tests/test_materials.py`

- [ ] **Шаг 1: Создать пример материала** `data/articles/kak-travyat-tsink.json`:

```json
{
  "slug": "kak-travyat-tsink",
  "rubric": "na-paltsakh",
  "title": "Как травят цинк: кислота и игла",
  "titleEm": "кислота и игла",
  "lead": "Офорт по шагам — от грунтовки доски до первого оттиска. Без романтики, по делу.",
  "cover": "",
  "author": "редакция ЁPRST",
  "date": "2026-05-14",
  "readMins": 7,
  "featured": true,
  "order": 1,
  "blocks": [
    { "type": "text", "text": "Офорт начинается не с рисунка, а с **подготовки доски**. Цинковую пластину шлифуют, обезжиривают и покрывают кислотоупорным грунтом." },
    { "type": "heading", "text": "Где кислота делает свою работу" },
    { "type": "text", "text": "Там, где грунт снят иглой, металл оголён. Доску опускают в кислоту — и она вытравливает бороздки именно по этим линиям." },
    { "type": "quote", "text": "Кислота не прощает спешки — она проявляет ровно то, что ты ей доверил.", "cite": "Пётр Швецов" }
  ]
}
```

- [ ] **Шаг 2: Написать тест:**

```python
class TestArticlesCollection(unittest.TestCase):
    def test_articles_loaded(self):
        self.assertTrue(any(a.get("slug") == "kak-travyat-tsink" for a in build.articles))

    def test_reserved_slug_guard_raises(self):
        with self.assertRaises(ValueError):
            build.check_article_slugs([{"slug": "istoriya"}])

    def test_reserved_slug_guard_ok(self):
        build.check_article_slugs([{"slug": "normalnyy-slug"}])  # не должно бросать
```

- [ ] **Шаг 3: Запустить — FAIL.**

Run: `python3 -m unittest tests.test_materials.TestArticlesCollection -v`

- [ ] **Шаг 4: Реализовать** — добавить загрузку рядом с другими коллекциями (после строки 58 `materials = load_collection("materials")`):

```python
articles = load_collection("articles")    # материалы журнала (track A)
```

И функцию-guard (рядом с блоками материалов):

```python
def check_article_slugs(items):
    """Slug материала не должен совпадать с зарезервированными (рубрики, all)."""
    for a in items:
        if a.get("slug") in RESERVED_SLUGS:
            raise ValueError(f'Slug материала "{a.get("slug")}" зарезервирован под рубрику. Переименуйте.')
```

- [ ] **Шаг 5: Запустить — PASS** (3 теста).

Run: `python3 -m unittest tests.test_materials.TestArticlesCollection -v`

- [ ] **Шаг 6: Commit**

```bash
git add build.py data/articles/kak-travyat-tsink.json tests/test_materials.py
git commit -m "feat: load articles collection + reserved-slug guard + sample material"
```

---

## Task 6: Страница материала + запись в main loop

**Files:**
- Modify: `build.py` (`render_material_page`, главный цикл)
- Test: `tests/test_materials.py`

- [ ] **Шаг 1: Написать тест:**

```python
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
```

- [ ] **Шаг 2: Запустить — FAIL.**

Run: `python3 -m unittest tests.test_materials.TestMaterialPage -v`

- [ ] **Шаг 3: Реализовать** `render_material_page` (рядом с блоками):

```python
def render_material_page(article):
    slug = article.get("slug", "")
    canonical = f"{BASE_URL}/journal/{slug}.html"
    plain_title = strip_tags(article.get("title", ""))
    page_title = f"{plain_title} — Журнал ЁPRST · PRSTNK"
    desc = strip_tags(article.get("lead", ""))
    rub = article.get("rubric", "")
    rub_cls = f"rub-{rubric_color(rub)}"

    # заголовок с курсивным выделением titleEm
    h1 = esc(article.get("title", ""))
    em = article.get("titleEm", "")
    if em:
        h1 = h1.replace(esc(em), f"<em>{esc(em)}</em>", 1)

    meta_parts = [esc(article.get("author", "редакция ЁPRST"))]
    if article.get("readMins"):
        meta_parts.append(f'{article["readMins"]} мин')
    if article.get("date"):
        meta_parts.append(fmt_date_ru(article["date"]))

    blocks_html = "\n".join(render_block(b) for b in article.get("blocks", []))

    body = f'''<article class="material">
  <header class="material-head">
    <div class="material-kicker {rub_cls}">{rubric_label(rub)}</div>
    <h1 class="material-title">{h1}</h1>
    <p class="material-lead">{esc(article.get("lead", ""))}</p>
    <div class="material-meta">{" · ".join(meta_parts)}</div>
  </header>
  <div class="material-body">
{blocks_html}
  </div>
  <a class="material-back" href="materials">← Все материалы</a>
</article>'''

    return (f'{head(page_title, desc, canonical, extra_css="journal.css")}{HEADER}\n'
            f'<div class="jn-wrap" style="padding:0;">\n{body}\n</div>\n{FOOTER}')
```

- [ ] **Шаг 4: Запустить — PASS** (5 тестов).

Run: `python3 -m unittest tests.test_materials.TestMaterialPage -v`

- [ ] **Шаг 5: Подключить в главный цикл** — в блоке `if __name__ == "__main__":` (после записи `journal.html`, около строки 1756) добавить:

```python
    check_article_slugs(articles)
    (ROOT / "journal").mkdir(exist_ok=True)
    for a in articles:
        (ROOT / "journal" / f'{a["slug"]}.html').write_text(clean_links(render_material_page(a)))
    print(f"  ✓ {len(articles)} страниц материалов (journal/<slug>.html)")
```

- [ ] **Шаг 6: Запустить сборку — проверить файл**

```bash
python3 build.py 2>&1 | grep -E "(материал|Error|Traceback)"
ls journal/kak-travyat-tsink.html && grep -c "material-title" journal/kak-travyat-tsink.html
```

Expected: строка `✓ N страниц материалов`, файл существует, grep = 1.

- [ ] **Шаг 7: Commit**

```bash
git add build.py
git commit -m "feat: render_material_page + wire material pages into build"
```

---

## Task 7: Ритм-лента + страница «Все материалы»

**Files:**
- Modify: `build.py` (`_feed_*`, `_feed_rhythm`, `render_materials_index`, главный цикл)
- Test: `tests/test_materials.py`

Эталон — `_materials-feed-v3.html`. Цикл модулей: `hero`(1) → `split`(2) → `band`(1) → `split2`(4) → `textband`(3).

- [ ] **Шаг 1: Написать тест:**

```python
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
```

- [ ] **Шаг 2: Запустить — FAIL.**

Run: `python3 -m unittest tests.test_materials.TestFeed -v`

- [ ] **Шаг 3: Реализовать** — модули ленты, ритм и индекс (рядом с блоками):

```python
def _feed_meta(a):
    parts = []
    if a.get("readMins"):
        parts.append(f'{a["readMins"]} мин')
    if a.get("date"):
        parts.append(fmt_date_ru(a["date"]))
    return " · ".join(parts)

def _feed_url(a):
    return f'journal/{a.get("slug", "")}'

def _feed_rub(a):
    rub = a.get("rubric", "")
    return f'<div class="rub rub-{rubric_color(rub)}">{rubric_label(rub)}</div>'

def _feed_img(a, label="фото"):
    cover = esc(a.get("cover", ""))
    if cover:
        return f'<div class="feed-img"><img src="{cover}" loading="lazy" alt=""/></div>'
    return f'<div class="feed-img feed-img--ph">{label}</div>'

def _feed_hero(a):
    return (f'<a class="feed-hero" href="{_feed_url(a)}">'
            f'{_feed_img(a)}'
            f'<div class="feed-hero-body">{_feed_rub(a)}'
            f'<h2 class="feed-h2">{esc(a.get("title", ""))}</h2>'
            f'<p class="feed-lead">{esc(a.get("lead", ""))}</p>'
            f'<div class="feed-meta">{_feed_meta(a)}</div></div></a>')

def _feed_card(a):
    return (f'<a class="feed-card" href="{_feed_url(a)}">{_feed_img(a)}'
            f'<div class="feed-card-body">{_feed_rub(a)}'
            f'<h3 class="feed-h3">{esc(a.get("title", ""))}</h3>'
            f'<div class="feed-meta">{_feed_meta(a)}</div></div></a>')

def _feed_split(items):
    cells = "".join(f'<div class="feed-half">{_feed_card(a)}</div>' for a in items)
    return f'<div class="feed-split">{cells}</div>'

def _feed_band(a):
    return (f'<a class="feed-band" href="{_feed_url(a)}">'
            f'<div class="feed-band-body">{_feed_rub(a)}'
            f'<h2 class="feed-h2">{esc(a.get("title", ""))}</h2>'
            f'<p class="feed-lead">{esc(a.get("lead", ""))}</p>'
            f'<div class="feed-meta">{_feed_meta(a)}</div></div>'
            f'{_feed_img(a, "панорама")}</a>')

def _feed_split2(items):
    feat = items[0]
    rest = items[1:]
    feat_html = (f'<a class="feed-feat" href="{_feed_url(feat)}">{_feed_img(feat)}'
                 f'<div class="feed-feat-body">{_feed_rub(feat)}'
                 f'<h3 class="feed-h3">{esc(feat.get("title", ""))}</h3>'
                 f'<p class="feed-lead">{esc(feat.get("lead", ""))}</p>'
                 f'<div class="feed-meta">{_feed_meta(feat)}</div></div></a>')
    stack = ""
    for a in rest:
        stack += (f'<a class="feed-it" href="{_feed_url(a)}">{_feed_rub(a)}'
                  f'<h4 class="feed-h4">{esc(a.get("title", ""))}</h4>'
                  f'<div class="feed-meta">{_feed_meta(a)}</div></a>')
    return f'<div class="feed-split2">{feat_html}<div class="feed-stack">{stack}</div></div>'

def _feed_textband(items):
    rows = ""
    for n, a in enumerate(items, start=1):
        rows += (f'<a class="feed-row" href="{_feed_url(a)}">'
                 f'<span class="feed-n">{n:02d}</span>'
                 f'<div><h3 class="feed-h3">{esc(a.get("title", ""))}</h3>{_feed_rub(a)}</div>'
                 f'<span class="feed-mt">{_feed_meta(a)}</span></a>')
    return f'<div class="feed-textband">{rows}</div>'

def _feed_rhythm(items):
    q = list(items)
    out = []
    cycle = [("hero", 1), ("split", 2), ("band", 1), ("split2", 4), ("textband", 3)]
    ci = 0
    while q:
        mod, take = cycle[ci % len(cycle)]
        ci += 1
        chunk = q[:take]
        del q[:take]
        if not chunk:
            continue
        if mod == "hero":
            out.append(_feed_hero(chunk[0]))
        elif mod == "split":
            out.append(_feed_split(chunk))
        elif mod == "band":
            out.append(_feed_band(chunk[0]))
        elif mod == "split2":
            out.append(_feed_split2(chunk))
        elif mod == "textband":
            out.append(_feed_textband(chunk))
    return "\n".join(out)

def _materials_sorted():
    return sorted(articles, key=lambda a: a.get("date", ""), reverse=True)

def render_materials_index():
    canonical = f"{BASE_URL}/materials.html"
    title = "Все материалы — Журнал ЁPRST · PRSTNK"
    desc = "Все материалы журнала ЁPRST: разговоры, техники, история, как смотреть графику."
    feed = _feed_rhythm(_materials_sorted())
    body = f'''<div class="materials-page jn-wrap" style="padding:0;">
  <div class="materials-head">
    <h1>Все <em>материалы</em></h1>
    <span class="materials-count">— {len(articles)} {_plural(len(articles), "материал", "материала", "материалов")}</span>
  </div>
  <div class="materials-feed">
{feed}
  </div>
  <div class="materials-more"><button type="button" disabled>Загрузить ещё</button></div>
</div>'''
    return (f'{head(title, desc, canonical, extra_css="journal.css")}{HEADER}\n'
            f'{body}\n{FOOTER}')
```

- [ ] **Шаг 4: Запустить — PASS** (4 теста).

Run: `python3 -m unittest tests.test_materials.TestFeed -v`

- [ ] **Шаг 5: Подключить в главный цикл** — после записи страниц материалов (Task 6) добавить:

```python
    (ROOT / "materials.html").write_text(clean_links(render_materials_index()))
    print("  ✓ materials.html — все материалы")
```

- [ ] **Шаг 6: Сборка**

```bash
python3 build.py 2>&1 | grep -E "(материал|Error|Traceback)"
grep -c "materials-feed" materials.html
```

Expected: `✓ materials.html — все материалы`, grep = 1.

- [ ] **Шаг 7: Commit**

```bash
git add build.py
git commit -m "feat: rhythm feed + render_materials_index (Все материалы)"
```

---

## Task 8: Страницы рубрик

**Files:**
- Modify: `build.py` (`render_rubric_page`, главный цикл)
- Test: `tests/test_materials.py`

- [ ] **Шаг 1: Написать тест:**

```python
class TestRubricPage(unittest.TestCase):
    def test_rubric_page_lists_only_its_rubric(self):
        html = build.render_rubric_page("na-paltsakh")
        self.assertIn("На пальцах", html)
        self.assertIn("journal/kak-travyat-tsink", html)  # этот материал — na-paltsakh

    def test_rubric_page_links_css(self):
        html = build.render_rubric_page("razgovory")
        self.assertIn('href="journal.css"', html)
```

- [ ] **Шаг 2: Запустить — FAIL.**

Run: `python3 -m unittest tests.test_materials.TestRubricPage -v`

- [ ] **Шаг 3: Реализовать** `render_rubric_page` (рядом с лентой):

```python
def render_rubric_page(rubric):
    label = rubric_label(rubric)
    color = rubric_color(rubric)
    canonical = f"{BASE_URL}/journal/{rubric}.html"
    title = f"{label} — Журнал ЁPRST · PRSTNK"
    desc = f"Материалы рубрики «{label}» журнала ЁPRST."
    items = [a for a in _materials_sorted() if a.get("rubric") == rubric]
    feed = _feed_rhythm(items)
    body = f'''<div class="materials-page jn-wrap" style="padding:0;">
  <div class="materials-head">
    <h1 class="rub-{color}">{label}</h1>
    <span class="materials-count">— {len(items)} {_plural(len(items), "материал", "материала", "материалов")}</span>
  </div>
  <div class="materials-feed">
{feed}
  </div>
  <a class="material-back" href="materials">← Все материалы</a>
</div>'''
    return (f'{head(title, desc, canonical, extra_css="journal.css")}{HEADER}\n'
            f'{body}\n{FOOTER}')
```

- [ ] **Шаг 4: Запустить — PASS** (2 теста).

Run: `python3 -m unittest tests.test_materials.TestRubricPage -v`

- [ ] **Шаг 5: Подключить в главный цикл** — после `materials.html`:

```python
    for rub_slug in RUBRICS:
        (ROOT / "journal" / f"{rub_slug}.html").write_text(clean_links(render_rubric_page(rub_slug)))
    print(f"  ✓ {len(RUBRICS)} страниц рубрик (journal/<rubric>.html)")
```

- [ ] **Шаг 6: Сборка**

```bash
python3 build.py 2>&1 | grep -E "(рубрик|Error|Traceback)"
ls journal/na-paltsakh.html
```

Expected: `✓ 4 страниц рубрик`, файл существует.

- [ ] **Шаг 7: Commit**

```bash
git add build.py
git commit -m "feat: rubric pages (fixes rubricator)"
```

---

## Task 9: Витрина /journal — свежие материалы и рубрикатор из articles

**Files:**
- Modify: `build.py` `render_journal_index()` (строки ~1304-1357)
- Test: `tests/test_materials.py`

Сейчас «Свежие материалы» и рубрикатор берут данные из статей выпуска. Переключаем на `articles`.

- [ ] **Шаг 1: Написать тест:**

```python
class TestJournalIndexUsesArticles(unittest.TestCase):
    def setUp(self):
        self.html = build.render_journal_index()

    def test_rubricator_links_to_rubric_pages(self):
        self.assertIn('href="journal/na-paltsakh"', self.html)

    def test_rubricator_uses_rubric_labels(self):
        self.assertIn("На пальцах", self.html)

    def test_all_materials_link_present(self):
        self.assertIn('href="materials"', self.html)
```

- [ ] **Шаг 2: Запустить — FAIL** (рубрикатор пока со старыми лейблами «Кураторская» и т.п.).

Run: `python3 -m unittest tests.test_materials.TestJournalIndexUsesArticles -v`

- [ ] **Шаг 3: Реализовать** — заменить блок RUBRIC BAR в `render_journal_index()` (строки ~1338-1357) на:

```python
    # ── RUBRIC BAR ─────────────────────────────────────────────────────────
    rub_counts = {}
    for a in articles:
        r = a.get("rubric", "")
        if r in RUBRICS:
            rub_counts[r] = rub_counts.get(r, 0) + 1
    total_count = len(articles)

    rub_links = [f'<a href="materials" class="on">Всё <sup>{total_count}</sup></a>']
    for rub_slug, info in RUBRICS.items():
        cnt = rub_counts.get(rub_slug, 0)
        if cnt:
            rub_links.append(f'<a href="journal/{rub_slug}">{info["label"]} <sup>{cnt}</sup></a>')

    rubric_html = f'''<nav class="rubric-bar" aria-label="Рубрики журнала">
  <span class="rb-label">Рубрики</span>
  {"".join(rub_links)}
</nav>'''
```

- [ ] **Шаг 4: Заменить блок ART HEADER** (строки ~1359-1363) — добавить ссылку «Все материалы»:

```python
    # ── ART HEADER ─────────────────────────────────────────────────────────
    art_header_html = '''<div class="art-header">
  <div class="art-header-label">— <b>Свежие материалы</b></div>
  <a class="art-header-meta" href="materials">Все материалы →</a>
</div>'''
```

- [ ] **Шаг 5: Переключить EDITORIAL GRID на свежие материалы** — заменить присвоения данных в начале функции (строки ~1306-1311) на:

```python
    fresh        = sorted(articles, key=lambda a: a.get("date", ""), reverse=True)
    hero_art     = next((a for a in fresh if a.get("featured")), fresh[0] if fresh else {})
    rest         = [a for a in fresh if a is not hero_art]
    lead_art     = rest[0] if rest else {}
    sec_arts     = rest[1:3]
    feature_art  = rest[3] if len(rest) > 3 else {}
    lenta_items  = materials[:4]
    recent_iss   = issues[:3]
```

Затем в HERO/GRID заменить обращения к полю `kicker` на рубрику. Заменить строки `h_kicker`, `lead_rub_cls`, `sec_rub_cls`, `feat_rub_cls` и `_jrn_rub_class(...)` на использование рубрики материала:

- `h_kicker = rubric_label(hero_art.get("rubric", ""))` (вместо `hero_art.get("kicker", ...)`)
- `lead_rub_cls = "rub-" + rubric_color(lead_art.get("rubric", ""))`
- в `sec_html`: `sec_rub_cls = "rub-" + rubric_color(sa.get("rubric", ""))`, а в разметке `<div class="rub {sec_rub_cls}">{rubric_label(sa.get("rubric",""))}</div>`
- в lead-разметке: `<div class="rub {lead_rub_cls}">{rubric_label(lead_art.get("rubric",""))}</div>`
- ссылки «Читать →» материалов: `lead_url = f'journal/{lead_art.get("slug","")}'` (вместо zine-якорей); аналогично `sec_url = f'journal/{sa.get("slug","")}'`, `feat_url = f'journal/{feature_art.get("slug","")}'`, `h_cta = f'<a class="hero-cta" href="journal/{hero_art.get("slug","")}">Читать →</a>'`
- `feat_rub_cls = "rub-" + rubric_color(feature_art.get("rubric",""))` и в разметке фичера `{rubric_label(feature_art.get("rubric",""))}`

(Блоки «Лента» и «Выпуски» в функции не трогаем.)

- [ ] **Шаг 6: Запустить тесты — PASS.**

```bash
python3 -m unittest tests.test_materials.TestJournalIndexUsesArticles -v
python3 -m unittest tests.test_journal -v
```

Expected: новые 3 теста PASS. Тесты `test_journal.py` (структура hero/rubric-bar/issues/lenta) — по-прежнему PASS.

- [ ] **Шаг 7: Сборка + проверка**

```bash
python3 build.py 2>&1 | grep -E "(journal|Error|Traceback)"
grep -c 'href="journal/na-paltsakh"' journal.html
```

Expected: grep = 1.

- [ ] **Шаг 8: Commit**

```bash
git add build.py
git commit -m "feat: journal index fresh materials + rubricator from articles"
```

---

## Task 10: Стили блоков и ленты в journal.css

**Files:**
- Modify: `journal.css`
- Test: визуальная сборка

Перенести проверенные стили из эталонов `_blocks-preview.html` (классы `.material*`, `.bl-*`) и `_materials-feed-v3.html` (классы `.feed-*`, `.materials-*`), но с префиксом `.feed-` для модулей ленты (чтобы не конфликтовать с `.hero` на `/journal`).

- [ ] **Шаг 1: Добавить в конец `journal.css`** блок стилей:

```css
/* ═══ МАТЕРИАЛ (страница из блоков) ═══ */
.material { max-width: 1000px; margin: 0 auto; padding: 0 24px 80px; }
.material-head { max-width: 680px; margin: 0 auto; padding: 56px 0 40px; }
.material-kicker { font-family: var(--f-mono); font-size: 11px; letter-spacing: .14em; text-transform: uppercase; margin-bottom: 22px; }
.material-title { font-family: var(--f-display); font-weight: 900; font-size: clamp(32px,4.4vw,56px); line-height: .98; letter-spacing: -.03em; margin: 0 0 24px; }
.material-title em { font-style: italic; color: var(--c-alyi); }
.material-lead { font-family: var(--f-text); font-weight: 300; font-size: 21px; line-height: 1.5; color: rgba(20,20,19,.72); margin: 0 0 26px; }
.material-meta { font-family: var(--f-mono); font-size: 11px; letter-spacing: .04em; color: rgba(20,20,19,.45); display: flex; gap: 16px; flex-wrap: wrap; padding-top: 18px; border-top: 1px solid rgba(20,20,19,.12); }
.material-body { max-width: 680px; margin: 0 auto; }
.material-back { display: inline-block; max-width: 680px; margin: 40px auto 0; font-family: var(--f-mono); font-size: 11px; letter-spacing: .06em; text-transform: uppercase; color: var(--ink); text-decoration: none; border-bottom: 1px solid var(--ink); }

/* блоки */
.bl { margin: 0 0 34px; }
.bl-text p { font-family: var(--f-text); font-size: 19px; line-height: 1.72; margin: 0 0 20px; }
.bl-heading h2 { font-family: var(--f-display); font-weight: 700; font-size: 28px; line-height: 1.05; letter-spacing: -.02em; margin: 18px 0 4px; }
.bl-photo { margin: 0 0 34px; }
.bl-photo img { width: 100%; border-radius: 4px; display: block; }
.bl-cap { font-family: var(--f-mono); font-size: 11px; color: rgba(20,20,19,.45); margin-top: 9px; line-height: 1.4; }
.bl-split-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 28px; align-items: center; }
.bl-split img { width: 100%; border-radius: 3px; display: block; }
.bl-split-text p { font-family: var(--f-text); font-size: 17px; line-height: 1.6; margin: 0 0 14px; }
.bl-gallery { display: grid; gap: 12px; }
.bl-gallery[data-count="2"] { grid-template-columns: repeat(2,1fr); }
.bl-gallery[data-count="3"] { grid-template-columns: repeat(3,1fr); }
.bl-gallery[data-count="4"] { grid-template-columns: repeat(2,1fr); }
.bl-gallery img { width: 100%; aspect-ratio: 1; object-fit: cover; border-radius: 3px; display: block; }
.bl-quote blockquote { margin: 0; border-left: 3px solid var(--c-alyi); padding: 4px 0 4px 26px; font-family: var(--f-display); font-weight: 700; font-style: italic; font-size: 27px; line-height: 1.18; letter-spacing: -.02em; }
.bl-quote cite { display: block; font-family: var(--f-mono); font-style: normal; font-weight: 400; font-size: 11px; letter-spacing: .06em; text-transform: uppercase; color: rgba(20,20,19,.45); margin-top: 16px; }
.bl-embed-frame { position: relative; aspect-ratio: 16/9; }
.bl-embed-frame iframe { position: absolute; inset: 0; width: 100%; height: 100%; border: 0; border-radius: 4px; }
.bl-picks { margin: 48px 0 40px; }
.picks-head { font-family: var(--f-mono); font-size: 11px; letter-spacing: .1em; text-transform: uppercase; color: rgba(20,20,19,.5); margin-bottom: 16px; }
.picks-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 20px; }
.pick { text-decoration: none; color: inherit; }
.pick-img { aspect-ratio: 4/5; overflow: hidden; border-radius: 3px; margin-bottom: 12px; background: #e8e4dc; }
.pick-img img { width: 100%; height: 100%; object-fit: cover; display: block; }
.pick-title { font-family: var(--f-display); font-weight: 600; font-size: 15px; line-height: 1.15; margin-bottom: 4px; }
.pick-artist { font-family: var(--f-text); font-size: 13px; color: rgba(20,20,19,.55); margin-bottom: 8px; }
.pick-row { display: flex; justify-content: space-between; align-items: baseline; }
.pick-price { font-family: var(--f-mono); font-size: 14px; font-weight: 500; }
.pick-buy { font-family: var(--f-mono); font-size: 10px; letter-spacing: .06em; text-transform: uppercase; border-bottom: 1.5px solid var(--ink); padding-bottom: 1px; }

/* ═══ ЛЕНТА «Все материалы» (ритм-модули) ═══ */
.materials-page { max-width: 1080px; margin: 0 auto; padding: 0 32px 80px; }
.materials-head { padding: 46px 0 22px; border-bottom: 2px solid var(--ink); display: flex; justify-content: space-between; align-items: baseline; }
.materials-head h1 { font-family: var(--f-display); font-weight: 900; font-size: clamp(30px,4vw,46px); letter-spacing: -.03em; margin: 0; }
.materials-head h1 em { font-style: italic; color: var(--c-alyi); }
.materials-count { font-family: var(--f-mono); font-size: 12px; letter-spacing: .05em; color: rgba(20,20,19,.4); }
.materials-feed a { text-decoration: none; color: inherit; }
.feed-img { background: linear-gradient(135deg,#e6e1d8,#d4cebf); overflow: hidden; }
.feed-img img { width: 100%; height: 100%; object-fit: cover; display: block; }
.feed-img--ph { display: flex; align-items: center; justify-content: center; font-family: var(--f-mono); font-size: 10px; letter-spacing: .08em; text-transform: uppercase; color: rgba(20,20,19,.3); }
.feed-h2 { font-family: var(--f-display); font-weight: 900; font-size: clamp(24px,3vw,40px); line-height: .96; letter-spacing: -.03em; margin: 0 0 14px; }
.feed-h3 { font-family: var(--f-display); font-weight: 700; font-size: clamp(18px,2vw,24px); line-height: 1; letter-spacing: -.025em; margin: 0 0 10px; }
.feed-h4 { font-family: var(--f-display); font-weight: 600; font-size: 18px; line-height: 1.05; letter-spacing: -.02em; margin: 0 0 9px; }
.feed-lead { font-family: var(--f-text); font-weight: 300; font-size: 16px; line-height: 1.5; color: rgba(20,20,19,.65); margin: 0 0 18px; }
.feed-meta { font-family: var(--f-mono); font-size: 10px; letter-spacing: .04em; color: rgba(20,20,19,.4); display: flex; gap: 10px; }
.feed-hero { display: grid; grid-template-columns: 1.55fr 1fr; border-top: 2px solid var(--ink); border-bottom: 1px solid var(--ink); }
.feed-hero .feed-img { aspect-ratio: 16/11; border-right: 1px solid var(--ink); }
.feed-hero-body { padding: 32px 34px; display: flex; flex-direction: column; justify-content: center; }
.feed-split { display: grid; grid-template-columns: 1fr 1fr; border-bottom: 1px solid var(--ink); }
.feed-half:first-child { border-right: 1px solid var(--ink); }
.feed-half .feed-img { aspect-ratio: 16/9; border-bottom: 1px solid rgba(20,20,19,.12); }
.feed-card-body { padding: 16px 26px 24px; }
.feed-band { display: grid; grid-template-columns: 1fr 1.3fr; border-bottom: 2px solid var(--ink); }
.feed-band-body { padding: 26px 30px; border-right: 1px solid var(--ink); display: flex; flex-direction: column; justify-content: center; }
.feed-band .feed-img { aspect-ratio: 21/9; }
.feed-split2 { display: grid; grid-template-columns: 1fr 1fr; border-bottom: 1px solid var(--ink); }
.feed-feat { border-right: 1px solid var(--ink); display: block; }
.feed-feat .feed-img { aspect-ratio: 4/5; }
.feed-feat-body { padding: 22px 26px 26px; }
.feed-stack { display: flex; flex-direction: column; }
.feed-it { padding: 20px 24px; border-bottom: 1px solid rgba(20,20,19,.12); flex: 1; display: flex; flex-direction: column; justify-content: center; }
.feed-it:last-child { border-bottom: none; }
.feed-textband { border-bottom: 1px solid var(--ink); }
.feed-row { display: grid; grid-template-columns: 64px 1fr auto; gap: 20px; align-items: baseline; padding: 16px 0; border-top: 1px solid rgba(20,20,19,.12); }
.feed-row:first-child { border-top: none; }
.feed-n { font-family: var(--f-mono); font-size: 12px; color: rgba(20,20,19,.3); }
.feed-mt { font-family: var(--f-mono); font-size: 10px; color: rgba(20,20,19,.4); white-space: nowrap; }
.materials-more { text-align: center; padding: 46px 0 0; }
.materials-more button { font-family: var(--f-mono); font-size: 12px; letter-spacing: .08em; text-transform: uppercase; background: none; border: 1.5px solid var(--ink); color: var(--ink); padding: 14px 28px; border-radius: 2px; opacity: .5; }

@media (max-width: 780px) {
  .bl-split-grid, .picks-grid { grid-template-columns: 1fr; }
  .feed-hero, .feed-split, .feed-band, .feed-split2 { grid-template-columns: 1fr; }
  .feed-hero .feed-img, .feed-band-body, .feed-feat, .feed-half:first-child { border-right: none; }
  .feed-band-body, .feed-half:first-child { border-bottom: 1px solid var(--ink); }
  .feed-row { grid-template-columns: 1fr; }
  .feed-n, .feed-mt { display: none; }
}
```

- [ ] **Шаг 2: Сборка + визуальная проверка**

```bash
python3 build.py
python3 -m http.server 8899 --directory /Users/artemgrinberg/prstnk-site &
open http://localhost:8899/journal/kak-travyat-tsink
open http://localhost:8899/materials
```

Проверить: страница материала из блоков выглядит как `_blocks-preview.html`; «Все материалы» — как `_materials-feed-v3.html` (чередование модулей).

- [ ] **Шаг 3: Commit**

```bash
git add journal.css
git commit -m "feat: material + feed styles in journal.css"
```

---

## Task 11: Конфиг Sveltia — коллекция «Материалы»

**Files:**
- Modify: `admin/config.yml`

- [ ] **Шаг 1: Переименовать лейбл ленты** — найти в `admin/config.yml` коллекцию с `folder: "data/materials"` и заменить её `label` на `"Лента"`.

- [ ] **Шаг 2: Добавить коллекцию «Материалы»** — вставить в раздел `collections:` (после коллекции `issues`):

```yaml
  - name: "articles"
    label: "Материалы"
    folder: "data/articles"
    extension: "json"
    format: "json"
    create: true
    slug: "{{slug}}"
    identifier_field: "title"
    fields:
      - { name: "title", label: "Заголовок", widget: "string" }
      - { name: "titleEm", label: "Курсивная часть заголовка (необяз.)", widget: "string", required: false }
      - { name: "slug", label: "Адрес (slug, латиницей)", widget: "string" }
      - name: "rubric"
        label: "Рубрика"
        widget: "select"
        options:
          - { label: "Разговоры", value: "razgovory" }
          - { label: "На пальцах", value: "na-paltsakh" }
          - { label: "История", value: "istoriya" }
          - { label: "Как смотреть", value: "kak-smotret" }
      - { name: "lead", label: "Лид", widget: "text" }
      - { name: "cover", label: "Обложка (необяз.)", widget: "image", required: false }
      - { name: "author", label: "Автор", widget: "string", default: "редакция ЁPRST" }
      - { name: "date", label: "Дата", widget: "datetime" }
      - { name: "readMins", label: "Время чтения (мин)", widget: "number", value_type: "int" }
      - { name: "featured", label: "В герои витрины", widget: "boolean", default: false }
      - { name: "order", label: "Порядок", widget: "number", required: false, value_type: "int" }
      - name: "blocks"
        label: "Блоки материала"
        widget: "list"
        types:
          - { label: "Абзац", name: "text", widget: "object", fields: [ { name: "text", label: "Текст", widget: "markdown" } ] }
          - { label: "Подзаголовок", name: "heading", widget: "object", fields: [ { name: "text", label: "Текст", widget: "string" } ] }
          - label: "Фото на всю ширину"
            name: "photo"
            widget: "object"
            fields:
              - { name: "image", label: "Фото", widget: "image" }
              - { name: "caption", label: "Подпись", widget: "string", required: false }
          - label: "Текст + фото рядом"
            name: "split"
            widget: "object"
            fields:
              - { name: "text", label: "Текст", widget: "markdown" }
              - { name: "image", label: "Фото", widget: "image" }
              - { name: "imageSide", label: "Фото слева/справа", widget: "select", options: ["left", "right"], default: "right" }
          - label: "Галерея"
            name: "gallery"
            widget: "object"
            fields: [ { name: "images", label: "Фото", widget: "list", field: { name: "image", widget: "image" } } ]
          - label: "Цитата"
            name: "quote"
            widget: "object"
            fields:
              - { name: "text", label: "Цитата", widget: "text" }
              - { name: "cite", label: "Автор цитаты", widget: "string", required: false }
          - label: "Подборка работ (магазин)"
            name: "picks"
            widget: "object"
            fields:
              - { name: "heading", label: "Заголовок подборки", widget: "string" }
              - { name: "workIds", label: "ID работ из каталога", widget: "list", field: { name: "id", widget: "string" } }
          - label: "Видео / встройка"
            name: "embed"
            widget: "object"
            fields:
              - { name: "provider", label: "Источник", widget: "select", options: ["youtube", "vimeo"] }
              - { name: "url", label: "Ссылка", widget: "string" }
              - { name: "caption", label: "Подпись", widget: "string", required: false }
```

- [ ] **Шаг 2: Проверить, что YAML валиден**

```bash
python3 -c "import yaml; yaml.safe_load(open('admin/config.yml')); print('YAML ok')"
```

Expected: `YAML ok`. (Если `yaml` не установлен — пропустить, Sveltia провалидирует в браузере.)

- [ ] **Шаг 3: Commit**

```bash
git add admin/config.yml
git commit -m "feat: Sveltia config — Материалы collection + relabel Лента"
```

---

## Task 12: Перенос статей выпуска 04, финальная проверка, очистка

**Files:**
- Create: `data/articles/<slug>.json` (по числу статей в выпуске 04)
- Delete: `_blocks-preview.html`, `_materials-feed.html`, `_materials-feed-v2.html`, `_materials-feed-v3.html`

- [ ] **Шаг 1: Посмотреть статьи выпуска 04**

```bash
python3 -c "import json,pathlib; d=json.loads(pathlib.Path('data/issues/04.json').read_text()); [print(i, a.get('kicker'), '|', a.get('title')) for i,a in enumerate(d.get('articles',[]))]"
```

- [ ] **Шаг 2: Для каждой статьи создать `data/articles/<slug>.json`** в новом формате. Маппинг рубрик по `kicker`:
  - содержит «разговор»/«интервью» → `razgovory`
  - содержит «техник»/«на пальцах»/«как» → `na-paltsakh`
  - содержит «истори» → `istoriya`
  - содержит «смотреть»/«коллекци»/«подбор» → `kak-smotret`
  - иначе → `razgovory` (поправить вручную при сомнении)

Тело: `body` (markdown) → один блок `{"type":"text","text": <body>}` (можно затем руками разбить на `heading`/`text`); `pullquote` → `{"type":"quote","text":..,"cite":..}`; `picks` (если есть id работ) → `{"type":"picks","heading":<picksIntro или "Работы">,"workIds":[..]}`; `bodyAfter` → ещё `text`. Проставить `date` (из периода выпуска, напр. `"2026-05-10"`), `readMins`, `author` (из `credits` или «редакция ЁPRST»), уникальный `slug` (не из `RESERVED_SLUGS`), `order`.

Пример структуры одного перенесённого файла:

```json
{
  "slug": "shvetsov-boloto",
  "rubric": "razgovory",
  "title": "Пётр Швецов: «Болото — место, где земля и небо договариваются»",
  "titleEm": "земля и небо",
  "lead": "Большой разговор о сериях «Омск» и «Север-7».",
  "author": "редакция ЁPRST",
  "date": "2026-05-12",
  "readMins": 14,
  "featured": false,
  "order": 2,
  "blocks": [
    { "type": "text", "text": "…перенесённый body статьи…" },
    { "type": "quote", "text": "…pullquote…", "cite": "Пётр Швецов" }
  ]
}
```

- [ ] **Шаг 3: Полная сборка — без ошибок**

```bash
python3 build.py
```

Expected: завершается без `Error`/`Traceback`; в выводе строки про материалы, рубрики, «все материалы».

- [ ] **Шаг 4: Полный тест-сьют**

```bash
python3 -m unittest discover -s tests -v
```

Expected: все тесты PASS (`test_journal` + `test_materials`).

- [ ] **Шаг 5: Визуальная проверка ключевых страниц**

```bash
python3 -m http.server 8899 --directory /Users/artemgrinberg/prstnk-site &
open http://localhost:8899/journal
open http://localhost:8899/materials
open http://localhost:8899/journal/na-paltsakh
open http://localhost:8899/journal/kak-travyat-tsink
```

Проверить: рубрикатор кликается и ведёт на рабочие страницы рубрик; «Все материалы» — живая ритм-лента; страница материала из блоков.

- [ ] **Шаг 6: Удалить макеты-эталоны**

```bash
rm -f _blocks-preview.html _materials-feed.html _materials-feed-v2.html _materials-feed-v3.html
```

- [ ] **Шаг 7: Финальный коммит**

```bash
git add -A
git commit -m "feat: migrate issue-04 articles to materials + cleanup mockups

- статьи выпуска 04 → data/articles/ в формате блоков
- удалены временные макеты"
```

- [ ] **Шаг 8: Push**

```bash
git fetch && git rebase origin/main && git push
```

---

## Self-review notes

- ✅ Покрытие спека: блоки (T2-T4), рубрики (T1), коллекция+guard (T5), страница материала (T6), «Все материалы» ритм-лента (T7), страницы рубрик (T8), витрина из articles (T9), стили (T10), Sveltia (T11), перенос (T12).
- ✅ Коллизии имён сняты: `render_material_page` (≠ `render_article`), `.feed-*` (≠ `.hero`), guard зарезервированных slug'ов.
- ✅ Python 3.9: нет вложенных f-строк с одинаковыми кавычками; сложные части вынесены в переменные.
- ✅ Графейсфул: пустые модули ленты пропускаются; неизвестный slug в picks/неизвестный тип блока → пропуск/пустая строка.
- ⚠️ Бесконечный скролл — кнопка-заглушка (disabled), JS позже (за рамками).
- ⚠️ Track B (выпуск, обложка-вёрстка, PDF) — отдельный спек/план.
- ⚠️ Перенос статей 04 (T12 шаг 2) — единственный ручной шаг, требующий смыслового решения по разбивке `body` на блоки и маппингу рубрик; остальное механическое.
```
