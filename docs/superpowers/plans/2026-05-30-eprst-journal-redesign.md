# ЁPRST Journal Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Переделать страницу журнала prstnk.ru/journal под новый редакционный дизайн из макета `_journal-mockup.html` — герой, редакционная сетка, лента, выпуски с цветными обложками.

**Architecture:** Существующие функции `render_journal_index()` и `issue_cover_svg()` в `build.py` заменяются. Новые стили выносятся в отдельный `journal.css`, подключаемый только на страницах журнала. Данные берутся из существующих `data/issues/*.json` и `data/materials/*.json` — схема немного расширяется (поле `coverColor` приводится к актуальным значениям, в статьи добавляются `image`, `rubric`, `date`).

**Tech Stack:** Python 3 stdlib, f-strings HTML templates, CSS Grid, inline SVG, `python3 -m unittest`

---

## File map

| Действие | Файл | Что меняется |
|----------|------|--------------|
| Modify | `build.py:209` | `head()` — добавить параметр `extra_css=""` |
| Modify | `build.py:1055` | `issue_cover_svg()` — заменить SVG-шаблон |
| Modify | `build.py:1243` | `render_journal_index()` — полная замена |
| Create | `journal.css` | Все стили редакционной вёрстки |
| Create | `tests/test_journal.py` | Тесты на цвет обложек и структуру HTML |
| Modify | `data/issues/01.json` | `coverColor: "ugol"` → `"hvoya"` |
| Modify | `data/issues/02.json` | добавить `coverColor: "fuxia"` |
| Modify | `data/issues/03.json` | добавить `coverColor: "kobalt"` |
| Modify | `data/issues/04.json` | в статьи добавить поля `rubric`, `date`, `image` |
| Delete | `_journal-mockup.html` | временный файл, убрать после сборки |

---

## Task 1: Обновить coverColor в JSON-файлах выпусков

**Files:**
- Modify: `data/issues/01.json`
- Modify: `data/issues/02.json`
- Modify: `data/issues/03.json`

- [ ] **Шаг 1: Обновить issue 01** — заменить `"coverColor": "ugol"` на `"coverColor": "hvoya"`

```json
// data/issues/01.json — только изменяемая строка:
"coverColor": "hvoya",
```

- [ ] **Шаг 2: Обновить issue 02** — открыть `data/issues/02.json`, добавить `"coverColor": "fuxia"` после поля `"coverImage"`.

Полная строка:
```json
  "coverColor": "fuxia",
```

- [ ] **Шаг 3: Обновить issue 03** — открыть `data/issues/03.json`, добавить `"coverColor": "kobalt"` после поля `"coverImage"`.

```json
  "coverColor": "kobalt",
```

- [ ] **Шаг 4: Проверить**

```bash
python3 -c "
import json; from pathlib import Path
for f in ['01','02','03','04']:
    d = json.loads(Path(f'data/issues/{f}.json').read_text())
    print(f, d.get('coverColor','MISSING'))
"
```

Ожидаемый вывод:
```
01 hvoya
02 fuxia
03 kobalt
04 alyi
```

- [ ] **Шаг 5: Commit**

```bash
git add data/issues/01.json data/issues/02.json data/issues/03.json
git commit -m "data: set coverColor for issues 01-03 (hvoya/fuxia/kobalt)"
```

---

## Task 2: Написать тесты

**Files:**
- Create: `tests/test_journal.py`

- [ ] **Шаг 1: Создать файл `tests/test_journal.py`**

```python
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
```

- [ ] **Шаг 2: Запустить — убедиться что тесты ПАДАЮТ** (функции ещё не переделаны)

```bash
python3 -m pytest tests/test_journal.py -v 2>&1 | head -40
```

Ожидаемый результат: несколько тестов FAIL или ERROR — это норма на этом этапе. Не двигаться дальше если `python3 build.py` сам падает с ошибкой.

- [ ] **Шаг 3: Commit**

```bash
git add tests/test_journal.py
git commit -m "test: add journal build tests (red)"
```

---

## Task 3: Добавить `extra_css` в `head()`

**Files:**
- Modify: `build.py` (функция `head`, строка ~209)

- [ ] **Шаг 1: Обновить сигнатуру и тело `head()`**

Найти строку:
```python
def head(title, description, canonical, og_type="website", extra_meta="", og_image=None):
```

Заменить на:
```python
def head(title, description, canonical, og_type="website", extra_meta="", og_image=None, extra_css=""):
```

Найти строку:
```python
  <link rel="stylesheet" href="prstnk.css"/>
  <script src="gate.js"></script>
```

Заменить на:
```python
  <link rel="stylesheet" href="prstnk.css"/>
  {f'<link rel="stylesheet" href="{extra_css}"/>' if extra_css else ""}
  <script src="gate.js"></script>
```

- [ ] **Шаг 2: Запустить тесты для `head()`**

```bash
python3 -m pytest tests/test_journal.py::TestHeadExtraCss -v
```

Ожидаемый результат: оба теста **PASS**.

- [ ] **Шаг 3: Убедиться что сборка не сломалась**

```bash
python3 build.py 2>&1 | tail -5
```

Ожидаемый результат: сборка завершается без `Error` (несколько `✓` строк).

- [ ] **Шаг 4: Commit**

```bash
git add build.py
git commit -m "feat: add extra_css param to head()"
```

---

## Task 4: Создать `journal.css`

**Files:**
- Create: `journal.css`

Это стили из `_journal-mockup.html`, адаптированные под основной сайт (без `.sh`, `.mk` — используются существующие `.site-header` и `.wrap`).

- [ ] **Шаг 1: Создать `journal.css`**

```css
/* ═══════════════════════════════════════════════════
   ЁPRST Journal — editorial layout styles
   Подключается только на страницах журнала.
   ═══════════════════════════════════════════════════ */

/* ─── JOURNAL WRAP (шире обычного wrap для редакционной сетки) ─── */
.jn-wrap {
  max-width: 1080px;
  margin: 0 auto;
  padding: 0 32px;
}

/* ─── HERO ─── */
.hero {
  display: grid;
  grid-template-columns: 56fr 44fr;
  border-bottom: 2px solid var(--ink);
  max-width: 1080px;
  margin: 0 auto;
}
.hero-img {
  position: relative;
  overflow: hidden;
  min-height: 540px;
}
.hero-img img,
.hero-img svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}
.hero-img::after {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 4px;
  background: var(--c-alyi);
  z-index: 2;
}
.hero-text {
  padding: 32px 36px 36px;
  display: flex;
  flex-direction: column;
  border-left: 2px solid var(--ink);
  position: relative;
  overflow: hidden;
  background: var(--paper);
}
.hero-kicker {
  font-family: var(--f-mono);
  font-size: 10px;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: var(--c-alyi);
  margin-bottom: 18px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.hero-kicker::before {
  content: '';
  display: block;
  width: 20px;
  height: 1.5px;
  background: var(--c-alyi);
  flex-shrink: 0;
}
.hero-h1 {
  font-family: var(--f-display);
  font-weight: 900;
  font-size: clamp(28px, 3vw, 48px);
  line-height: .91;
  letter-spacing: -.03em;
  color: var(--ink);
  margin: 0 0 20px;
  flex: 1;
}
.hero-h1 em {
  font-style: italic;
  color: var(--c-alyi);
}
.hero-lead {
  font-family: var(--f-text);
  font-size: 15px;
  line-height: 1.55;
  color: var(--ink-2, rgba(22,22,20,.65));
  margin: 0 0 24px;
}
.hero-cta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: var(--f-mono);
  font-size: 11px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--ink);
  text-decoration: none;
  border-bottom: 1.5px solid var(--ink);
  padding-bottom: 2px;
  width: fit-content;
  margin-bottom: auto;
}
.hero-stamp {
  font-family: var(--f-mono);
  font-size: 9px;
  letter-spacing: .06em;
  color: rgba(22,22,20,.3);
  text-transform: uppercase;
  margin-top: 28px;
}

/* ─── RUBRIC BAR ─── */
.rubric-bar {
  display: flex;
  align-items: stretch;
  border-bottom: 1px solid var(--ink);
  max-width: 1080px;
  margin: 0 auto;
  padding: 0 32px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
.rb-label {
  font-family: var(--f-mono);
  font-size: 10px;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: rgba(22,22,20,.3);
  padding: 14px 16px 14px 0;
  white-space: nowrap;
  display: flex;
  align-items: center;
  border-right: 1px solid var(--ink);
  margin-right: 4px;
}
.rubric-bar a {
  font-family: var(--f-mono);
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--ink-2, rgba(22,22,20,.6));
  text-decoration: none;
  padding: 14px 14px;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 4px;
  border-right: 1px solid rgba(22,22,20,.08);
}
.rubric-bar a sup {
  font-size: 9px;
  opacity: .45;
}
.rubric-bar a.on,
.rubric-bar a:hover {
  background: var(--ink);
  color: var(--paper);
}

/* ─── ARTICLES HEADER ─── */
.art-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  max-width: 1080px;
  margin: 0 auto;
  padding: 10px 32px 8px;
  border-bottom: 1px solid rgba(22,22,20,.12);
}
.art-header-label {
  font-family: var(--f-mono);
  font-size: 10px;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: rgba(22,22,20,.4);
}
.art-header-meta {
  font-family: var(--f-mono);
  font-size: 10px;
  letter-spacing: .04em;
  color: rgba(22,22,20,.3);
}

/* ─── EDITORIAL GRID (asymmetric 2-col) ─── */
.ed-grid {
  display: grid;
  grid-template-columns: 1.75fr 1fr;
  max-width: 1080px;
  margin: 0 auto;
  border-top: 2px solid var(--ink);
  border-bottom: 1px solid var(--ink);
}
.ed-lead {
  padding: 0;
  border-right: 1px solid var(--ink);
  display: flex;
  flex-direction: column;
}
.ed-lead-img {
  position: relative;
  overflow: hidden;
  flex: 1;
  min-height: 300px;
  background: #E8E4DC;
}
.ed-lead-img img,
.ed-lead-img svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.ed-lead-body {
  padding: 20px 24px 24px;
  border-top: 1px solid var(--ink);
}
.ed-sec-stack {
  display: flex;
  flex-direction: column;
}
.ed-sec {
  padding: 20px 22px;
  flex: 1;
}
.ed-sec + .ed-sec {
  border-top: 1px solid var(--ink);
}

/* ─── RUBRIC LABELS ─── */
.rub {
  font-family: var(--f-mono);
  font-size: 10px;
  letter-spacing: .1em;
  text-transform: uppercase;
  margin-bottom: 10px;
}
.rub-alyi    { color: var(--c-alyi); }
.rub-kobalt  { color: var(--c-kobalt); }
.rub-hvoya   { color: var(--c-hvoya); }
.rub-fuxia   { color: var(--c-fuxia); }
.rub-limon   { color: #b08a00; }  /* лимон — затемнён для читаемости на белом */
.rub-default { color: rgba(22,22,20,.45); }

/* ─── ARTICLE CARD TYPOGRAPHY ─── */
.ed-h2 {
  font-family: var(--f-display);
  font-weight: 700;
  font-size: clamp(18px, 2.2vw, 28px);
  line-height: .95;
  letter-spacing: -.025em;
  color: var(--ink);
  margin: 0 0 12px;
}
.ed-h2 em { font-style: italic; color: var(--c-alyi); }
.ed-h3 {
  font-family: var(--f-display);
  font-weight: 600;
  font-size: clamp(14px, 1.6vw, 19px);
  line-height: 1.0;
  letter-spacing: -.02em;
  color: var(--ink);
  margin: 0 0 10px;
}
.ed-h3 em { font-style: italic; color: var(--c-alyi); }
.ed-lead-text {
  font-family: var(--f-text);
  font-weight: 300;
  font-size: 14px;
  line-height: 1.5;
  color: rgba(22,22,20,.65);
  margin: 0 0 14px;
}
.ed-meta {
  font-family: var(--f-mono);
  font-size: 10px;
  letter-spacing: .04em;
  color: rgba(22,22,20,.35);
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.ed-read-link {
  font-family: var(--f-mono);
  font-size: 10px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--ink);
  text-decoration: none;
  border-bottom: 1px solid var(--ink);
  padding-bottom: 1px;
  display: inline-block;
  margin-top: 12px;
}

/* ─── HORIZONTAL FEATURE ─── */
.ed-feature {
  display: grid;
  grid-template-columns: 1fr 1fr;
  border-top: 2px solid var(--c-kobalt);
  max-width: 1080px;
  margin: 0 auto;
}
.ed-feat-left {
  padding: 28px 28px 32px;
  border-right: 1px solid var(--ink);
}
.ed-feat-right {
  padding: 28px 28px 32px;
}
.ed-feat-pull {
  font-family: var(--f-display);
  font-weight: 700;
  font-size: clamp(16px, 1.8vw, 22px);
  line-height: 1.1;
  letter-spacing: -.02em;
  color: var(--ink);
  border-left: 3px solid var(--c-alyi);
  padding-left: 18px;
  margin: 0 0 18px;
  font-style: italic;
}

/* ─── ЛЕНТА (blueprint strip) ─── */
.lenta-section {
  border-top: 2px solid var(--c-hvoya);
  border-bottom: 2px solid var(--ink);
  max-width: 1080px;
  margin: 0 auto;
  background: var(--paper);
}
.lenta-inner {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 0;
}
.lenta-label {
  padding: 26px 16px 26px 24px;
  border-right: 1px solid var(--ink);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  overflow: hidden;
  min-width: 0;
}
.lenta-label-title {
  font-family: var(--f-display);
  font-weight: 700;
  font-size: 28px;
  line-height: .94;
  letter-spacing: -.02em;
  color: var(--ink);
}
.lenta-label-title em { font-style: italic; color: var(--c-alyi); }
.lenta-label-sub {
  font-family: var(--f-mono);
  font-size: 9px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: rgba(22,22,20,.4);
  margin-top: 10px;
}
.lenta-label-tg {
  font-family: var(--f-mono);
  font-size: 10px;
  letter-spacing: .06em;
  color: var(--ink);
  text-decoration: none;
  border-bottom: 1px solid var(--ink);
  width: fit-content;
}
.lenta-list {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0;
}
.lc {
  padding: 20px 18px;
  border-right: 1px solid rgba(22,22,20,.08);
  display: flex;
  flex-direction: column;
}
.lc:last-child { border-right: none; }
.lc-meta {
  font-family: var(--f-mono);
  font-size: 10px;
  letter-spacing: .04em;
  margin-bottom: 12px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.lc-date { color: rgba(22,22,20,.4); }
.lc-tag  { color: var(--c-alyi); font-weight: 500; }
.lc-title {
  font-family: var(--f-text);
  font-weight: 300;
  font-size: 13px;
  line-height: 1.45;
  color: var(--ink);
  margin: 0 0 auto;
  letter-spacing: -.01em;
}
.lc-cta {
  font-family: var(--f-mono);
  font-size: 9px;
  letter-spacing: .05em;
  color: rgba(22,22,20,.4);
  text-transform: uppercase;
  margin-top: 14px;
  text-decoration: none;
}
.lc-cta:hover { color: var(--ink); }

/* ─── ВЫПУСКИ ─── */
.issues-section {
  background: #E4E0DA;
  max-width: 1080px;
  margin: 0 auto;
  padding: 36px 32px 52px;
}
.issues-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(22,22,20,.15);
  margin-bottom: 26px;
}
.issues-head h3 {
  font-family: var(--f-display);
  font-weight: 700;
  font-size: 26px;
  margin: 0;
  color: var(--ink);
  letter-spacing: -.01em;
}
.issues-head h3 em { font-style: italic; opacity: .5; }
.issues-head-link {
  font-family: var(--f-mono);
  font-size: 11px;
  letter-spacing: .05em;
  color: var(--ink);
  text-decoration: none;
  border-bottom: 1.5px solid var(--ink);
  padding-bottom: 1px;
  text-transform: uppercase;
}
.issues-head-link:hover { opacity: .5; }
.issues-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}
.issue-card .cover {
  aspect-ratio: 3/4;
  overflow: hidden;
  margin-bottom: 12px;
}
.issue-card .cover svg {
  width: 100%;
  height: 100%;
  display: block;
}
.issue-card .im {
  font-family: var(--f-mono);
  font-size: 10px;
  color: rgba(22,22,20,.4);
  letter-spacing: .05em;
  text-transform: uppercase;
  margin-bottom: 4px;
}
.issue-card h4 {
  font-family: var(--f-display);
  font-weight: 600;
  font-size: 15px;
  line-height: 1.2;
  color: var(--ink);
  margin: 0;
}

/* ─── RESPONSIVE ─── */
@media (max-width: 780px) {
  .hero { grid-template-columns: 1fr; }
  .hero-img { min-height: 280px; }
  .hero-text { border-left: none; border-top: 2px solid var(--ink); }
  .ed-grid { grid-template-columns: 1fr; }
  .ed-lead { border-right: none; border-bottom: 1px solid var(--ink); }
  .ed-feature { grid-template-columns: 1fr; }
  .ed-feat-left { border-right: none; border-bottom: 1px solid var(--ink); }
  .lenta-inner { grid-template-columns: 1fr; }
  .lenta-label { border-right: none; border-bottom: 1px solid var(--ink); padding: 20px 16px; }
  .lenta-list { grid-template-columns: 1fr 1fr; }
  .issues-grid { grid-template-columns: 1fr 1fr; }
  .jn-wrap { padding: 0 16px; }
}
@media (max-width: 480px) {
  .lenta-list { grid-template-columns: 1fr; }
  .issues-grid { grid-template-columns: 1fr; }
  .rubric-bar { padding: 0 16px; }
}
```

- [ ] **Шаг 2: Убедиться что файл существует**

```bash
ls -lh journal.css
```

- [ ] **Шаг 3: Commit**

```bash
git add journal.css
git commit -m "feat: add journal.css editorial layout styles"
```

---

## Task 5: Заменить `issue_cover_svg()`

**Files:**
- Modify: `build.py` (~строка 1055)

- [ ] **Шаг 1: Найти и заменить функцию `issue_cover_svg()`**

Найти блок:
```python
def issue_cover_svg(issue):
    """Автообложка выпуска: чистая «печатная» композиция в выбранном цвете."""
    c = PALETTE.get(issue.get("coverColor", "alyi"), "#FA2A22")
    ...
    return f'''<svg viewBox="0 0 400 530" ...
```

Заменить ВЕСЬ блок функции на:

```python
def issue_cover_svg(issue):
    """Обложка выпуска: цветной фон из палитры PRSTNK + типографика."""
    color_name = issue.get("coverColor", "alyi")
    bg = PALETTE.get(color_name, "#FA2A22")
    # Лимон — светлый фон, остальные тёмные → белый текст
    light = (color_name == "limon")
    fg      = "#161614"           if light else "#FCFCFB"
    fg_mid  = "rgba(22,22,20,.55)" if light else "rgba(252,252,251,.6)"
    fg_low  = "rgba(22,22,20,.35)" if light else "rgba(252,252,251,.45)"
    sep     = "rgba(22,22,20,.25)" if light else "rgba(255,255,255,.35)"
    ghost   = "rgba(22,22,20,.07)" if light else "rgba(255,255,255,.1)"
    num     = str(issue.get("number", "")).zfill(2)
    period  = (issue.get("period", "") or "").upper()
    # Разбиваем title на 2 строки по первому пробелу (SVG не переносит сам)
    raw_title = esc(strip_tags(issue.get("title", "")))
    parts = raw_title.split(None, 1)
    line1 = parts[0] if parts else ""
    line2 = parts[1] if len(parts) > 1 else ""
    # Вторая строка: обрезаем если длинная
    if len(line2) > 18:
        line2 = line2[:16] + "…"
    sub = esc(strip_tags(issue.get("subtitle") or issue.get("period", "")))
    y2 = "282" if line2 else "248"  # одна строка — ниже по центру
    line2_el = (f'\n  <text x="20" y="282" style="font-family:var(--f-display);font-weight:700;"'
                f' fill="{fg}" font-size="26" letter-spacing="-1">{line2}</text>') if line2 else ""
    return (f'<svg viewBox="0 0 300 400" xmlns="http://www.w3.org/2000/svg">'
            f'<rect width="300" height="400" fill="{bg}"/>'
            f'<text x="-12" y="385" style="font-family:var(--f-display);font-weight:900;"'
            f' fill="{ghost}" font-size="240" letter-spacing="-14">{num}</text>'
            f'<text x="20" y="34" style="font-family:var(--f-display);font-weight:700;"'
            f' fill="{fg}" font-size="10" letter-spacing="5">ЁPRST</text>'
            f'<rect x="20" y="40" width="260" height="1" fill="{sep}"/>'
            f'<text x="20" y="56" style="font-family:var(--f-mono);"'
            f' fill="{fg_mid}" font-size="8" letter-spacing="2">№ {num} · {period}</text>'
            f'<text x="20" y="{y2}" style="font-family:var(--f-display);font-weight:700;"'
            f' fill="{fg}" font-size="26" letter-spacing="-1">{line1}</text>'
            f'{line2_el}'
            f'<rect x="20" y="296" width="260" height="1" fill="{sep}"/>'
            f'<text x="20" y="312" style="font-family:var(--f-mono);"'
            f' fill="{fg_mid}" font-size="9" letter-spacing="1">{sub}</text>'
            f'<rect x="20" y="358" width="260" height="1" fill="{sep}"/>'
            f'<text x="20" y="372" style="font-family:var(--f-mono);"'
            f' fill="{fg_low}" font-size="7" letter-spacing="1">'
            f'PRSTNK · ПЕЧАТНАЯ ГРАФИКА СПБ</text>'
            f'</svg>')
```

- [ ] **Шаг 2: Запустить тесты на покрытие**

```bash
python3 -m pytest tests/test_journal.py::TestIssueCoverSvg -v
```

Ожидаемый результат: все 7 тестов **PASS**.

- [ ] **Шаг 3: Убедиться что build работает**

```bash
python3 build.py 2>&1 | grep -E "(✓|Error|Traceback)"
```

- [ ] **Шаг 4: Commit**

```bash
git add build.py
git commit -m "feat: redesign issue_cover_svg() with brand color system"
```

---

## Task 6: Переписать `render_journal_index()` — герой и рубричная панель

**Files:**
- Modify: `build.py` (~строка 1243)

Функция переписывается целиком. В этом шаге — первая половина (герой + рубричная навигация).

- [ ] **Шаг 1: Добавить вспомогательные функции перед `render_journal_index()`**

Вставить после `def render_journal_index():` (или перед ней) новые хелперы:

```python
# ─── Вспомогательные хелперы для нового journal index ───

def _jrn_rub_class(kicker: str) -> str:
    """Возвращает CSS-класс цвета рубрики по тексту кикера."""
    k = (kicker or "").lower()
    if "куратор" in k or "подбор" in k: return "rub-alyi"
    if "интервью" in k or "разговор" in k: return "rub-kobalt"
    if "история" in k or "техник" in k: return "rub-hvoya"
    if "репортаж" in k or "лента" in k: return "rub-fuxia"
    return "rub-default"


def _jrn_article_img(art: dict) -> str:
    """Изображение статьи: загруженное фото или SVG-плейсхолдер."""
    img = (art.get("image") or "").strip()
    if img:
        from urllib.parse import quote as _q
        return (f'<img src="{_q(img.lstrip("/"), safe="/")}" '
                f'alt="{esc(strip_tags(art.get("title", "")))}" '
                f'loading="lazy" style="width:100%;height:100%;object-fit:cover;display:block;"/>')
    # SVG-заглушка в тоне рубрики
    rc = art.get("rubricColor", "#FA2A22")
    return (f'<svg viewBox="0 0 800 540" xmlns="http://www.w3.org/2000/svg" '
            f'style="width:100%;height:100%;display:block;" aria-hidden="true">'
            f'<rect width="800" height="540" fill="#1a1614"/>'
            f'<rect x="100" y="80" width="420" height="380" fill="{rc}" opacity=".18"/>'
            f'<circle cx="400" cy="270" r="90" fill="{rc}" opacity=".3"/>'
            f'</svg>')
```

- [ ] **Шаг 2: Заменить `render_journal_index()` — начало функции (герой + рубрика)**

Найти `def render_journal_index():` и заменить ВСЮ функцию целиком на приведённую ниже. (Реализация разбита на шаги для ясности, но вставляется как один блок.)

```python
def render_journal_index():
    canonical = f"{BASE_URL}/journal.html"
    title = "Журнал «ЁPRST» — PRSTNK"
    desc = ("Журнал PRSTNK про авторскую графику: разговоры с художниками, "
            "техники, коллекции, репортажи из мастерских. Выходит ежемесячно.")

    # ── данные ─────────────────────────────────────────────────────────────
    current = next((i for i in issues if i.get("current")), issues[0] if issues else {})
    arts = current.get("articles", [])
    hero_art     = arts[0] if arts else {}
    other_arts   = arts[1:]
    lead_art     = other_arts[0] if other_arts else {}
    sec_arts     = other_arts[1:3]
    feature_art  = other_arts[3] if len(other_arts) > 3 else (other_arts[-1] if other_arts else {})
    lenta_items  = materials[:4]
    recent_iss   = issues[:3]

    issue_slug   = iss_slug(current)
    issue_url    = f"zine-{issue_slug}.html" if issue_has_page(current) else ""

    # ── HERO ───────────────────────────────────────────────────────────────
    h_kicker  = hero_art.get("kicker", "Статья выпуска")
    h_title   = hero_art.get("title", current.get("title", ""))
    h_lead    = hero_art.get("lead", current.get("lead", ""))
    h_img     = _jrn_article_img({**hero_art,
                                   "rubricColor": PALETTE.get(current.get("coverColor","alyi"),"#FA2A22")})
    h_cta     = f'<a class="hero-cta" href="{issue_url}#article-1">Читать →</a>' if issue_url else ""
    h_stamp   = f'ЁPRST · Выпуск № {current.get("number","")} · {current.get("period","")} · Магазин PRSTNK'

    hero_html = f'''<div class="hero">
  <div class="hero-img">{h_img}</div>
  <div class="hero-text">
    <div class="hero-kicker">{h_kicker}</div>
    <h1 class="hero-h1">{h_title}</h1>
    <p class="hero-lead">{h_lead}</p>
    {h_cta}
    <div class="hero-stamp">{h_stamp}</div>
  </div>
</div>'''

    # ── RUBRIC BAR ─────────────────────────────────────────────────────────
    # Считаем кол-во статей по рубрикам (все выпуски)
    all_arts = [a for iss in issues for a in iss.get("articles", [])]
    rub_counts: dict[str, int] = {}
    for a in all_arts:
        k = (a.get("kicker") or "").split("·")[0].strip()
        rub_counts[k] = rub_counts.get(k, 0) + 1
    total_count = sum(rub_counts.values())

    rub_links = [f'<a href="journal.html" class="on">Всё <sup>{total_count}</sup></a>']
    shown_rubs = [("Кураторская", "kuraторская"), ("Интервью", "intervyu"),
                  ("История", "istoriya"), ("Техники", "tekhniki"), ("Репортаж", "reportazh")]
    for label, slug_r in shown_rubs:
        cnt = sum(v for k, v in rub_counts.items() if label.lower() in k.lower())
        if cnt:
            rub_links.append(f'<a href="journal/{slug_r}"><sup class="rub-count">{cnt}</sup>{label}</a>')

    rubric_html = f'''<nav class="rubric-bar" aria-label="Рубрики журнала">
  <span class="rb-label">Рубрики</span>
  {"".join(rub_links)}
</nav>'''

    # ── ART HEADER ─────────────────────────────────────────────────────────
    art_header_html = f'''<div class="art-header">
  <div class="art-header-label">— <b>Свежие материалы</b></div>
  <div class="art-header-meta">Выпуск № {current.get("number","")} · {current.get("period","")}</div>
</div>'''

    # ── EDITORIAL GRID ─────────────────────────────────────────────────────
    def _art_meta(a):
        parts = []
        if a.get("readMins"): parts.append(f'{a["readMins"]} мин')
        if a.get("date"):     parts.append(fmt_date_ru(a["date"]))
        return " · ".join(parts)

    lead_rub_cls = _jrn_rub_class(lead_art.get("kicker",""))
    lead_img     = _jrn_article_img({**lead_art, "rubricColor": PALETTE.get("kobalt")}) if lead_art else ""
    lead_url     = f"{issue_url}#article-2" if issue_url and lead_art else ""

    lead_html = ""
    if lead_art:
        lead_html = f'''<article class="ed-lead">
  <div class="ed-lead-img">{lead_img}</div>
  <div class="ed-lead-body">
    <div class="rub {lead_rub_cls}">{lead_art.get("kicker","")}</div>
    <h2 class="ed-h2">{lead_art.get("title","")}</h2>
    <p class="ed-lead-text">{lead_art.get("lead","")}</p>
    <div class="ed-meta">{_art_meta(lead_art)}</div>
    {f'<a class="ed-read-link" href="{lead_url}">Читать →</a>' if lead_url else ""}
  </div>
</article>'''

    sec_html = ""
    for idx_s, sa in enumerate(sec_arts, start=3):
        sec_rub_cls = _jrn_rub_class(sa.get("kicker",""))
        sec_url = f"{issue_url}#article-{idx_s}" if issue_url else ""
        sec_html += f'''<article class="ed-sec">
  <div class="rub {sec_rub_cls}">{sa.get("kicker","")}</div>
  <h3 class="ed-h3">{sa.get("title","")}</h3>
  <div class="ed-meta">{_art_meta(sa)}</div>
  {f'<a class="ed-read-link" href="{sec_url}">Читать →</a>' if sec_url else ""}
</article>'''

    grid_html = ""
    if lead_art or sec_html:
        grid_html = f'''<div class="ed-grid">
  {lead_html}
  <div class="ed-sec-stack">{sec_html}</div>
</div>'''

    # ── HORIZONTAL FEATURE ─────────────────────────────────────────────────
    feature_html = ""
    if feature_art:
        feat_rub_cls = _jrn_rub_class(feature_art.get("kicker",""))
        feat_url  = f"{issue_url}#article-{len(other_arts)}" if issue_url else ""
        pq = feature_art.get("pullquote") or {}
        pull_html = (f'<p class="ed-feat-pull">{pq["text"]}</p>' if pq.get("text") else "")
        feat_desc = feature_art.get("lead","")
        creds = current.get("credits", [])
        author = next((c["name"] for c in creds if c.get("role") in ("Гости","Автор")), "")
        feature_html = f'''<div class="ed-feature">
  <div class="ed-feat-left">
    <div class="rub {feat_rub_cls}">{feature_art.get("kicker","")}</div>
    <h2 class="ed-h2">{feature_art.get("title","")}</h2>
    <p class="ed-lead-text">{feat_desc}</p>
    <div class="ed-meta">{_art_meta(feature_art)}</div>
    {f'<a class="ed-read-link" href="{feat_url}">Читать →</a>' if feat_url else ""}
  </div>
  <div class="ed-feat-right">
    {pull_html}
    {f'<p class="ed-lead-text">{esc(author)}</p>' if author else ""}
  </div>
</div>'''

    # ── ЛЕНТА ──────────────────────────────────────────────────────────────
    lc_html = ""
    for m in lenta_items:
        date_s = fmt_date_ru(m.get("date",""))
        tag_s  = m.get("tag","")
        url_m  = (m.get("url") or "").strip()
        if not url_m and m.get("tgText"):
            url_m = f'https://t.me/prstnk_store'
        href = f'href="{esc(url_m)}" target="_blank" rel="noopener"' if url_m else "data-tg-open"
        lc_html += f'''<a class="lc" {href} data-analytics="lenta-card">
  <div class="lc-meta">
    <span class="lc-date">{date_s}</span>
    <span class="lc-tag">{esc(tag_s)}</span>
  </div>
  <div class="lc-title">{esc(m.get("title",""))}</div>
  <span class="lc-cta">Читать в Telegram →</span>
</a>'''

    lenta_html = f'''<div class="lenta-section">
  <div class="lenta-inner">
    <div class="lenta-label">
      <div>
        <div class="lenta-label-title">Лента.<br/><em>Каждый<br/>день.</em></div>
        <div class="lenta-label-sub">из Telegram · между выпусками</div>
      </div>
      <a class="lenta-label-tg" href="https://t.me/prstnk_store" target="_blank" rel="noopener">@prstnk_store →</a>
    </div>
    <div class="lenta-list">{lc_html}</div>
  </div>
</div>'''

    # ── ВЫПУСКИ ────────────────────────────────────────────────────────────
    issue_cards = ""
    for iss in recent_iss:
        slug_i = iss_slug(iss)
        href_i = f'href="zine-{slug_i}.html"' if issue_has_page(iss) else "data-tg-open"
        n_i    = iss.get("number","")
        p_i    = iss.get("period","")
        mc_i   = iss.get("materialsCount") or len(iss.get("articles",[]))
        im_i   = f'№ {n_i} · {p_i} · {mc_i} {_plural(mc_i,"материал","материала","материалов")}' if mc_i else f'№ {n_i} · {p_i}'
        issue_cards += f'''<a class="issue-card" {href_i} data-analytics="issues-card" data-issue="{n_i}">
  <div class="cover">{issue_cover_svg(iss)}</div>
  <div class="im">{im_i}</div>
  <h4>{strip_tags(iss.get("title",""))}</h4>
</a>'''

    issues_html = f'''<div class="issues-section">
  <div class="issues-head">
    <h3>Выпуски <em>месяца</em>.</h3>
    <a class="issues-head-link" href="issues.html">Все выпуски →</a>
  </div>
  <div class="issues-grid">{issue_cards}</div>
</div>'''

    # ── СБОРКА ────────────────────────────────────────────────────────────
    return f'''{head(title, desc, canonical, extra_css="journal.css")}{HEADER}
<div class="jn-wrap" style="padding:0;">
{hero_html}
{rubric_html}
{art_header_html}
{grid_html}
{feature_html}
{lenta_html}
{issues_html}
</div>
{FOOTER}'''
```

- [ ] **Шаг 3: Запустить тесты**

```bash
python3 -m pytest tests/test_journal.py -v
```

Ожидаемый результат: все тесты **PASS**.

- [ ] **Шаг 4: Запустить сборку, проверить `journal.html`**

```bash
python3 build.py 2>&1 | grep -E "(journal|Error|Traceback)"
grep -c "class=\"hero\"" journal.html
grep -c "class=\"issues-section\"" journal.html
```

Ожидаемый вывод:
```
  ✓ journal.html — журнал (...)
1
1
```

- [ ] **Шаг 5: Commit**

```bash
git add build.py
git commit -m "feat: redesign render_journal_index() with editorial layout"
```

---

## Task 7: Финальная проверка и удаление макета

**Files:**
- Delete: `_journal-mockup.html`

- [ ] **Шаг 1: Полная сборка, убедиться что нет ошибок**

```bash
python3 build.py
```

Ожидаемый результат: завершается без `Error`/`Traceback`.

- [ ] **Шаг 2: Проверить journal.html в браузере**

```bash
python3 -m http.server 8899 --directory /Users/artemgrinberg/prstnk-site &
open http://localhost:8899/journal
```

Проверить визуально: герой есть, рубричная панель есть, редакционная сетка есть, лента есть, выпуски с цветными обложками есть.

- [ ] **Шаг 3: Запустить полный тест-сьют**

```bash
python3 -m pytest tests/ -v
```

Все тесты PASS.

- [ ] **Шаг 4: Удалить макет**

```bash
rm /Users/artemgrinberg/prstnk-site/_journal-mockup.html
```

- [ ] **Шаг 5: Финальный коммит**

```bash
git add -u
git add journal.css tests/
git commit -m "feat: ЁPRST journal redesign — editorial layout, color covers, lenta

- New editorial grid: hero + asymmetric 2-col + horizontal feature
- issue_cover_svg() now uses brand color system (alyi/kobalt/fuxia/hvoya)
- journal.css extracted for journal-only styles
- render_journal_index() fully rewritten
- Mockup file removed"
```

- [ ] **Шаг 6: Push**

```bash
git fetch && git rebase origin/main && git push
```

---

## Self-review notes

- ✅ Все секции из спека покрыты: герой, рубричная панель, редакционная сетка, горизонтальный фичер, лента, выпуски
- ✅ Система цветов обложек: alyi/kobalt/fuxia/hvoya — через `coverColor` в JSON
- ✅ `journal.css` подключается только на журнальных страницах через `extra_css=`
- ✅ Graceful degradation: если в выпуске 0-3 статей, секции отсутствующих статей просто не рендерятся
- ✅ Мобильная адаптация — в journal.css брейкпоинты 780px и 480px
- ⚠️ Страницы `/issues` (архив всех выпусков) и `/journal/<slug>` (отдельная статья) — не в этом плане. Это следующая итерация после того как главная страница журнала принята.
