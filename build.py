#!/usr/bin/env python3
"""
PRSTNK — генератор статических страниц из data/*.json.

Запуск из корня проекта:
    python3 build.py

Что делает:
  • читает data/artworks.json, data/artists.json, data/collections.json
  • генерит work-<slug>.html для каждой работы (SEO + OG + блок тиража/уникальности + CTA)
  • перегенерирует works.html (каталог с бейджами статуса и фильтром по технике)
  • обновляет sitemap.xml (главная, каталог, художники, журнал, выпуск, все работы)

После правки данных запусти `python3 build.py` ещё раз — страницы пересоберутся.
(На GitHub эту команду можно повесить на Action, чтобы пересборка шла автоматически.)
"""

import json
import os
import re
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).parent
BASE_URL = "https://prstnk.ru"

# ─── Чистые адреса без .html ───
# Файлы на диске остаются <name>.html, но во всех ссылках/канонических/OG
# расширение убирается: GitHub Pages сам отдаёт /journal как journal.html.
# Главная (index.html) превращается в «/».
_LINK_RE = re.compile(
    r'(href|content)="((?:https://prstnk\.ru)?/?[A-Za-z0-9._\-]+)\.html((?:#|\?)[^"]*)?"'
)

def _link_repl(m):
    attr, base, suffix = m.group(1), m.group(2), m.group(3) or ""
    if base == "index":
        base = "/"                 # относительная ссылка на главную
    elif base.endswith("/index"):
        base = base[:-5]           # https://prstnk.ru/index → https://prstnk.ru/
    return f'{attr}="{base}{suffix}"'

def clean_links(html):
    """Убирает .html из всех внутренних href/content. Идемпотентна."""
    return _LINK_RE.sub(_link_repl, html)


def load_collection(name):
    """Читает все JSON из data/<name>/ и сортирует по полю order."""
    folder = ROOT / "data" / name
    if not folder.exists():
        return []
    items = [json.loads(p.read_text()) for p in folder.glob("*.json")]
    return sorted(items, key=lambda x: x.get("order", 0))

# hidden: true — запись остаётся в базе (и в админке), но на сайт не попадает
artworks = [w for w in load_collection("artworks") if not w.get("hidden")]
artists = [a for a in load_collection("artists") if not a.get("hidden")]
collections = load_collection("collections")
issues = [x for x in load_collection("issues") if not x.get("hidden")]        # выпуски журнала «ЁPRST»
materials = [x for x in load_collection("materials") if not x.get("hidden")]  # лента коротких постов
# draft: true — черновик статьи: на сайт не попадает; локально виден при PRSTNK_DRAFTS=1
articles = [x for x in load_collection("articles")
            if not x.get("hidden") and (not x.get("draft") or os.environ.get("PRSTNK_DRAFTS"))]    # материалы журнала (track A)


def load_lenta():
    """Лента: свои посты сайта (data/materials, правятся в админке), новые первыми.
    Если своих постов нет — посты Telegram-канала (data/lenta_channel.json)."""
    own = sorted(materials, key=lambda m: str(m.get("date", "")), reverse=True)
    if own:
        return own
    p = ROOT / "data" / "lenta_channel.json"
    if p.exists():
        try:
            items = json.loads(p.read_text())
            if items:
                return items
        except Exception:
            pass
    return materials

lenta = load_lenta()


def _slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s or "zapis"


def enrich_artist(a):
    """Безопасные значения по умолчанию — чтобы неполная запись из админки
    (например, без скрытого id) не роняла сборку всего сайта."""
    if not a.get("slug"):
        a["slug"] = _slugify(a.get("name", ""))
    if not a.get("id"):
        a["id"] = a["slug"]
    a.setdefault("name", "Без имени")
    a.setdefault("nameShort", a.get("name", ""))
    _parts = (a.get("name", "") or "").split()
    a.setdefault("firstName", _parts[0] if _parts else "автора")
    a.setdefault("gen", a.get("name", ""))
    a.setdefault("oneLiner", "")
    a.setdefault("city", "Санкт-Петербург")
    a.setdefault("techniques", [])
    a.setdefault("bio", [])
    a.setdefault("collections", [])
    a.setdefault("meta", [])
    a.setdefault("featured", False)
    a.setdefault("order", 99)


for _a in artists:
    enrich_artist(_a)

artists_by_id = {a["id"]: a for a in artists}

# Если у художника из админки не было id, админка кладёт в работу его имя
# вместо id («Гарт Штапаков»). Приводим такие ссылки к настоящему id.
_artists_by_name = {a["name"]: a for a in artists}
for _w in artworks:
    if _w.get("artistId") not in artists_by_id and _w.get("artistId") in _artists_by_name:
        _w["artistId"] = _artists_by_name[_w["artistId"]]["id"]


def _fmt_price(n):
    try:
        return f"{int(n):,}".replace(",", " ") + " ₽"
    except (ValueError, TypeError):
        return ""


def fmt_size(s):
    """Разделитель размеров → красивый знак умножения: 46x60 / 46х60 / 46*60 → 46 × 60."""
    if not s:
        return s or ""
    return re.sub(r"(\d)\s*[xXхХ*×]\s*(\d)", r"\1 × \2", s.strip())


def ed_label(art):
    """«14/30», если номер и тираж заполнены; иначе то, что известно."""
    if art.get("workType") == "unique":
        return "1/1"
    n, t = art.get("editionNumber"), art.get("editionTotal")
    if n and t:
        return f"{n}/{t}"
    return f"тираж {t}" if t else "тираж"


def enrich_artwork(w):
    """Автозаполнение служебных полей, чтобы в админке их можно было не показывать.
    Смысловые поля (название, цена, год…) задаёт человек; всё техническое —
    SEO, текст брони, alt, цена прописью, реквизиты — генерится здесь при сборке."""
    # Админка сохраняет незаполненные поля как null — считаем их просто пустыми
    for _k in [k for k, v in w.items() if v is None]:
        del w[_k]
    if not w.get("slug"):
        w["slug"] = _slugify(w.get("title", ""))
    a = artists_by_id.get(w.get("artistId"))
    aname = a["name"] if a else w.get("artistName", "")
    if a:
        w["artistName"] = a["name"]
        w["artistSlug"] = a["slug"]

    # id = slug
    if not w.get("id"):
        w["id"] = w.get("slug", "")

    # Размеры: разделитель «x/х/*» → красивый «×» (везде: карточка, страница, рама, SEO)
    w["sheetSize"] = fmt_size(w.get("sheetSize", ""))
    w["imageSize"] = fmt_size(w.get("imageSize", ""))

    # Дефолты-реквизиты (партнёр может переопределить через JSON, но в форме не нужны)
    w.setdefault("imageSize", "")
    w.setdefault("galleryImages", [])
    w.setdefault("collections", [])
    w.setdefault("featuredInCatalog", True)
    w.setdefault("featuredOnHome", False)
    w.setdefault("order", 99)
    if not w.get("dominantColor"):
        w["dominantColor"] = "#FA2A22"
    # paper/signature/condition/certificate больше не получают авто-дефолтов:
    # пустое поле не показывается на странице (управляется из админки).

    # Тип-зависимое
    if w.get("workType") == "unique":
        w["availableCount"] = 1
    else:
        w["workType"] = "editioned"
        w.setdefault("artistProofs", 0)
        w.setdefault("editionClosed", False)
        if not w.get("availableCount") and w.get("editionTotal") and w.get("editionNumber"):
            w["availableCount"] = max(1, int(w["editionTotal"]) - int(w["editionNumber"]))

    # Всегда пересчитываем (зависят от смысловых полей) — чтобы были актуальны
    w["priceFormatted"] = _fmt_price(w.get("price"))
    w["alt"] = f"{w.get('technique','')}, {w.get('title','')}, {aname}"
    ed = ed_label(w)
    if w.get("workType") == "unique":
        w["telegramReserveText"] = (f"Хочу забронировать уникальную работу «{w.get('title','')}» — "
                                    f"{aname}, {w.get('year','')}. Цена {w['priceFormatted']}.")
    else:
        w["telegramReserveText"] = (f"Хочу забронировать экземпляр {'№' + ed if '/' in ed else ''} работы «{w.get('title','')}» — "
                                    f"{aname}, {w.get('year','')}. Цена {w['priceFormatted']}.")
    w["seoTitle"] = f"{aname}. «{w.get('title','')}», {w.get('year','')} — {w.get('technique','')} {ed} — PRSTNK"
    w["seoDescription"] = (f"«{w.get('title','')}» — {w.get('technique','')}, {aname}, {w.get('year','')}, "
                           f"{w.get('sheetSize','')}. Оригинал, подпись автора. {w['priceFormatted']}.")


for _w in artworks:
    enrich_artwork(_w)

artworks_by_slug = {w["slug"]: w for w in artworks if w.get("slug")}

# Художники: id = slug если пусто, пересчёт привязки работ
for _a in artists:
    if not _a.get("id"):
        _a["id"] = _a.get("slug", "")
    _a["workSlugs"] = [w["slug"] for w in artworks if w.get("artistId") == _a["id"]]
    _a["worksCount"] = len(_a["workSlugs"])

# ─── Извлекаем SVG-плейсхолдеры из текущего works.html по slug ───
svg_map = {}
old_works = (ROOT / "works.html").read_text()
for block in re.findall(r'<a class="work".*?</a>', old_works, re.DOTALL):
    m_slug = re.search(r'data-work-slug="([^"]+)"', block)
    m_svg = re.search(r'(<svg viewBox="0 0 100 133".*?</svg>)', block, re.DOTALL)
    if m_slug and m_svg:
        svg_map[m_slug.group(1)] = m_svg.group(1)

# Две уникальные монотипии Агальцова — рисуем вручную (риzо-минимализм)
svg_map["pustaya-komnata"] = '''<svg viewBox="0 0 100 133" preserveAspectRatio="none" width="100%" height="100%" aria-hidden="true">
                <rect width="100" height="133" fill="#E4E2DA"/>
                <rect y="96" width="100" height="37" fill="#9B9587"/>
                <rect x="18" y="30" width="40" height="50" fill="none" stroke="#6E6B61" stroke-width="2"/>
                <rect x="62" y="48" width="22" height="48" fill="#6E6B61" opacity="0.5"/>
                <rect x="30" y="84" width="20" height="12" fill="#38362F" opacity="0.6"/>
              </svg>'''
svg_map["okno-s-dozhdyom"] = '''<svg viewBox="0 0 100 133" preserveAspectRatio="none" width="100%" height="100%" aria-hidden="true">
                <rect width="100" height="133" fill="#C9C5B6"/>
                <rect x="20" y="20" width="60" height="80" fill="#2A4BFF" opacity="0.55"/>
                <rect x="49" y="20" width="2" height="80" fill="#C9C5B6"/>
                <rect x="20" y="58" width="60" height="2" fill="#C9C5B6"/>
                <line x1="30" y1="26" x2="26" y2="44" stroke="#F8F6F1" stroke-width="1.5"/>
                <line x1="44" y1="30" x2="40" y2="52" stroke="#F8F6F1" stroke-width="1.5"/>
                <line x1="60" y1="26" x2="56" y2="48" stroke="#F8F6F1" stroke-width="1.5"/>
                <line x1="72" y1="32" x2="68" y2="54" stroke="#F8F6F1" stroke-width="1.5"/>
              </svg>'''


def esc(s):
    return (s or "").replace("&", "&amp;").replace('"', "&quot;")


# ─── Общие куски ───
def head(title, description, canonical, og_type="website", extra_meta="", og_image=None, extra_css="", base_href=""):
    img = og_image or f"{BASE_URL}/og-cover.svg"
    base_tag = f'<base href="{base_href}"/>\n  ' if base_href else ""
    return f'''<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8"/>
  {base_tag}<meta name="viewport" content="width=device-width,initial-scale=1"/>
  <meta name="theme-color" content="#F8F6F1"/>
  <title>{title}</title>
  <meta name="description" content="{esc(description)}"/>

  <link rel="canonical" href="{canonical}"/>
  <meta property="og:type" content="{og_type}"/>
  <meta property="og:site_name" content="PRSTNK"/>
  <meta property="og:title" content="{esc(title)}"/>
  <meta property="og:description" content="{esc(description)}"/>
  <meta property="og:url" content="{canonical}"/>
  <meta property="og:image" content="{img}"/>
  <meta property="og:locale" content="ru_RU"/>
{extra_meta}  <meta name="twitter:card" content="summary_large_image"/>
  <meta name="twitter:title" content="{esc(title)}"/>
  <meta name="twitter:description" content="{esc(description)}"/>
  <meta name="twitter:image" content="{img}"/>

  <link rel="icon" type="image/svg+xml" href="favicon.svg"/>
  <link rel="stylesheet" href="fonts.css"/>
  <link rel="stylesheet" href="prstnk.css"/>
  {f'<link rel="stylesheet" href="{extra_css}"/>' if extra_css else ""}
  <script src="gate.js"></script>
</head>
<body>
'''


HEADER = '''  <header class="site-header">
    <div class="wrap site-header__inner">
      <a class="brand" href="index.html" aria-label="PRSTNK — главная">
        <svg class="brand__mark" viewBox="0 0 60 80" aria-hidden="true">
          <rect class="window" x="2" y="2" width="9" height="76"/>
          <rect class="pillar" x="13" y="0" width="34" height="80"/>
          <rect class="window" x="49" y="2" width="9" height="76"/>
        </svg>
        <span class="brand__word">PRSTNK</span>
        <span class="brand__desc">[ простенок ]</span>
      </a>
      <nav class="nav" id="nav" aria-label="Главное меню">
        <a href="works.html">Каталог</a>
        <a href="index.html#fit">Подбор</a>
        <a href="artists.html">Художники</a>
        <a href="journal.html">Журнал</a>
      </nav>
      <div class="header-tools">
        <button class="search" aria-label="Поиск" title="Поиск">⌕</button>
        <a class="cart" data-tg-open data-analytics="contact-header-tg" aria-label="Написать в Telegram">
          <span>Написать</span><b>· tg</b>
        </a>
        <button class="menu-toggle" aria-label="Меню" aria-expanded="false" aria-controls="nav">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <line x1="4" y1="8" x2="20" y2="8"/><line x1="4" y1="16" x2="20" y2="16"/>
          </svg>
        </button>
      </div>
    </div>
  </header>
'''

FOOTER = '''  <footer class="site-footer">
    <div class="wrap">
      <div class="footer-top">
        <div class="footer-statement">Большое искусство<br/>на <em>маленькой</em><br/>стене.</div>
        <div class="footer-top__right">
          <a class="brand on-dark" href="index.html" aria-label="PRSTNK">
            <svg class="brand__mark" viewBox="0 0 60 80" aria-hidden="true">
              <rect class="window" x="2" y="2" width="9" height="76"/>
              <rect class="pillar" x="13" y="0" width="34" height="80"/>
              <rect class="window" x="49" y="2" width="9" height="76"/>
            </svg>
            <span class="brand__word">PRSTNK</span>
          </a>
        </div>
      </div>
      <div class="footer-grid">
        <div>
          <h4>Гарантия</h4>
          <p style="font-family: var(--f-text); font-size: 15px; color: var(--on-dark-2); line-height: 1.5; max-width: 44ch;">
            Только оригиналы, никаких репродукций. Каждую работу подписывает автор, а оттиски из тиража ещё и нумерует. Если что-то не так — забираем обратно в течение 14 дней.
          </p>
        </div>
        <div>
          <h4>Магазин</h4>
          <ul>
            <li><a href="works.html">Каталог</a></li>
            <li><a href="index.html#fit">Подбор на стену</a></li>
            <li><a href="artists.html">Художники</a></li>
            <li><a href="index.html#plates">Готовые подборки</a></li>
          </ul>
        </div>
        <div>
          <h4>О нас</h4>
          <ul>
            <li><a data-tg-text="Здравствуйте! Расскажите про PRSTNK." data-analytics="footer-about">О проекте</a></li>
            <li><a href="index.html#how">Как купить</a></li>
            <li><a href="journal.html">Журнал «ЁPRST»</a></li>
            <li><a href="index.html#faq">FAQ</a></li>
            <li><a data-tg-text="Здравствуйте! Хочу обсудить сотрудничество с PRSTNK." data-analytics="footer-partnership">Сотрудничество</a></li>
          </ul>
        </div>
        <div>
          <h4>Связь</h4>
          <ul>
            <li><a data-tg-open data-analytics="footer-tg">Написать в Telegram</a></li>
          </ul>
        </div>
      </div>
      <div class="footer-bottom">
        <span>© 2026 PRSTNK · сделано в Санкт-Петербурге</span>
        <span class="domain">prstnk.ru</span>
        <span class="footer-social">
          <a data-tg-open data-analytics="social-tg">Telegram</a>
          <span class="footer-social__sep">·</span>
          <a href="https://instagram.com/prstnk_store" target="_blank" rel="noopener" data-analytics="social-ig">Instagram</a>
          <span class="footer-social__sep">·</span>
          <a href="https://vk.com/prstnk_store" target="_blank" rel="noopener" data-analytics="social-vk">VK</a>
        </span>
      </div>
    </div>
  </footer>

  <script src="prstnk.js" defer></script>
</body>
</html>
'''


ARROW = ('<svg width="18" height="14" viewBox="0 0 18 14" fill="none" aria-hidden="true">'
         '<path d="M1 7H17M17 7L11 1M17 7L11 13" stroke="currentColor" stroke-width="2"/></svg>')


def plate_visual(art):
    """Визуал работы: реальное фото (если загружено) или SVG-заглушка.
    Путь нормализуется: ведущий «/» убирается (относительный путь работает
    и на github.io/prstnk/, и на prstnk.ru), пробелы и спецсимволы экранируются.
    Для горизонтальных файлов (art.orientation == 'horizontal') — object-fit: contain,
    чтобы изображение не обрезалось."""
    img = (art.get("mainImage") or "").strip()
    if img:
        from urllib.parse import quote
        img = quote(img.lstrip("/"), safe="/")  # «/images/works/a b.jpg» → «images/works/a%20b.jpg»
        alt = esc(art.get("alt") or art.get("title", ""))
        fit = "contain" if art.get("orientation") == "horizontal" else "cover"
        return (f'<img src="{img}" alt="{alt}" loading="lazy" '
                f'style="width:100%;height:100%;object-fit:{fit};display:block;"/>')
    return svg_map.get(art["slug"], "")


def edition_dots(art):
    """Точки тиража: проданные (sold) + текущий (current) + доступные."""
    total = art.get("editionTotal")
    num = art.get("editionNumber")
    if not total or not num:
        return ""
    dots = []
    for i in range(1, total + 1):
        if i < num:
            dots.append('<i class="sold"></i>')
        elif i == num:
            dots.append('<i class="current"></i>')
        else:
            dots.append("<i></i>")
    return ('<div class="lot__edition-dots" aria-label="Состояние тиража">\n            '
            + "".join(dots) + "\n          </div>")


def status_block(art):
    """Блок тиража (editioned) или уникальности (unique)."""
    if art["workType"] == "unique":
        return f'''        <div class="lot__status lot__status--unique">
          <div class="lot__status__label"><b>Уникальная работа</b></div>
          <div class="lot__status__big"><span class="num">1</span><span class="of">из 1 · единственный экземпляр</span></div>
        </div>
        <p class="lot__trust-note">Это уникальная авторская работа. Экземпляр существует в одном варианте.</p>'''
    # editioned
    total = art.get("editionTotal")
    num = art.get("editionNumber")
    avail = art.get("availableCount")
    if not (total and num):
        # тираж в админке не заполнен — показываем без номеров
        label = f"Тираж · <b>{total} экз.</b>" if total else "Тиражная работа"
        return f'''        <div class="lot__status">
          <div class="lot__status__label">{label}</div>
        </div>
        <p class="lot__trust-note">Это авторский оттиск из ограниченного тиража. Каждый экземпляр подписан художником.</p>'''
    closed = art.get("editionClosed")
    if closed:
        note = '<div class="lot__status__note lot__status__note--alert">Тираж закрыт · больше не будет</div>'
    elif avail == 1:
        note = '<div class="lot__status__note lot__status__note--alert">Последний экземпляр</div>'
    elif avail <= 4:
        note = f'<div class="lot__status__note lot__status__note--alert">Осталось: {avail} экз.</div>'
    else:
        note = f'<div class="lot__status__note">Доступно: {avail} экз.</div>'
    ap = art.get("artistProofs") or 0
    ap_str = f" + {ap} авторских (a.p.)" if ap else ""
    return f'''        <div class="lot__status">
          <div class="lot__status__label">Тираж · <b>{total}</b>{ap_str}</div>
          <div class="lot__status__big"><span class="num">{num}</span><span class="of">из {total} · этот экземпляр</span></div>
          {edition_dots(art)}
          {note}
        </div>
        <p class="lot__trust-note">Это авторский оттиск из ограниченного тиража. Каждый экземпляр подписан и пронумерован художником.</p>'''


def cta_block(art):
    """CTA: available → форма-заявка (модалка); reserved/sold → Telegram."""
    status = art["status"]
    slug = art["slug"]
    wish = f'<button class="btn btn--big btn--ghost" aria-label="Сохранить в избранное" data-fav-toggle data-fav-slug="{slug}" aria-pressed="false" data-analytics="lot-wishlist" data-lot-slug="{slug}">♡</button>'
    extra = f'''        <div class="lot__cta-extra">
          <a class="btn btn--ghost" data-tg-text="Здравствуйте! Хочу подобрать раму для «{esc(art['title'])}» — {esc(art['artistName'])}, {art['year']}, {esc(art['sheetSize'])}." data-analytics="lot-frame" data-lot-slug="{slug}">Подобрать раму</a>
          <a class="btn btn--ghost" data-tg-text="Здравствуйте! Есть вопрос по «{esc(art['title'])}» — {esc(art['artistName'])}, {art['year']}." data-analytics="lot-curator-question" data-lot-slug="{slug}">Задать вопрос куратору</a>
        </div>'''
    if status == "sold":
        return f'''        <div class="lot__cta">
          <a class="btn btn--big btn--ghost" data-tg-text="Здравствуйте! Работа «{esc(art['title'])}» продана. Подскажите, появится ли что-то похожее у {esc(art['artistName'])}?" data-analytics="lot-sold-ask" data-lot-slug="{slug}">Работа продана · спросить о похожей</a>
          {wish}
        </div>'''
    if status == "reserved":
        tg = f"Здравствуйте! Работа «{esc(art['title'])}» — {esc(art['artistName'])} забронирована. Хочу встать в лист ожидания, если бронь снимется."
        return f'''        <div class="lot__cta">
          <a class="btn btn--big btn--ghost" data-tg-text="{tg}" data-analytics="lot-waitlist" data-lot-slug="{slug}">Уже забронирована · встать в лист ожидания</a>
          {wish}
        </div>
{extra}'''
    cta_label = "Забронировать работу" if art["workType"] == "unique" else "Забронировать экземпляр"
    tg = esc(art["telegramReserveText"])
    return f'''        <div class="lot__cta">
          <a class="btn btn--big btn--accent" data-buy data-buy-type="Заявка на работу" data-work="{esc(art['title'])}" data-price="{esc(art['priceFormatted'])}" data-tg-text="{tg}" data-analytics="lot-reserve" data-lot-slug="{slug}" data-work-type="{art['workType']}">
            {cta_label}
            <svg width="18" height="14" viewBox="0 0 18 14" fill="none" aria-hidden="true"><path d="M1 7H17M17 7L11 1M17 7L11 13" stroke="currentColor" stroke-width="2"/></svg>
          </a>
          {wish}
        </div>
{extra}'''


def work_card(art, stagger=False, delay=None):
    """Карточка работы для каталога / блоков «ещё у автора»."""
    svg = plate_visual(art)
    plate_h = ' work__plate--horizontal' if art.get("orientation") == "horizontal" else ''
    aname = art["artistName"]
    initials = aname.split()[0][0] + ". " + aname.split()[-1] if len(aname.split()) >= 2 else aname
    ed = ed_label(art)
    # бейдж
    badge = ""
    cls = "work"
    if art["status"] == "sold":
        badge = '<span class="work__badge work__badge--sold">Продано</span>'
        cls += " is-sold"
    elif art["status"] == "reserved":
        badge = '<span class="work__badge work__badge--reserved">Бронь</span>'
        cls += " is-reserved"
    elif art["workType"] == "unique":
        badge = '<span class="work__badge work__badge--unique">1/1 · уникальная</span>'
    elif art.get("editionClosed"):
        badge = '<span class="work__badge work__badge--last">Тираж закрыт</span>'
    elif art.get("availableCount") == 1:
        badge = '<span class="work__badge work__badge--last">Последний экз.</span>'
    elif art.get("availableCount") and art["availableCount"] <= 4:
        badge = f'<span class="work__badge work__badge--last">Осталось {art["availableCount"]}</span>'
    stag = ' stagger' if stagger else ''
    stag_attr = f' data-stag-delay="{delay}"' if delay else ''
    href = f'work-{art["slug"]}.html'
    sub = (f'{art["technique"]} · {art["sheetSize"].replace(" см","").replace(" × ","×")} · тираж <b>{art["editionTotal"]}</b>'
           if art["workType"] == "editioned" and art.get("editionTotal")
           else f'{art["technique"]} · {art["sheetSize"].replace(" см","").replace(" × ","×")} · тираж'
           if art["workType"] == "editioned"
           else f'{art["technique"]} · {art["sheetSize"].replace(" см","").replace(" × ","×")} · <b>1/1</b>')
    search_blob = esc(f"{art.get('title','')} {aname} {art.get('technique','')}".lower())
    filt = (f' data-price="{art.get("price",0)}" data-status="{art["status"]}"'
            f' data-technique="{art["techniqueGroup"]}" data-type="{art["workType"]}"'
            f' data-available="{art.get("availableCount",1)}" data-year="{art.get("year","")}"'
            f' data-order="{art.get("order",99)}" data-search="{search_blob}"')
    return f'''<a class="{cls}{stag}" href="{href}" data-work-color="{art['dominantColor']}"{stag_attr} data-analytics="work-card" data-work-slug="{art['slug']}"{filt}>
          {badge}
          <button class="work__fav" data-fav-toggle data-fav-slug="{art['slug']}" aria-label="В избранное" aria-pressed="false">♡</button>
          <div class="work__sheet">
            <div class="work__plate{plate_h}">
              {svg}
            </div>
            <div class="work__sig"><span>{initials}</span><span>{ed}</span></div>
          </div>
          <div class="work__meta">
            <div class="work__author">{aname} · {art['year']}</div>
            <div class="work__title">{art['title']}</div>
            <div class="work__price">{art['priceFormatted']}</div>
            <div class="work__sub">{sub}</div>
          </div>
        </a>'''


def render_work_page(art):
    a = artists_by_id[art["artistId"]]
    svg = plate_visual(art)
    canonical = f"{BASE_URL}/work-{art['slug']}.html"

    extra_meta = (f'  <meta property="product:price:amount" content="{art["price"]}"/>\n'
                  f'  <meta property="product:price:currency" content="RUB"/>\n'
                  f'  <meta property="product:availability" content="{"in stock" if art["status"]=="available" else "out of stock"}"/>\n')

    # eyebrow
    if art["workType"] == "unique":
        eyebrow = f'Уникальная работа · {art["technique"]} · {art["year"]}'
    else:
        if art.get("editionNumber") and art.get("editionTotal"):
            eyebrow = f'№ {art["editionNumber"]} из {art["editionTotal"]} · {art["technique"]} · {art["year"]}'
        else:
            eyebrow = f'Тиражная работа · {art["technique"]} · {art["year"]}'

    # имя на 2 строки
    parts = a["name"].split(" ", 1)
    author_h1 = f'{parts[0]}<br/>{parts[1]}.' if len(parts) == 2 else f'{a["name"]}.'

    # атрибуты — пустые строки скрываются; доп. характеристики из списка specs
    attrib_rows = [
        ("Техника", art.get("technique", "")),
        ("Размер листа", art.get("sheetSize", "")),
    ]
    if art.get("imageSize"):
        attrib_rows.append(("Размер изображения", art["imageSize"]))
    if art.get("paper"):
        attrib_rows.append(("Бумага", art["paper"]))
    if art["workType"] == "editioned":
        ap = art.get("artistProofs") or 0
        ed_str = (f'<b>{art["editionTotal"]} экз.</b>' if art.get("editionTotal") else '<b>тиражная</b>') + (f' + {ap} авторских (a.p.)' if ap else '')
        attrib_rows.append(("Тираж", ed_str))
    else:
        attrib_rows.append(("Тираж", "<b>уникальная работа · 1/1</b>"))
    if art.get("signature"):
        attrib_rows.append(("Подпись", art["signature"]))
    if art.get("condition"):
        attrib_rows.append(("Состояние", art["condition"]))
    # свободные характеристики из админки (название + значение)
    for spec in (art.get("specs") or []):
        label = (spec.get("label") or "").strip()
        value = (spec.get("value") or "").strip()
        if label and value:
            attrib_rows.append((esc(label), esc(value)))
    # на всякий случай прячем строки с пустым значением
    attrib_rows = [(k, v) for k, v in attrib_rows if str(v).strip()]
    attrib_html = "\n          ".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in attrib_rows)

    # цена-строка
    if art["status"] == "sold":
        avail_html = '<div class="eyebrow" style="margin-bottom: 4px;">статус</div><div style="font-family: var(--f-mono); font-size: 13px; color: var(--prstnk-color);">продано</div>'
    elif art["status"] == "reserved":
        avail_html = '<div class="eyebrow" style="margin-bottom: 4px;">статус</div><div style="font-family: var(--f-mono); font-size: 13px; color: var(--ink-2);">забронировано</div>'
    elif art["workType"] == "unique":
        avail_html = '<div class="eyebrow" style="margin-bottom: 4px;">в наличии</div><div style="font-family: var(--f-mono); font-size: 13px; color: var(--ink-2);">1 экз. · отправим за 1–2 дня</div>'
    else:
        avail_html = f'<div class="eyebrow" style="margin-bottom: 4px;">в наличии</div><div style="font-family: var(--f-mono); font-size: 13px; color: var(--ink-2);">{str(art["availableCount"]) + " экз. · " if art.get("availableCount") else ""}отправим за 1–2 дня</div>'

    # описание (если есть) — иначе нейтральный текст
    desc = art.get("description") or (
        f'«{art["title"]}» — {art["technique"]}, {a["name"]}, {art["year"]}. '
        f'{a["oneLiner"]}' + (' Лист отпечатан в мастерской и подписан автором карандашом.'
                              if re.search(r"монотип|линогр|офорт|сухая игла|литогр|шелкогр|акватинт", art["technique"].lower()) else ''))

    # ещё у автора (до 3 других)
    same_artist = [w for w in artworks if w["artistId"] == art["artistId"] and w["slug"] != art["slug"]][:3]
    # похожее по технике (другие авторы, та же группа)
    mood = [w for w in artworks if w["techniqueGroup"] == art["techniqueGroup"]
            and w["artistId"] != art["artistId"] and w["slug"] != art["slug"]][:3]
    if len(mood) < 3:
        extra = [w for w in artworks if w["slug"] != art["slug"]
                 and w not in same_artist and w not in mood][:3 - len(mood)]
        mood += extra

    def grid(cards):
        return ('<div class="grid-works">\n        '
                + "\n        ".join(work_card(w) for w in cards) + "\n      </div>")

    same_artist_section = ""
    if same_artist:
        same_artist_section = f'''    <section style="padding: 80px 0 0;">
      <div class="section-head">
        <h2 class="stagger">Ещё <em>у {a["gen"].split()[-1]}</em>.</h2>
        <div class="section-head__right">
          <span>{a["worksCount"]} {"работа" if a["worksCount"]==1 else ("работы" if a["worksCount"]<5 else "работ")} в коллекции</span>
          <a class="link" href="artist-{a["slug"]}.html" data-analytics="lot-artist-all">Все работы автора →</a>
        </div>
      </div>
      {grid(same_artist)}
    </section>
'''

    mood_section = ""
    if mood:
        mood_section = f'''    <section style="padding: 60px 0 0;">
      <div class="section-head">
        <h2 class="stagger">Похожее <em>по настроению</em>.</h2>
        <div class="section-head__right">
          <span>Подобрано вручную куратором</span>
          <a class="link" href="works.html" data-analytics="lot-back-to-catalog">К витрине →</a>
        </div>
      </div>
      {grid(mood)}
    </section>
'''

    body = f'''{head(art["seoTitle"], art["seoDescription"], canonical, og_type="product", extra_meta=extra_meta)}{HEADER}
  <main class="wrap">
    <nav class="crumbs" aria-label="Хлебные крошки">
      <a href="index.html">Главная</a><span class="sep">/</span>
      <a href="artists.html">Художники</a><span class="sep">/</span>
      <a href="artist-{a['slug']}.html" data-analytics="crumbs-artist">{a['name']}</a><span class="sep">/</span>
      <span class="here">{art['title']}</span>
    </nav>

    <section class="lot">
      <div class="lot__stage{' lot__stage--horizontal' if art.get('orientation') == 'horizontal' else ''} stagger" data-stag-delay="0">
        <div class="sheet">
          <div class="sheet__plate{' sheet__plate--horizontal' if art.get('orientation') == 'horizontal' else ''}">
            {svg}
          </div>
          <div class="sheet__sig">
            <span>{art['artistName'].split()[0][0]}. {art['artistName'].split()[-1]}, {art['year']}</span>
            <span>{ed_label(art)}</span>
          </div>
        </div>
      </div>

      <div class="lot__info stagger" data-stag-delay="0.10">
        <div class="eyebrow">{eyebrow}</div>
        <h1 class="lot__author"><a href="artist-{a['slug']}.html" style="color: inherit;">{author_h1}</a></h1>
        <h2 class="lot__title"><span class="lot__q">«</span>{art['title']}<span class="lot__q">»</span>, <span class="lot__year">{art['year']}</span></h2>

        <dl class="lot__attrib">
          {attrib_html}
        </dl>

{status_block(art)}

        <div class="lot__price-row">
          <div class="lot__price"><small>цена</small>{art['priceFormatted']}</div>
          <div style="text-align: right;">{avail_html}</div>
        </div>

{cta_block(art)}

        <div class="authenticity">
          <h4>Подлинность</h4>
          <ul>
            <li>Подпись карандашом{" и нумерация автора" if art["workType"]=="editioned" else " автора"}</li>
            <li>Оригинал — не репродукция и не постер</li>
            <li>{"Бережная упаковка в короб" if art.get("techniqueGroup") in ("painting", "object", "author-tech") else "Архивный тубус + картон"} + открытка от куратора</li>
            <li>Возврат в течение 14 дней без вопросов</li>
          </ul>
        </div>

        <div class="lot__description">
          <h3>О работе</h3>
          <p>{desc}</p>
        </div>
      </div>
    </section>

{same_artist_section}{mood_section}  </main>

{FOOTER}'''
    return body


def render_catalog():
    groups = [
        ("lithography", "Литография"),
        ("silkscreen", "Шелкография"),
        ("linocut", "Линогравюра"),
        ("etching", "Офорт"),
        ("graphics", "Графика и монотипия"),
        ("painting", "Живопись"),
        ("object", "Объект"),
        ("author-tech", "Авторская техника"),
    ]
    total = len(artworks)
    avail = sum(1 for w in artworks if w["status"] == "available")
    min_price = min(w["price"] for w in artworks)
    min_price_str = f"{min_price:,}".replace(",", " ")  # 4800 → «4 800»

    # Чипсы техник (выбор один из) + чипсы-переключатели
    tech_chips = ['<button class="catalog-filter__chip is-active" data-group="tech" data-filter="all" data-analytics="catalog-filter">Все техники</button>']
    for gid, label in groups:
        tech_chips.append(f'<button class="catalog-filter__chip" data-group="tech" data-filter="{gid}" data-analytics="catalog-filter">{label}</button>')
    toggle_chips = [
        '<button class="catalog-filter__chip" data-toggle="available" data-analytics="catalog-toggle">В наличии</button>',
        '<button class="catalog-filter__chip" data-toggle="under10k" data-analytics="catalog-toggle">До 10 000 ₽</button>',
        '<button class="catalog-filter__chip" data-toggle="unique" data-analytics="catalog-toggle">Уникальные 1/1</button>',
        '<button class="catalog-filter__chip" data-toggle="last" data-analytics="catalog-toggle">Последние экземпляры</button>',
    ]
    tech_html = "".join(chr(10) + "        " + c for c in tech_chips)
    toggle_html = "".join(chr(10) + "        " + c for c in toggle_chips)

    # Все работы одной сеткой, в кураторском порядке (artworks отсортированы по order)
    cards = "\n        ".join(work_card(w) for w in artworks)

    canonical = f"{BASE_URL}/works.html"
    title = "Каталог оригинальных работ — PRSTNK"
    desc = f"Оригинальные работы петербургских художников: живопись, графика, авторская печать и объекты. Уникальные работы и небольшие тиражи, от {min_price_str} ₽."

    return f'''{head(title, desc, canonical)}{HEADER}
  <main class="wrap">
    <nav class="crumbs" aria-label="Хлебные крошки">
      <a href="index.html">Главная</a><span class="sep">/</span>
      <span class="here">Каталог</span>
    </nav>

    <section class="page-hero">
      <div class="eyebrow">№ 04 · <b>Каталог</b></div>
      <h1>Все <em>{total} {_plural(total, "работа", "работы", "работ")}</em>.<br/>Подписано автором.</h1>
      <p class="page-hero__lead">
        Полный каталог PRSTNK: живопись, графика, авторская печать и объекты. Уникальные работы и оттиски из небольших тиражей — только оригиналы, никаких репродукций.
      </p>
      <div class="page-hero__stats">
        <div><b>{total}</b>работ в каталоге</div>
        <div><b>{avail}</b>доступно сейчас</div>
        <div><b>от {min_price_str} ₽</b>стартовая цена</div>
        <div><b>{len(artists)}</b>художников</div>
      </div>
    </section>

    <div class="catalog-toolbar">
      <div class="cat-chips" role="group" aria-label="Фильтры">{tech_html}
        <span class="cat-chips__break" aria-hidden="true"></span>{toggle_html}
      </div>
      <div class="cat-tools">
        <label class="cat-search">
          <span class="cat-search__icon" aria-hidden="true">⌕</span>
          <input type="search" id="catSearch" placeholder="Название, художник, техника" aria-label="Поиск по каталогу"/>
        </label>
        <select class="cat-sort" id="catSort" aria-label="Сортировка">
          <option value="curated">Кураторская подборка</option>
          <option value="new">Сначала новые</option>
          <option value="price-asc">Сначала дешевле</option>
          <option value="price-desc">Сначала дороже</option>
        </select>
      </div>
    </div>
    <div class="catalog-meta">
      <span id="catCount">Показано {total} из {total}</span>
      <button class="cat-reset" id="catReset" hidden>Сбросить фильтры</button>
    </div>

    <section class="catalog-grid-wrap">
      <div class="grid-works" id="catGrid">
        {cards}
      </div>
      <div class="catalog-empty" id="catEmpty" hidden>
        <h3>Ничего не нашлось.</h3>
        <p>Снимите часть фильтров — или попросите куратора подобрать листы под вашу стену.</p>
        <a class="btn btn--accent" data-fit data-tg-text="Здравствуйте! Не нашёл подходящую работу в каталоге — помогите подобрать." data-analytics="catalog-empty">Куратор подберёт →</a>
      </div>
    </section>

    <section class="fit-block" style="padding: 56px 0;">
      <div class="fit__grid">
        <div class="fit__left">
          <div class="eyebrow">Не нашли своё?</div>
          <h2 style="font-size: clamp(32px, 4.4vw, 56px); margin-top: 16px;">Куратор подберёт <em>под стену</em>.</h2>
          <p class="fit__lead">Покажите фото стены, и мы подберём 3–5 работ по размеру, цвету и настроению. Бесплатно.</p>
          <a class="btn btn--big btn--accent fit__cta" data-fit data-tg-text="Здравствуйте! Хочу подбор работы по фото стены." data-analytics="catalog-fit">
            Отправить фото стены
            <svg width="18" height="14" viewBox="0 0 18 14" fill="none" aria-hidden="true"><path d="M1 7H17M17 7L11 1M17 7L11 13" stroke="currentColor" stroke-width="2"/></svg>
          </a>
        </div>
        <div class="fit__right" aria-hidden="true">
          <svg viewBox="0 0 400 320" preserveAspectRatio="xMidYMid meet">
            <rect width="400" height="320" fill="#F0EEE8"/>
            <g transform="translate(140, 50)">
              <rect width="120" height="160" fill="#F8F6F1" stroke="#141413" stroke-width="2"/>
              <rect x="14" y="14" width="92" height="110" fill="#E8DCBE"/>
              <rect x="32" y="32" width="56" height="50" fill="#0E2F66"/>
              <circle cx="78" cy="48" r="8" fill="#FFCC00"/>
              <rect x="44" y="92" width="32" height="22" fill="#FA2A22"/>
            </g>
            <text x="200" y="280" font-family="monospace" font-size="13" text-anchor="middle" fill="#6E6B61" letter-spacing="2">3—5 ВАРИАНТОВ ПОДБОРКИ</text>
          </svg>
        </div>
      </div>
    </section>
  </main>

{FOOTER}'''


def render_artist_page(a, idx):
    canonical = f"{BASE_URL}/artist-{a['slug']}.html"
    title = f"{a['name']}. Художник PRSTNK"
    one_clean = re.sub(r"<[^>]+>", "", a["oneLiner"])
    desc = f"{a['name']} — петербургский художник. {', '.join(a['techniques'][:3])}. {one_clean}"
    parts = a["name"].split(" ", 1)
    h1 = f'{parts[0]}<br/>{parts[1]}.' if len(parts) == 2 else f'{a["name"]}.'

    _meta = a.get("meta", [])
    if isinstance(_meta, dict):  # старый формат (ключ:значение) — поддержим на всякий
        _meta = [{"key": k, "value": v} for k, v in _meta.items()]
    meta_dl = "\n          ".join(
        f"<dt>{row.get('key','')}</dt><dd>{row.get('value','')}</dd>" for row in _meta)
    bio = "\n        ".join(f"<p>{p}</p>" for p in a.get("bio", []))
    colls = "\n          ".join(f"<li>{c}</li>" for c in a.get("collections", []))

    works = [w for w in artworks if w["artistId"] == a["id"]]
    if works:
        n = len(works)
        word = "работа" if n == 1 else ("работы" if n < 5 else "работ")
        works_h2 = f'<em>{n} {word}</em> {a["firstName"]} у нас.'
        cards = "\n        ".join(work_card(w) for w in works)
        works_html = f'<div class="grid-works">\n        {cards}\n      </div>'
    else:
        works_h2 = f'Работы <em>{a["firstName"]}</em>.'
        works_html = f'''<div class="artist-works__empty">
        <h3>В каталоге пока нет работ.</h3>
        <p>Из архива можем подобрать что-то конкретное — напишите куратору в Telegram, расскажем, что есть у {a['gen']} в работе и какие тиражи готовятся.</p>
        <a class="btn btn--accent" data-tg-text="Здравствуйте! Хочу узнать про работы {a['gen']} — что есть в архиве?" data-analytics="artist-empty-cta">Спросить про работы {a['firstName']} →</a>
      </div>'''

    return f'''{head(title, desc, canonical, og_type="profile")}{HEADER}
  <main class="wrap">
    <nav class="crumbs" aria-label="Хлебные крошки">
      <a href="index.html">Главная</a><span class="sep">/</span>
      <a href="artists.html">Художники</a><span class="sep">/</span>
      <span class="here">{a['name']}</span>
    </nav>

    <section class="artist-page-hero">
      <div>
        <div class="eyebrow"><b>№ {idx:02d}</b> · художник</div>
        <h1>{h1}</h1>
        <p class="one-liner">{a['oneLiner']}</p>
      </div>
      <div class="artist-page-hero__meta">
        <dl>{meta_dl}</dl>
      </div>
    </section>

    <section class="artist-bio">
      <div><h2>О художнике</h2></div>
      <div class="artist-bio__body">
        {bio}
      </div>
    </section>

    <section class="artist-collections">
      <div><h2>Где увидеть<br/>и коллекции</h2></div>
      <div><ul>{colls}</ul></div>
    </section>

    <section class="artist-works">
      <div class="artist-works__head">
        <h2>{works_h2}</h2>
        <span class="meta"><a href="works.html" style="color: inherit; border-bottom: 1px solid currentColor; padding-bottom: 2px;">Весь каталог →</a></span>
      </div>
      {works_html}
    </section>
  </main>

{FOOTER}'''


def render_artists_index():
    canonical = f"{BASE_URL}/artists.html"
    vis = [a for a in artists if a.get("showInArtists", True)]
    nvis = len(vis)
    word_cap = num2word_ru(nvis)
    noun = _plural(nvis, "имя", "имени", "имён")
    title = f"Художники PRSTNK — {word_cap.lower()} {noun} ленинградской школы"
    desc = "Петербургские художники PRSTNK: " + ", ".join(a["name"] for a in vis) + "."

    cards = []
    for idx, a in enumerate(vis, start=1):
        n = a["worksCount"]
        if n == 0:
            count_html = '<span class="artist-card__count">скоро</span>'
        else:
            word = "работа" if n == 1 else ("работы" if n < 5 else "работ")
            count_html = f'<span class="artist-card__count"><b>{n}</b> {word}</span>'
        meta = f'{", ".join(a["techniques"][:3])} · {a["city"]}'
        if a.get("birthYear"):
            meta += f' · {a["birthYear"]}'
        cards.append(f'''<a class="artist-card" href="artist-{a['slug']}.html" data-analytics="artist-card" data-artist-slug="{a['slug']}">
        <div class="artist-card__num">{idx:02d}</div>
        <h3 class="artist-card__name">{a['name']}</h3>
        <div class="artist-card__meta">{meta}</div>
        <p class="artist-card__bio">{a['oneLiner']}</p>
        <div class="artist-card__bottom">
          {count_html}
          <span class="artist-card__cta">Работы {a['firstName']} →</span>
        </div>
      </a>''')

    cards_html = "\n      ".join(cards)
    return f'''{head(title, desc, canonical)}{HEADER}
  <main class="wrap">
    <nav class="crumbs" aria-label="Хлебные крошки">
      <a href="index.html">Главная</a><span class="sep">/</span>
      <span class="here">Художники</span>
    </nav>

    <section class="page-hero">
      <div class="eyebrow">№ 05 · <b>Все художники</b></div>
      <h1>{word_cap} <em>{noun}</em>.</h1>
      <div class="page-hero__stats">
        <div><b>{nvis}</b>художников</div>
        <div><b>{len(artworks)}</b>работ в каталоге</div>
      </div>
    </section>

    <section class="artists-grid">
      {cards_html}
    </section>

    <section class="fit-block" style="padding: 56px 0;">
      <div class="fit__grid">
        <div class="fit__left">
          <div class="eyebrow">Не знаете кого выбрать?</div>
          <h2 style="font-size: clamp(32px, 4.4vw, 56px); margin-top: 16px;">Куратор <em>подскажет</em>.</h2>
          <p class="fit__lead">Напишите, что у вас на стене сейчас и какое настроение хотите, и мы подберём работы под ваш интерьер.</p>
          <a class="btn btn--big btn--accent fit__cta" data-tg-text="Здравствуйте! Помогите выбрать художника. Расскажу про интерьер и настроение." data-analytics="artists-curator">
            Спросить у куратора
            <svg width="18" height="14" viewBox="0 0 18 14" fill="none" aria-hidden="true"><path d="M1 7H17M17 7L11 1M17 7L11 13" stroke="currentColor" stroke-width="2"/></svg>
          </a>
        </div>
        <div class="fit__right" aria-hidden="true">
          <svg viewBox="0 0 400 320" preserveAspectRatio="xMidYMid meet">
            <rect width="400" height="320" fill="#F0EEE8"/>
            <g transform="translate(40, 60)"><rect width="90" height="120" fill="#F8F6F1" stroke="#141413" stroke-width="2"/><rect x="10" y="10" width="70" height="80" fill="#2A4BFF"/><circle cx="45" cy="50" r="14" fill="#FFCC00"/></g>
            <g transform="translate(155, 60)"><rect width="90" height="120" fill="#F8F6F1" stroke="#141413" stroke-width="2"/><rect x="10" y="10" width="70" height="80" fill="#FA2A22"/><rect x="32" y="40" width="26" height="34" fill="#141413"/></g>
            <g transform="translate(270, 60)"><rect width="90" height="120" fill="#F8F6F1" stroke="#141413" stroke-width="2"/><rect x="10" y="10" width="70" height="80" fill="#2E5A2A"/><ellipse cx="45" cy="50" rx="20" ry="12" fill="#FF3DA0"/></g>
            <text x="200" y="230" font-family="monospace" font-size="14" text-anchor="middle" fill="#6E6B61" letter-spacing="2">КУРАТОР → ВЫ</text>
          </svg>
        </div>
      </div>
    </section>
  </main>

{FOOTER}'''


# ============================================================
#  ЖУРНАЛ «ЁPRST» — лента, выпуски и страницы выпусков
# ============================================================

PALETTE = {
    "alyi": "#FA2A22", "limon": "#FFCC00", "kobalt": "#2A4BFF",
    "hvoya": "#2E5A2A", "fuxia": "#FF3DA0", "ugol": "#161614",
}

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

_MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня",
           "июля", "августа", "сентября", "октября", "ноября", "декабря"]


def _plural(n, one, few, many):
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
        return few
    return many


_NUMWORDS = {
    1: "Одно", 2: "Два", 3: "Три", 4: "Четыре", 5: "Пять", 6: "Шесть", 7: "Семь",
    8: "Восемь", 9: "Девять", 10: "Десять", 11: "Одиннадцать", 12: "Двенадцать",
    13: "Тринадцать", 14: "Четырнадцать", 15: "Пятнадцать", 16: "Шестнадцать",
    17: "Семнадцать", 18: "Восемнадцать", 19: "Девятнадцать", 20: "Двадцать",
    21: "Двадцать одно", 22: "Двадцать два", 23: "Двадцать три", 24: "Двадцать четыре",
    25: "Двадцать пять", 30: "Тридцать", 40: "Сорок",
}


def num2word_ru(n):
    """Число → слово для заголовков (Двенадцать). Вне таблицы — цифрой."""
    return _NUMWORDS.get(int(n), str(n))


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s or "").replace("&nbsp;", " ").strip()


def _md_inline(s):
    """Строчное форматирование: ссылки, **жирный**, *курсив*, _курсив_."""
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\*([^*]+?)\*", r"<em>\1</em>", s)
    s = re.sub(r"(?<!\w)_([^_]+?)_(?!\w)", r"<em>\1</em>", s)
    return s


def md_to_html(text):
    """Мини-markdown → HTML. Понимает то, что выдаёт визуальный редактор с кнопками:
    заголовки (#/##/###), маркированные и нумерованные списки, цитаты (>),
    **жирный**, *курсив*, [ссылки], абзацы через пустую строку."""
    if not text:
        return ""
    lines = text.replace("\r\n", "\n").split("\n")
    blocks, para, i, n = [], [], 0, len(lines)

    def flush():
        if para:
            blocks.append("<p>" + _md_inline(" ".join(p.strip() for p in para)) + "</p>")
            para.clear()

    while i < n:
        raw = lines[i]
        s = raw.strip()
        if not s:
            flush(); i += 1; continue
        m = re.match(r"^#{1,6}\s+(.*)$", s)
        if m:
            flush(); blocks.append("<h3>" + _md_inline(m.group(1).strip()) + "</h3>"); i += 1; continue
        if s.startswith(">"):
            flush(); q = []
            while i < n and lines[i].strip().startswith(">"):
                q.append(re.sub(r"^\s*>\s?", "", lines[i])); i += 1
            blocks.append("<blockquote>" + _md_inline(" ".join(x.strip() for x in q)) + "</blockquote>")
            continue
        if re.match(r"^[-*]\s+", s):
            flush(); items = []
            while i < n and re.match(r"^\s*[-*]\s+", lines[i]):
                items.append(re.sub(r"^\s*[-*]\s+", "", lines[i]).strip()); i += 1
            blocks.append("<ul>" + "".join(f"<li>{_md_inline(x)}</li>" for x in items) + "</ul>")
            continue
        if re.match(r"^\d+\.\s+", s):
            flush(); items = []
            while i < n and re.match(r"^\s*\d+\.\s+", lines[i]):
                items.append(re.sub(r"^\s*\d+\.\s+", "", lines[i]).strip()); i += 1
            blocks.append("<ol>" + "".join(f"<li>{_md_inline(x)}</li>" for x in items) + "</ol>")
            continue
        para.append(raw); i += 1
    flush()
    return "\n        ".join(blocks)


def iss_slug(issue):
    """Адрес выпуска: своё поле slug, иначе из номера (05 → zine-05.html)."""
    return issue.get("slug") or issue.get("number") or ""


def fmt_date_ru(s):
    s = (s or "")[:10]  # «2026-05-20T00:00…» → «2026-05-20»
    try:
        y, m, d = s.split("-")
        return f"{int(d)} {_MONTHS[int(m) - 1]} {y}"
    except (ValueError, IndexError):
        return s


def issue_has_page(issue):
    """Выпуск получает отдельную страницу zine-<slug>.html, если в нём есть статьи
    (свои, articles) или он собирает уже опубликованные материалы (materials — список slug)."""
    return bool(issue.get("articles") or issue_materials(issue))


def issue_materials(issue):
    """Опубликованные статьи журнала, собранные в выпуск (поле materials: список slug), по порядку."""
    by_slug = {a.get("slug"): a for a in articles}
    return [by_slug[s] for s in (issue.get("materials") or []) if s in by_slug]


def series_cards(arts, cls="sx"):
    """Карточки статей выпуска: обложка, номер, город/рубрика, заголовок, вводка."""
    out = []
    for i, a in enumerate(arts, start=1):
        img = a.get("cover", "")
        t = esc(strip_tags(a.get("title", "")))
        em = a.get("titleEm", "")
        if em:
            t = t.replace(esc(em), f"<em>{esc(em)}</em>", 1)
        acc = a.get("accent", "alyi")
        out.append(f'''<a class="{cls}-card" href="journal/{esc(a.get("slug", ""))}" style="--sx-accent:var(--c-{esc(acc)})">
      <span class="{cls}-img">{f'<img src="{esc(img)}"{_wh(img)} loading="lazy" alt=""/>' if img else ""}</span>
      <span class="{cls}-n">{i:02d}</span>
      <span class="{cls}-title">{t}</span>
      <span class="{cls}-lead">{esc(strip_tags(a.get("lead", "")))}</span>
      <span class="{cls}-go">Читать →</span>
    </a>''')
    return "\n".join(out)


def render_series_issue_page(issue):
    """Страница выпуска, который собирает уже опубликованные статьи в одну историю."""
    slug = iss_slug(issue)
    canonical = f"{BASE_URL}/zine-{slug}.html"
    arts = issue_materials(issue)
    plain = strip_tags(issue.get("title", ""))
    title = f'«ЁPRST» № {issue.get("number", "")}, {issue.get("period", "")}: {plain} — PRSTNK'
    desc = strip_tags(issue.get("coverLead") or issue.get("lead", ""))
    body = f'''<div class="jn-wrap sx-page">
  <a class="material-back material-back--top" href="journal">← В журнал</a>
  <div class="sx-eyebrow">Выпуск № {esc(issue.get("number", ""))} · {esc(issue.get("period", ""))} · {len(arts)} {_plural(len(arts), "статья", "статьи", "статей")}</div>
  <h1 class="sx-h1">{issue.get("title", "")}</h1>
  <p class="sx-lead">{esc(desc)}</p>
  <div class="sx-grid">
    {series_cards(arts)}
  </div>
</div>'''
    return (f'{head(title, desc, canonical, extra_css="journal.css", base_href="/")}{HEADER}\n{body}\n{FOOTER}')


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
    num     = str(issue.get("number") or "").zfill(2)
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
    y2 = "248" if line2 else "264"  # две строки: line1 на 248; одна строка: на 264 (центр)
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


def issue_cover_visual(issue):
    """Обложка: загруженное фото (если есть) или автообложка."""
    img = (issue.get("coverImage") or "").strip()
    if img:
        from urllib.parse import quote
        img = quote(img.lstrip("/"), safe="/")
        return (f'<img src="{img}" alt="Обложка выпуска № {issue.get("number","")}" '
                f'loading="lazy" style="width:100%;height:100%;object-fit:cover;display:block;"/>')
    return issue_cover_svg(issue)


def render_picks(picks):
    """Блок «работы из каталога» — данные подтягиваются из artworks по слагу."""
    rows = []
    for i, p in enumerate(picks, start=1):
        w = artworks_by_slug.get(p.get("work"))
        if w:
            size = (w.get("sheetSize", "") or "").replace(" см", "").replace(" × ", "×")
            small = f'{w["artistName"]} · {w["year"]} · {w["technique"]} · {size} · {w["priceFormatted"]}'
            title, href, slug = w["title"], f'work-{w["slug"]}.html', w["slug"]
        else:
            title = p.get("title", p.get("work", ""))
            small = p.get("small", "")
            href, slug = "works.html", p.get("work", "")
        rows.append(f'''<div class="zine-pick">
          <div class="zine-pick__num">{i:02d}</div>
          <div>
            <div class="zine-pick__title">{title} <small>{small}</small></div>
          </div>
          <a class="zine-pick__cta" href="{href}" data-analytics="zine-pick" data-pick="{slug}">Купить →</a>
          <div class="zine-pick__body">
            {p.get("note", "")}
          </div>
        </div>''')
    return '<div class="zine-article__picks">\n        ' + "\n        ".join(rows) + '\n      </div>'


def render_article(issue, art, idx):
    eyebrow = art.get("kicker", "")
    if art.get("readMins"):
        eyebrow = (f'{eyebrow} · читать {art["readMins"]} мин' if eyebrow
                   else f'читать {art["readMins"]} мин')
    parts = [f'    <article class="zine-article" id="article-{idx}">',
             f'      <div class="zine-article__eyebrow">{eyebrow}</div>',
             f'      <div class="zine-article__num">{idx:02d}</div>',
             f'      <h2>{art.get("title", "")}</h2>']
    if art.get("lead"):
        parts.append(f'      <p class="zine-article__lead">{art["lead"]}</p>')
    if art.get("body"):
        parts.append(f'      <div class="zine-article__body">\n        {md_to_html(art["body"])}\n      </div>')
    pq = art.get("pullquote") or {}
    if pq.get("text"):
        cite = f'\n        <cite>{pq["cite"]}</cite>' if pq.get("cite") else ""
        parts.append(f'      <blockquote class="zine-pullquote">\n        {pq["text"]}{cite}\n      </blockquote>')
    if art.get("picksIntro"):
        parts.append(f'      <div class="zine-article__body">\n        {md_to_html(art["picksIntro"])}\n      </div>')
    if art.get("picks"):
        parts.append("      " + render_picks(art["picks"]))
    if art.get("bodyAfter"):
        parts.append(f'      <div class="zine-article__body">\n        {md_to_html(art["bodyAfter"])}\n      </div>')
    cta = art.get("cta") or {}
    if cta.get("label"):
        parts.append(f'''      <div style="margin-top: 32px;">
        <a class="btn btn--big btn--accent" data-tg-text="{esc(cta.get("tgText", ""))}" data-analytics="zine-{iss_slug(issue)}-cta">
          {cta["label"]}
          {ARROW}
        </a>
      </div>''')
    al = art.get("artistLink") or {}
    if al.get("slug") and any(a["slug"] == al["slug"] for a in artists):
        parts.append(f'''      <div style="margin-top: 32px;">
        <a class="btn btn--ghost" href="artist-{al["slug"]}.html" data-analytics="zine-{iss_slug(issue)}-artist-{al["slug"]}">
          {al.get("label", "На страницу художника")} →
        </a>
      </div>''')
    parts.append('    </article>')
    return "\n".join(parts)


def render_issue_page(issue):
    slug = iss_slug(issue)
    canonical = f"{BASE_URL}/zine-{slug}.html"
    plain_title = strip_tags(issue.get("title", ""))
    title = f'«ЁPRST» № {issue["number"]}, {issue["period"]}: {plain_title} — PRSTNK'
    desc = strip_tags(issue.get("coverLead") or issue.get("lead", ""))
    credits = issue.get("credits") or []
    author = credits[0]["name"] if credits else "PRSTNK"
    extra_meta = f'  <meta property="article:author" content="{esc(author)}"/>\n'

    arts = issue.get("articles", [])
    mc = issue.get("materialsCount") or len(arts)
    cover_eyebrow = f'Выпуск № {issue["number"]} · {issue["period"]}'
    if mc:
        cover_eyebrow += f' · {mc} {_plural(mc, "материал", "материала", "материалов")}'
    if issue.get("readingTime"):
        cover_eyebrow += f' · {issue["readingTime"]}'

    credits_html = ""
    if credits:
        credits_html = ('<div class="zine-cover__meta">\n        '
                        + "\n        ".join(f'<div><b>{c.get("role","")}:</b> {c.get("name","")}</div>'
                                            for c in credits) + '\n      </div>')

    toc_html = ""
    if len(arts) > 1:
        lis = []
        for i, a in enumerate(arts, start=1):
            tag = a.get("tocTag", "")
            tag_html = f'\n          <span class="toc-tag">{tag}</span>' if tag else ""
            lis.append(f'''<li>
          <a href="#article-{i}">{strip_tags(a.get("title", ""))}</a>{tag_html}
        </li>''')
        toc_html = f'''
    <section class="zine-toc">
      <div class="zine-toc__head">Содержание</div>
      <ol>
        {"".join(lis)}
      </ol>
    </section>
'''

    articles_html = "\n\n".join(render_article(issue, a, i) for i, a in enumerate(arts, start=1))

    next_eyebrow = ""
    if issue.get("nextIssue"):
        next_eyebrow = f'<div class="eyebrow" style="margin-bottom: 16px;">Следующий выпуск {issue["nextIssue"]}</div>'

    cover_lead = issue.get("coverLead") or issue.get("lead", "")

    return f'''{head(title, desc, canonical, og_type="article", extra_meta=extra_meta)}{HEADER}
  <main class="wrap">
    <nav class="crumbs" aria-label="Хлебные крошки">
      <a href="index.html">Главная</a><span class="sep">/</span>
      <a href="journal.html">Журнал</a><span class="sep">/</span>
      <span class="here">№ {issue["number"]} · {issue["period"]}</span>
    </nav>

    <section class="zine-cover">
      <div class="zine-cover__eyebrow">{cover_eyebrow}</div>
      <h1>{issue.get("title", "")}</h1>
      <p class="zine-cover__lead">
        {cover_lead}
      </p>
      {credits_html}
    </section>
{toc_html}
{articles_html}

    <section style="padding: 64px 0 32px; border-top: 2px solid var(--ink);">
      <div style="text-align: center;">
        {next_eyebrow}
        <h2 style="font-family: var(--f-display); font-weight: 800; font-size: clamp(32px, 4.4vw, 56px); letter-spacing: -0.035em; line-height: 1; margin-bottom: 24px;">Не пропускайте <em style="font-style: italic; color: var(--prstnk-color);">новые выпуски</em>.</h2>
        <p style="font-family: var(--f-text); font-size: 17px; line-height: 1.5; color: var(--ink-2); max-width: 48ch; margin: 0 auto 32px;">
          Между выпусками у нас в Telegram-канале — анонсы тиражей, репортажи из мастерских и короткие материалы, которые не попали в большой формат.
        </p>
        <a class="btn btn--big btn--accent"
           data-tg-text="Здравствуйте! Прочитал выпуск {issue["number"]} журнала «ЁPRST». Хочу подписаться на канал и не пропускать новые выпуски."
           data-analytics="zine-{slug}-subscribe">
          Подписаться на Telegram-канал
          {ARROW}
        </a>
      </div>
    </section>
  </main>

{FOOTER}'''


def _jrn_article_img(art: dict) -> str:
    """Изображение статьи: загруженное фото (image/cover) или SVG-плейсхолдер."""
    img = (art.get("image") or art.get("cover") or "").strip()
    if img:
        from urllib.parse import quote as _q
        return (f'<img src="{_q(img.lstrip("/"), safe="/")}" '
                f'alt="{esc(strip_tags(art.get("title", "")))}" '
                f'loading="lazy" style="width:100%;height:100%;object-fit:cover;display:block;"/>')
    rc = re.sub(r'[^#a-zA-Z0-9()., %]', '', art.get("rubricColor", "#FA2A22"))
    return (f'<svg viewBox="0 0 800 540" xmlns="http://www.w3.org/2000/svg" '
            f'style="width:100%;height:100%;display:block;" aria-hidden="true">'
            f'<rect width="800" height="540" fill="#1a1614"/>'
            f'<rect x="100" y="80" width="420" height="380" fill="{rc}" opacity=".18"/>'
            f'<circle cx="400" cy="270" r="90" fill="{rc}" opacity=".3"/>'
            f'</svg>')


def render_journal_index():
    canonical = f"{BASE_URL}/journal.html"
    title = "Журнал «ЁPRST» — PRSTNK"
    desc = ("Журнал PRSTNK про авторскую графику: разговоры с художниками, "
            "техники, коллекции, репортажи из мастерских. Выходит ежемесячно.")

    # ── данные ─────────────────────────────────────────────────────────────
    current = next((i for i in issues if i.get("current")), issues[0] if issues else {})
    fresh        = sorted(articles, key=lambda a: a.get("date", ""), reverse=True)
    hero_art     = next((a for a in fresh if a.get("featured")), fresh[0] if fresh else {})
    rest         = [a for a in fresh if a is not hero_art]
    lead_art     = rest[0] if rest else {}
    sec_arts     = rest[1:3]
    feature_art  = rest[3] if len(rest) > 3 else {}
    lenta_items  = lenta[:4]
    recent_iss   = issues[:3]

    # ── HERO (полноширинное фото + текст поверх) ────────────────────────────
    _hk = rubric_label(hero_art.get("rubric", ""))
    h_kicker = f'{_hk} · Статья недели' if _hk else 'Статья недели'
    h_title = esc(hero_art.get("title", current.get("title", "")))
    _hem = hero_art.get("titleEm", "")
    if _hem:
        h_title = h_title.replace(esc(_hem), f'<em>{esc(_hem)}</em>', 1)
    h_lead = esc(hero_art.get("lead", current.get("lead", "")))
    h_img = _jrn_article_img({**hero_art,
                              "rubricColor": PALETTE.get(rubric_color(hero_art.get("rubric", "")), "#FA2A22")})
    h_url = f'journal/{hero_art.get("slug", "")}' if hero_art else ""

    hero_html = f'''<a class="hero" href="{h_url}">
  <div class="hero-bg">{h_img}</div>
  <div class="hero-shade"></div>
  <div class="hero-overlay">
    <div class="hero-kicker">{h_kicker}</div>
    <h1 class="hero-h1">{h_title}</h1>
    <p class="hero-lead">{h_lead}</p>
    <span class="hero-cta">Читать →</span>
  </div>
</a>'''

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

    # ── ART HEADER ─────────────────────────────────────────────────────────
    art_header_html = '''<div class="art-header">
  <div class="art-header-label">— <b>Свежие материалы</b></div>
  <a class="art-header-meta" href="materials">Все материалы →</a>
</div>'''

    # ── EDITORIAL GRID ─────────────────────────────────────────────────────
    def _art_meta(a):
        parts = []
        if a.get("readMins"): parts.append(f'{a["readMins"]} мин')
        if a.get("date"):     parts.append(fmt_date_ru(a["date"]))
        return " · ".join(parts)

    lead_rub_cls = "rub-" + rubric_color(lead_art.get("rubric",""))
    lead_img     = _jrn_article_img({**lead_art, "rubricColor": PALETTE.get(rubric_color(lead_art.get("rubric","")), "#FA2A22")}) if lead_art else ""
    lead_url     = f'journal/{lead_art.get("slug","")}' if lead_art else ""

    lead_html = ""
    if lead_art:
        lead_cta = f'<a class="ed-read-link" href="{lead_url}">Читать →</a>' if lead_url else ""
        lead_html = f'''<article class="ed-lead">
  <div class="ed-lead-img">{lead_img}</div>
  <div class="ed-lead-body">
    <div class="rub {lead_rub_cls}">{rubric_label(lead_art.get("rubric",""))}</div>
    <h2 class="ed-h2">{lead_art.get("title","")}</h2>
    <p class="ed-lead-text">{lead_art.get("lead","")}</p>
    <div class="ed-meta">{_art_meta(lead_art)}</div>
    {lead_cta}
  </div>
</article>'''

    sec_html = ""
    for idx_s, sa in enumerate(sec_arts, start=3):
        sec_rub_cls = "rub-" + rubric_color(sa.get("rubric",""))
        sec_url = f'journal/{sa.get("slug","")}'
        sec_cta = f'<a class="ed-read-link" href="{sec_url}">Читать →</a>'
        sec_html += f'''<article class="ed-sec">
  <div class="rub {sec_rub_cls}">{rubric_label(sa.get("rubric",""))}</div>
  <h3 class="ed-h3">{sa.get("title","")}</h3>
  <div class="ed-meta">{_art_meta(sa)}</div>
  {sec_cta}
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
        feat_rub_cls = "rub-" + rubric_color(feature_art.get("rubric",""))
        feat_url  = f'journal/{feature_art.get("slug","")}'
        feat_cta  = f'<a class="ed-read-link" href="{feat_url}">Читать →</a>'
        pq = feature_art.get("pullquote") or {}
        pull_html = (f'<p class="ed-feat-pull">{pq["text"]}</p>' if pq.get("text") else "")
        feat_desc = feature_art.get("lead","")
        creds = current.get("credits", [])
        author = next((c["name"] for c in creds if c.get("role") in ("Гости","Автор")), "")
        author_html = f'<p class="ed-lead-text">{esc(author)}</p>' if author else ""
        feature_html = f'''<div class="ed-feature">
  <div class="ed-feat-left">
    <div class="rub {feat_rub_cls}">{rubric_label(feature_art.get("rubric",""))}</div>
    <h2 class="ed-h2">{feature_art.get("title","")}</h2>
    <p class="ed-lead-text">{feat_desc}</p>
    <div class="ed-meta">{_art_meta(feature_art)}</div>
    {feat_cta}
  </div>
  <div class="ed-feat-right">
    {pull_html}
    {author_html}
  </div>
</div>'''

    # ── ЛЕНТА ──────────────────────────────────────────────────────────────
    lc_html = "".join(lenta_card(m) for m in lenta_items)

    if lenta_items:
        lenta_html = f'''<div class="lenta-section">
  <div class="lenta-inner">
    <div class="lenta-label">
      <div>
        <div class="lenta-label-title">Лента.<br/><em>Каждый<br/>день.</em></div>
        <div class="lenta-label-sub">Петербург и мир · между выпусками</div>
      </div>
      <a class="lenta-label-tg" href="lenta">Вся лента →</a>
    </div>
    <div class="lenta-list">{lc_html}</div>
  </div>
</div>'''
    else:
        lenta_html = ""

    # ── ВЫПУСКИ ────────────────────────────────────────────────────────────
    issue_cards = ""
    for iss in recent_iss:
        slug_i = iss_slug(iss)
        href_i = f'href="zine-{slug_i}.html"' if issue_has_page(iss) else ""
        n_i    = iss.get("number","")
        p_i    = iss.get("period","")
        mc_i   = iss.get("materialsCount") or len(iss.get("articles",[])) or len(issue_materials(iss))
        im_i   = (f'№ {n_i} · {p_i} · {mc_i} {_plural(mc_i,"материал","материала","материалов")}'
                  if mc_i else f'№ {n_i} · {p_i}')
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

    # ── МАСТКЕД (нэйм-плашка журнала) ──────────────────────────────────────
    _mast_period = (current.get("period", "") or "").upper()
    _mast_num = current.get("number", "")
    _mast_stamp = (f'№ {_mast_num} · {_mast_period} · ВЫХОДИТ РАЗ В МЕСЯЦ'
                   if _mast_num else 'ВЫХОДИТ РАЗ В МЕСЯЦ')
    masthead_html = f'''<div class="jn-masthead">
  <div class="jn-mast-word">«<em>ЁPRST</em>»<em>.</em></div>
  <div class="jn-mast-side">
    <p class="jn-mast-desc">Выставки, поездки и художники, которых мы любим</p>
    <div class="jn-mast-stamp">{_mast_stamp}</div>
  </div>
</div>'''

    # ── СБОРКА ────────────────────────────────────────────────────────────
    raw = f'''{head(title, desc, canonical, extra_css="journal.css")}{HEADER}
<div class="jn-wrap">
{masthead_html}
{rubric_html}
{hero_html}
{art_header_html}
{grid_html}
{feature_html}
{lenta_html}
{issues_html}
</div>
{FOOTER}'''
    return clean_links(raw)


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

def img_dims(src):
    """Ширина и высота JPEG/PNG по заголовку файла (без сторонних библиотек), чтобы страница не «прыгала» при загрузке."""
    try:
        data = (ROOT / src.lstrip("/")).read_bytes()
    except OSError:
        return None
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    i = 2
    while i < len(data) - 9 and data[:2] == b"\xff\xd8":
        if data[i] != 0xFF:
            i += 1
            continue
        marker, size = data[i + 1], int.from_bytes(data[i + 2:i + 4], "big")
        if marker in (0xC0, 0xC1, 0xC2):
            return int.from_bytes(data[i + 7:i + 9], "big"), int.from_bytes(data[i + 5:i + 7], "big")
        i += 2 + size
    return None

def _wh(src):
    d = img_dims(src or "")
    return f' width="{d[0]}" height="{d[1]}"' if d else ""

def _cap_html(b, tag="figcaption"):
    """Подпись к фото: штамп времени съёмки (моно) + текст."""
    cap, t = b.get("caption", ""), b.get("time", "")
    if not (cap or t):
        return ""
    stamp = f'<span class="bl-stamp">{esc(t)}</span>' if t else ""
    return f'<{tag} class="bl-cap">{stamp}{esc(cap)}</{tag}>'

def _media_html(b):
    """Картинка или беззвучная видеопетля («живое фото» вместо гифки)."""
    alt = esc(b.get("alt") or b.get("caption", ""))
    if b.get("video"):
        poster = f' poster="{esc(b["poster"])}"' if b.get("poster") else ""
        return (f'<video class="bl-loop" src="{esc(b["video"])}"{poster}{_wh(b.get("poster"))} muted loop playsinline '
                f'preload="metadata" aria-label="{alt}"></video>')
    return f'<img src="{esc(b.get("image", ""))}"{_wh(b.get("image"))} loading="lazy" alt="{alt}"/>'

def _blk_photo(b):
    wide = " bl--wide" if b.get("wide") else ""
    return f'<figure class="bl bl-photo{wide}"{_shape_attr(b)}>{_media_html(b)}{_cap_html(b)}</figure>'

def _blk_split(b):
    side = "left" if b.get("imageSide") == "left" else "right"
    img_html = (f'<div class="bl-split-img"><img src="{esc(b.get("image", ""))}"{_wh(b.get("image"))} loading="lazy" '
                f'alt="{esc(b.get("caption", ""))}"/>{_cap_html(b, "div")}</div>')
    txt_html = f'<div class="bl-split-text">{md_to_html(b.get("text", ""))}</div>'
    inner = (img_html + txt_html) if side == "left" else (txt_html + img_html)
    return f'<div class="bl bl-split bl-split--{side}"{_shape_attr(b)}><div class="bl-split-grid">{inner}</div></div>'

def _blk_gallery(b):
    imgs = b.get("images") or []
    cells = "".join(f'<img src="{esc(i)}"{_wh(i)} loading="lazy" alt=""/>' for i in imgs)
    fit = ' data-fit="natural"' if b.get("fit") == "natural" else ""
    cap = _cap_html(b, "div")
    return f'<div class="bl bl-gallery{" bl--wide" if b.get("wide") else ""}" data-count="{len(imgs)}"{fit}>{cells}</div>{cap}'

def _blk_collage(b):
    """Свободная раскладка 2–3 кадров (фото и видеопетли) со смещением, на ширину шире текста."""
    items = b.get("items") or []
    cells = "".join(f'<figure class="cl-item">{_media_html(it)}{_cap_html(it)}</figure>' for it in items)
    return f'<div class="bl bl-collage bl--wide" data-count="{len(items)}" data-variant="{esc(b.get("variant", "a"))}"{_shape_attr(b)}>{cells}</div>'

def _blk_fullbleed(b):
    """Кадр на всю ширину экрана между главами (фото или видеопетля), с лёгким параллаксом."""
    return (f'<figure class="bl bl-fullbleed"><div class="fb-frame">{_media_html(b)}</div>'
            f'{_cap_html(b)}</figure>')

def _blk_note(b):
    """Сноска мелким шрифтом (пометки, источники)."""
    return f'<div class="bl bl-note">{md_to_html(b.get("text", ""))}</div>'

def _blk_pull(b):
    """Крупная цитата вразрядку, как в печатном журнале."""
    tone = f' data-tone="{esc(b["tone"])}"' if b.get("tone") else ""
    return f'<blockquote class="bl bl-pull"{tone}><p>{esc(b.get("text", ""))}</p></blockquote>'

def _shape_attr(b):
    """Цветная фигура-«вырезка» за кадром: shape = alyi|limon|kobalt|fuxia, shapePos = tl|tr|bl|br."""
    if not b.get("shape"):
        return ""
    return f' data-shape="{esc(b["shape"])}" data-shape-pos="{esc(b.get("shapePos", "tr"))}"'

def _blk_daymark(b):
    """Отметка дня/времени в дорожном дневнике."""
    return (f'<div class="bl bl-daymark"><span class="dm-date">{esc(b.get("date", ""))}</span>'
            f'<span class="dm-text">{esc(b.get("text", ""))}</span></div>')

def _blk_route(b):
    """«Билет» на следующие остановки маршрута: город, даты, кто и где."""
    stops = ""
    for i, st in enumerate(b.get("stops") or [], start=int(b.get("startAt", 1))):
        rows = "".join(
            f'<li><b>{esc(it.get("name", ""))}</b><span class="rt-where">{esc(it.get("where", ""))}</span>'
            f'<span class="rt-note">{esc(it.get("note", ""))}</span></li>' for it in st.get("items") or [])
        stops += (f'<section class="rt-stop"><div class="rt-head"><span class="rt-n">{i:02d}</span>'
                  + (f'<h3 class="rt-city"><a href="journal/{esc(st["slug"])}">{esc(st.get("city", ""))} <span class="rt-go">→</span></a></h3>'
                     if st.get("slug") and any(a.get("slug") == st["slug"] for a in articles)
                     else f'<h3 class="rt-city">{esc(st.get("city", ""))}</h3>')
                  + (f'<span class="rt-when">{esc(st["when"])}</span>' if st.get("when") else "") + f'</div><ul>{rows}</ul></section>')
    head = esc(b.get("heading", ""))
    return (f'<div class="bl bl-route bl--wide"><div class="rt-title">{head}</div>'
            f'<div class="rt-stops">{stops}</div></div>')

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
    head_html = (f'<div class="picks-top"><span class="picks-kicker">Можно повесить дома · каталог PRSTNK</span>'
                 f'{f"<div class=picks-head>{heading}</div>" if heading else ""}</div>')
    return f'<div class="bl bl-picks">{head_html}<div class="picks-grid">{cards}</div></div>'

_BLOCK_RENDERERS = {
    "text": _blk_text,
    "heading": _blk_heading,
    "quote": _blk_quote,
    "photo": _blk_photo,
    "split": _blk_split,
    "gallery": _blk_gallery,
    "embed": _blk_embed,
    "picks": _blk_picks,
    "collage": _blk_collage,
    "daymark": _blk_daymark,
    "fullbleed": _blk_fullbleed,
    "pull": _blk_pull,
    "note": _blk_note,
    "route": _blk_route,
}

def render_block(block):
    """Диспетчер блока материала по полю type. Неизвестный тип → пустая строка."""
    fn = _BLOCK_RENDERERS.get(block.get("type", ""))
    return fn(block) if fn else ""


def check_article_slugs(items):
    """Slug материала не должен совпадать с зарезервированными (рубрики, all)."""
    for a in items:
        if a.get("slug") in RESERVED_SLUGS:
            raise ValueError(f'Slug материала "{a.get("slug")}" зарезервирован под рубрику. Переименуйте.')


TRAVEL_JS = """<div class="tr-progress" aria-hidden="true"><span></span></div>
<script>
(function () {
  var still = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var io = "IntersectionObserver" in window;

  // Видеопетли играют, только когда видны; при «меньше движения» — ручной запуск.
  // Видео в одной ленте (как сторис) стартуют и останавливаются вместе.
  var play = function (v) { var p = v.play(); if (p && p.catch) p.catch(function () {}); };
  var handled = [];
  document.querySelectorAll(".bl-collage[data-variant='reel']").forEach(function (reel) {
    var vids = [].slice.call(reel.querySelectorAll(".bl-loop"));
    if (!vids.length) return;
    handled = handled.concat(vids);
    if (still || !io) { vids.forEach(function (v) { v.controls = true; }); return; }
    new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        if (e.isIntersecting) vids.forEach(function (v) { v.currentTime = 0; play(v); });
        else vids.forEach(function (v) { v.pause(); });
      });
    }, { threshold: 0.25 }).observe(reel);
  });
  document.querySelectorAll(".bl-loop").forEach(function (v) {
    if (handled.indexOf(v) >= 0) return;
    if (still || !io) { v.controls = true; return; }
    new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) play(v); else v.pause(); });
    }, { threshold: 0.35 }).observe(v);
  });

  // Полоса прочитанного
  var bar = document.querySelector(".tr-progress span"), art = document.querySelector(".material--travel");
  // Параллакс кадров на всю ширину
  var fbs = still ? [] : [].slice.call(document.querySelectorAll(".fb-frame > *"));
  var ticking = false;
  function onScroll() {
    if (ticking) return; ticking = true;
    requestAnimationFrame(function () {
      ticking = false;
      if (bar && art) {
        var r = art.getBoundingClientRect(), total = r.height - innerHeight;
        bar.style.transform = "scaleX(" + Math.min(1, Math.max(0, -r.top / (total || 1))) + ")";
      }
      fbs.forEach(function (m) {
        var f = m.parentNode.getBoundingClientRect();
        if (f.bottom < 0 || f.top > innerHeight) return;
        var k = (f.top + f.height / 2 - innerHeight / 2) / innerHeight;
        m.style.transform = "translate3d(0," + (k * -8).toFixed(2) + "%,0) scale(1.12)";
      });
    });
  }
  addEventListener("scroll", onScroll, { passive: true }); addEventListener("resize", onScroll); onScroll();

  // Плавное появление кадров: проявление + лёгкое всплытие; только для того, что ниже первого экрана
  if (still || !io) return;
  var els = document.querySelectorAll(".material--travel .bl-photo, .material--travel .bl-collage:not([data-variant='reel']) .cl-item, .material--travel .bl-collage[data-variant='reel'], .material--travel .bl-gallery, .material--travel .bl-split-img, .material--travel .pick");
  var rv = new IntersectionObserver(function (es) {
    es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("is-in"); rv.unobserve(e.target); } });
  }, { rootMargin: "0px 0px -10% 0px" });
  els.forEach(function (el) {
    if (el.getBoundingClientRect().top > innerHeight * 0.9) {
      var sib = el.parentNode.children, n = [].indexOf.call(sib, el);
      el.style.setProperty("--d", (el.classList.contains("cl-item") || el.classList.contains("pick") ? n * 140 : 0) + "ms");
      el.classList.add("rv"); rv.observe(el);
    }
  });
})();
</script>
"""


def render_material_page(article):
    slug = article.get("slug", "")
    canonical = f"{BASE_URL}/journal/{slug}"
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

    travel = article.get("layout") == "travel" and article.get("cover")
    if travel:
        return render_travel_page(article, h1, blocks_html, page_title, desc, canonical, rub)

    body = f'''<article class="material">
  <header class="material-head">
    <a class="material-back material-back--top" href="journal">← В журнал</a>
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

    return (f'{head(page_title, desc, canonical, extra_css="journal.css", base_href="/")}{HEADER}\n'
            f'<div class="jn-wrap">\n{body}\n</div>\n{FOOTER}')


def link_previews(html):
    """Ссылки на другие статьи журнала: подсветка + карточка-превью при наведении (на компьютере)."""
    by_slug = {a.get("slug"): a for a in articles}
    def repl(m):
        a = by_slug.get(m.group(1))
        if not a:
            return m.group(0)
        img = a.get("cover", "")
        lead = strip_tags(a.get("lead", ""))
        lead = lead if len(lead) <= 150 else lead[:147].rsplit(" ", 1)[0] + "…"
        card = (f'<span class="jn-card" aria-hidden="true">'
                + (f'<span class="jn-card-img" style="background-image:url(\'/{esc(img.lstrip("/"))}\')"></span>' if img else "")
                + f'<span class="jn-card-body"><span class="jn-card-rub">{rubric_label(a.get("rubric", ""))}</span>'
                f'<span class="jn-card-title">{esc(strip_tags(a.get("title", "")))}</span>'
                f'<span class="jn-card-lead">{esc(lead)}</span></span></span>')
        return f'<a class="jn-link" href="journal/{m.group(1)}">{m.group(2)}{card}</a>'
    return re.sub(r'<a href="journal/([a-z0-9-]+)">(.*?)</a>', repl, html)


def render_travel_page(article, h1, blocks_html, page_title, desc, canonical, rub):
    """Дорожная статья в журнальной раскладке: огромный заголовок, обложка-коллаж,
    слева «паспорт» материала с жирной вертикальной линией, фото выходят до правого края экрана."""
    # Города маршрута: текущий подсвечен, остальные ведут на свои статьи (если статья есть на сайте)
    live = {a.get("slug") for a in articles}
    def _stop(st):
        city = esc(st.get("city", ""))
        if st.get("here"):
            return f'<li class="is-here"><span aria-current="page">{city}</span></li>'
        if st.get("slug") in live:
            return f'<li><a href="journal/{esc(st["slug"])}">{city}</a></li>'
        return f'<li>{city}</li>'
    route = "".join(_stop(st) for st in article.get("route") or [])
    shape = esc(article.get("coverShape", "limon"))
    # Цвет статьи из палитры Простенка: им же красится столбик логотипа в шапке
    acc = article.get("accent", "alyi")
    acc = acc if acc in ("alyi", "limon", "kobalt", "hvoya", "fuxia", "ugol") else "alyi"
    accent_css = f'<style>:root{{--mz-accent:var(--c-{acc});--prstnk-color:var(--c-{acc})}}</style>'
    mark = ('<svg class="mz-mark" viewBox="0 0 60 80" aria-hidden="true"><rect class="w" x="2" y="2" width="9" height="76"/>'
            '<rect class="p" x="13" y="0" width="34" height="80"/><rect class="w" x="49" y="2" width="9" height="76"/></svg>')
    hero = f'''{accent_css}<header class="mz-hero">
  <div class="mz-hero-top"><a class="mz-back" href="journal">← Журнал ЁPRST</a><span class="mz-rub">{rubric_label(rub)}</span></div>
  <div class="mz-title-row"><h1 class="mz-title">{h1}</h1>{mark}</div>
  <figure class="mz-cover" data-shape="{shape}"><img src="{esc(article["cover"])}"{_wh(article["cover"])}{f' style="object-position:{esc(article["coverPosition"])}"' if article.get("coverPosition") else ""} alt="{esc(article.get("coverAlt", ""))}"/></figure>
</header>'''
    side = f'''<aside class="mz-side"><div class="mz-side-in">
    <div class="mz-issue">{esc(article.get("issueLabel", "Журнал ЁPRST"))}</div>
    <dl class="mz-meta">
      <dt>Текст и фото</dt><dd>{esc(article.get("author", "редакция ЁPRST"))}</dd>
      {f'<dt>Читать</dt><dd>{article["readMins"]} минут</dd>' if article.get("readMins") else ""}
    </dl>
    {f'<ol class="mz-route" aria-label="Маршрут">{route}</ol>' if route else ""}
  </div></aside>'''
    blocks_html = link_previews(blocks_html)
    body = f'''<article class="material material--travel mz">
  <div class="mz-grid">
  {side}
  <p class="mz-lead">{esc(article.get("lead", ""))}</p>
{blocks_html}
  <a class="material-back mz-end" href="materials">← Все материалы</a>
  </div>
</article>'''
    return (f'{head(page_title, desc, canonical, extra_css="journal.css", base_href="/")}{HEADER}\n'
            f'{hero}\n{body}\n{TRAVEL_JS}{FOOTER}')


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

def lenta_own(m):
    """Своя новость сайта (а не пост Telegram): у неё есть своя страница lenta/<slug>."""
    return bool(m.get("slug")) and "t.me/" not in (m.get("url") or "")


def lenta_img(m):
    return (m.get("image") or m.get("photo") or "").strip()


def lenta_card(m):
    date_s = fmt_date_ru(m.get("date", ""))
    url_m = (m.get("url") or "").strip()
    if not url_m and m.get("tgText"):
        url_m = "https://t.me/prstnk_eprst"
    if lenta_own(m):
        href_attr, cta = f'href="lenta/{esc(m["slug"])}"', "Читать →"
    else:
        href_attr = f'href="{esc(url_m)}" target="_blank" rel="noopener"' if url_m else ""
        cta = "Читать в Telegram →" if url_m else ""
    tag_html = f'<span class="lc-tag">{esc(m.get("tag", ""))}</span>' if m.get("tag") else ""
    exc_html = f'<div class="lc-excerpt">{esc(m.get("excerpt", ""))}</div>' if m.get("excerpt") else ""
    img = lenta_img(m)
    img_html = (f'<div class="lc-img"><img src="{esc(img)}"{_wh(img)} loading="lazy" alt=""/></div>' if img
                else f'<div class="lc-img lc-img--plate" style="background:var(--c-{esc(m.get("color") or "alyi")})"></div>')
    return (f'<a class="lc" {href_attr} data-analytics="lenta-card">{img_html}'
            f'<div class="lc-meta"><span class="lc-date">{date_s}</span>{tag_html}</div>'
            f'<div class="lc-title">{esc(m.get("title", ""))}</div>{exc_html}'
            f'<span class="lc-cta">{cta}</span></a>')


def render_lenta_item(m):
    """Страница одной новости: фото, текст, внизу ссылка на источник и ещё новости."""
    slug = m["slug"]
    canonical = f"{BASE_URL}/lenta/{slug}.html"
    title = strip_tags(m.get("title", ""))
    desc = strip_tags(m.get("excerpt", ""))
    img = lenta_img(m)
    credit = m.get("imageCredit", "")
    fig = (f'<figure class="ln-fig"><img src="{esc(img)}"{_wh(img)} alt="{esc(title)}"/>'
           f'{f"<figcaption>{esc(credit)}</figcaption>" if credit else ""}</figure>') if img else ""
    body_md = (m.get("body") or "").strip() or m.get("excerpt", "")
    url_m = (m.get("url") or "").strip()
    src_name = (m.get("sourceName") or re.sub(r"^www\.", "", urllib.parse.urlparse(url_m).netloc)) if url_m else ""
    src_html = (f'<a class="ln-source" href="{esc(url_m)}" target="_blank" rel="noopener">'
                f'<span>Источник</span><b>{esc(src_name)} ↗</b></a>') if url_m else ""
    more = [x for x in lenta if x is not m and lenta_own(x)][:3]
    more_html = (f'<div class="ln-more"><div class="ln-more-head">Ещё в ленте</div>'
                 f'<div class="lenta-grid">{"".join(lenta_card(x) for x in more)}</div></div>') if more else ""
    body = f'''<div class="jn-wrap ln-page">
  <a class="material-back material-back--top" href="lenta">← Вся лента</a>
  <article class="ln-article">
    <div class="ln-meta"><span>{fmt_date_ru(m.get("date", ""))}</span>{f'<span class="lc-tag">{esc(m.get("tag", ""))}</span>' if m.get("tag") else ""}</div>
    <h1 class="ln-h1">{esc(title)}</h1>
    {fig}
    <div class="ln-body">{md_to_html(body_md)}</div>
    {src_html}
  </article>
  {more_html}
</div>'''
    og = f"{BASE_URL}/{img}" if img else None
    return (f'{head(title + " — Лента ЁPRST · PRSTNK", desc, canonical, og_type="article", og_image=og, extra_css="journal.css", base_href="/")}{HEADER}\n'
            f'{body}\n{FOOTER}')


def render_lenta_page():
    canonical = f"{BASE_URL}/lenta.html"
    cards = "\n".join(lenta_card(m) for m in lenta)
    body = f'''<div class="jn-wrap lenta-page">
  <div class="materials-head"><h1>Лента. <em>Новости искусства</em></h1>
    <span class="materials-count">Петербург и мир · между выпусками</span></div>
  <div class="lenta-grid">{cards}</div>
  <a class="material-back" href="journal">← В журнал</a>
</div>'''
    return (f'{head("Лента новостей — Журнал ЁPRST · PRSTNK", "Короткие новости искусства: Петербург, Лондон, Берлин, Милан.", canonical, extra_css="journal.css")}{HEADER}\n'
            f'{body}\n{FOOTER}')


def render_materials_index():
    canonical = f"{BASE_URL}/materials.html"
    title = "Все материалы — Журнал ЁPRST · PRSTNK"
    desc = "Все материалы журнала ЁPRST: разговоры, техники, история, как смотреть графику."
    feed = _feed_rhythm(_materials_sorted())
    count_word = _plural(len(articles), "материал", "материала", "материалов")
    body = f'''<div class="materials-page jn-wrap">
  <div class="materials-head">
    <h1>Все <em>материалы</em></h1>
    <span class="materials-count">— {len(articles)} {count_word}</span>
  </div>
  <div class="materials-feed">
{feed}
  </div>
  <div class="materials-more"><button type="button" disabled>Загрузить ещё</button></div>
</div>'''
    return (f'{head(title, desc, canonical, extra_css="journal.css")}{HEADER}\n'
            f'{body}\n{FOOTER}')


def render_rubric_page(rubric):
    label = rubric_label(rubric)
    color = rubric_color(rubric)
    canonical = f"{BASE_URL}/journal/{rubric}"
    title = f"{label} — Журнал ЁPRST · PRSTNK"
    desc = f"Материалы рубрики «{label}» журнала ЁPRST."
    items = [a for a in _materials_sorted() if a.get("rubric") == rubric]
    feed = _feed_rhythm(items)
    count_word = _plural(len(items), "материал", "материала", "материалов")
    body = f'''<div class="materials-page jn-wrap">
  <div class="materials-head">
    <h1 class="rub-{color}">{label}</h1>
    <span class="materials-count">— {len(items)} {count_word}</span>
  </div>
  <div class="materials-feed">
{feed}
  </div>
  <a class="material-back" href="materials">← Все материалы</a>
</div>'''
    return (f'{head(title, desc, canonical, extra_css="journal.css", base_href="/")}{HEADER}\n'
            f'{body}\n{FOOTER}')


def update_index_home():
    """Обновляет на главной (index.html) блок художников и число «N имён» из данных.
    Меняется только содержимое между HTML-маркерами — остальная вёрстка главной не трогается."""
    path = ROOT / "index.html"
    if not path.exists():
        return False
    html = path.read_text()

    # Блок художников: те, у кого включено «на главной» (с фолбэком на первые 6 видимых)
    home = [a for a in artists if a.get("featured") and a.get("showInArtists", True)]
    if not home:
        home = [a for a in artists if a.get("showInArtists", True)][:6]
    rows = []
    for i, a in enumerate(home, start=1):
        tag = ", ".join(a.get("techniques", [])[:2])
        n = a.get("worksCount", 0)
        cnt = f'{n} {_plural(n, "работа", "работы", "работ")}' if n else "скоро"
        rows.append(
            f'      <a class="artist-row" href="artist-{a["slug"]}.html" data-analytics="artist-row" data-artist-slug="{a["slug"]}">\n'
            f'        <span class="artist-row__num">{i:02d}</span>\n'
            f'        <span class="artist-row__name">{a["name"]}</span>\n'
            f'        <span class="artist-row__tag">{tag}</span>\n'
            f'        <span class="artist-row__count">{cnt}</span>\n'
            f'      </a>')
    rows_block = "<!--AH-ROWS-->\n" + "\n".join(rows) + "\n      <!--/AH-ROWS-->"
    html = re.sub(r"<!--AH-ROWS-->.*?<!--/AH-ROWS-->", lambda m: rows_block, html, flags=re.DOTALL)

    # Заголовок-число «N имён»
    nvis = len([a for a in artists if a.get("showInArtists", True)])
    title_block = (f"<!--AH-TITLE--><em>{num2word_ru(nvis)}</em> "
                   f"{_plural(nvis, 'имя', 'имени', 'имён')}.<!--/AH-TITLE-->")
    html = re.sub(r"<!--AH-TITLE-->.*?<!--/AH-TITLE-->", lambda m: title_block, html, flags=re.DOTALL)

    # Плашки подборок «Готовые подборки»: из data/collections, число листов считается само
    plates = []
    for i, c in enumerate(collections, start=1):
        cn = len([s for s in c.get("works", []) if s in artworks_by_slug])
        if not cn:
            continue
        word = _plural(cn, "лист", "листа", "листов")
        plates.append(
            f'      <a class="plate plate--{c.get("color", "alyi")}" href="collection-{c["slug"]}.html" data-analytics="plate" data-plate-id="{c["slug"]}">\n'
            f'        <span class="plate__num">№ {i:02d} · {cn} {word}</span>\n'
            f'        <span class="plate__title">{c["title"]}</span>\n'
            f'        <span class="plate__meta">{c.get("subtitle", "")}</span>\n'
            f'      </a>')
    # Нет ни одной непустой подборки — прячем весь блок (вернётся сам, когда в подборках появятся работы)
    html = re.sub(r'<section class="wrap" id="plates"( hidden)?>',
                  '<section class="wrap" id="plates">' if plates else '<section class="wrap" id="plates" hidden>', html)
    plates_block = "<!--PLATES-START-->\n" + "\n".join(plates) + "\n      <!--PLATES-END-->"
    html = re.sub(r"<!--PLATES-START-->.*?<!--PLATES-END-->", lambda m: plates_block, html, flags=re.DOTALL)

    # Блок «Кураторская подборка» (6 карточек на главной) — из данных.
    # Берём работы с featuredOnHome: true, отсортированные по order. Если их меньше 6,
    # добиваем оставшимися видимыми (featuredInCatalog) по тому же ключу.
    featured = sorted(
        [a for a in artworks if a.get("featuredOnHome")],
        key=lambda a: a.get("order", 99))
    if len(featured) < 6:
        seen = {a["slug"] for a in featured}
        extras = sorted(
            [a for a in artworks if a.get("featuredInCatalog") and a["slug"] not in seen],
            key=lambda a: a.get("order", 99))
        featured = (featured + extras)[:6]
    else:
        featured = featured[:6]
    home_cards = []
    for i, art in enumerate(featured):
        delay = f"{i * 0.06:.2f}"
        home_cards.append("      " + work_card(art, stagger=True, delay=delay))
    home_block = "<!--HOME-WORKS-->\n" + "\n".join(home_cards) + "\n      <!--/HOME-WORKS-->"
    html = re.sub(r"<!--HOME-WORKS-->.*?<!--/HOME-WORKS-->", lambda m: home_block, html, flags=re.DOTALL)

    # Большая работа в hero — берём первую из featured (та же, что и первая карточка в подборке)
    if featured:
        art = featured[0]
        svg = plate_visual(art)
        aname_short = (art["artistName"].split()[0][0] + ". " + art["artistName"].split()[-1]
                       if len(art["artistName"].split()) >= 2 else art["artistName"])
        ed = ed_label(art)
        size = art["sheetSize"].replace(" см", "").replace(" × ", "×")
        if art["workType"] == "editioned":
            meta_size = f'<b>{size}</b> см · ' + (f'тираж {art["editionTotal"]}' if art.get("editionTotal") else 'тираж')
        else:
            meta_size = f'<b>{size}</b> см · <b>уникальная</b>'
        hero_block = (
            f'<!--HERO-WORK-->\n'
            f'          <div class="hero__art stagger" data-stag-delay="0.12">\n'
            f'            <a class="sheet sheet--hero" href="work-{art["slug"]}.html" '
            f'data-work-color="{art["dominantColor"]}" data-analytics="hero-work">\n'
            f'              <div class="sheet__plate">\n'
            f'                {svg}\n'
            f'              </div>\n'
            f'              <div class="sheet__sig">\n'
            f'                <span>{aname_short}, {art["year"]}</span>\n'
            f'                <span>{ed}</span>\n'
            f'              </div>\n'
            f'            </a>\n'
            f'          </div>\n'
            f'          <div class="hero__meta stagger" data-stag-delay="0.30">\n'
            f'            <span><b>«{art["title"]}»</b> · {art["technique"]}</span>\n'
            f'            <span>{meta_size}</span>\n'
            f'            <span class="price">{art["priceFormatted"]}</span>\n'
            f'          </div>\n'
            f'          <!--/HERO-WORK-->')
        html = re.sub(r"<!--HERO-WORK-->.*?<!--/HERO-WORK-->",
                      lambda m: hero_block, html, flags=re.DOTALL)

    # Анонсы журнала на главной — последние три видимые статьи (скрытые не попадают)
    latest = sorted(articles, key=lambda a: a.get("date", ""), reverse=True)[:3]
    teasers = "".join(
        f'        <article class="journal__article">\n'
        f'          <div class="eyebrow">{RUBRICS.get(a.get("rubric"), {}).get("label", "журнал").lower()}</div>\n'
        f'          <h3><a href="journal/{a["slug"]}.html" style="color: inherit;">{esc(a.get("title", ""))}</a></h3>\n'
        f'        </article>\n' for a in latest)
    html = re.sub(r"<!--JOURNAL-ARTICLES-->.*?<!--/JOURNAL-ARTICLES-->",
                  lambda m: f"<!--JOURNAL-ARTICLES-->\n{teasers}        <!--/JOURNAL-ARTICLES-->", html, flags=re.DOTALL)

    # Текущий выпуск журнала — eyebrow на главной + тикер
    if issues:
        cur = next((i for i in issues if i.get("current")), issues[0])
        n = cur.get("number", "")
        html = re.sub(r"<!--ISSUE-EYEBROW-->.*?<!--/ISSUE-EYEBROW-->",
                      lambda m: f'<!--ISSUE-EYEBROW-->Журнал «<b>ЁPRST</b>» · выпуск {n}<!--/ISSUE-EYEBROW-->',
                      html, flags=re.DOTALL)
        html = re.sub(r"<!--RIBBON-ISSUE-->.*?<!--/RIBBON-ISSUE-->",
                      lambda m: f'<!--RIBBON-ISSUE-->Журнал «ЁPRST» · выпуск {n}<!--/RIBBON-ISSUE-->',
                      html, flags=re.DOTALL)

    path.write_text(clean_links(html))
    return True


def render_collection(coll):
    slug = coll["slug"]
    canonical = f"{BASE_URL}/collection-{slug}.html"
    works = [artworks_by_slug[s] for s in coll.get("works", []) if s in artworks_by_slug]
    n = len(works)
    title = f"{coll['title']} — подборка PRSTNK"
    desc = coll.get("description") or f"Кураторская подборка «{coll['title']}»: {n} оригинальных работ петербургских художников."
    eyebrow = "Подборка" + (f" · {coll['subtitle']}" if coll.get("subtitle") else "")
    if works:
        cards = "\n        ".join(work_card(w) for w in works)
        body_grid = f'<div class="grid-works">\n        {cards}\n      </div>'
    else:
        tg = esc(coll.get("telegramText") or f"Здравствуйте! Расскажите про подборку «{coll['title']}».")
        body_grid = f'''<div class="favorites-empty">
        <h3>Подборка пока собирается.</h3>
        <p>Куратор готовит работы для этой подборки — напишите, подскажем, что уже есть.</p>
        <a class="btn btn--accent" data-tg-text="{tg}" data-analytics="collection-empty">Спросить у куратора →</a>
      </div>'''
    return f'''{head(title, desc, canonical)}{HEADER}
  <main class="wrap">
    <nav class="crumbs" aria-label="Хлебные крошки">
      <a href="index.html">Главная</a><span class="sep">/</span>
      <a href="index.html#plates">Подборки</a><span class="sep">/</span>
      <span class="here">{coll['title']}</span>
    </nav>

    <section class="page-hero" style="padding-bottom: 24px;">
      <div class="eyebrow">{eyebrow}</div>
      <h1>{coll['title']}</h1>
      <p class="page-hero__lead">{coll.get('description', '')}</p>
      <div class="page-hero__stats">
        <div><b>{n}</b>{_plural(n, 'работа', 'работы', 'работ')}</div>
      </div>
    </section>

    <section class="catalog-grid-wrap">
      {body_grid}
    </section>
  </main>

{FOOTER}'''


def render_favorites():
    canonical = f"{BASE_URL}/favorites.html"
    title = "Избранное — PRSTNK"
    desc = "Сохранённые работы — список откладывается в этом браузере."
    return f'''{head(title, desc, canonical)}{HEADER}
  <main class="wrap">
    <nav class="crumbs" aria-label="Хлебные крошки">
      <a href="index.html">Главная</a><span class="sep">/</span>
      <span class="here">Избранное</span>
    </nav>

    <section class="page-hero" style="padding-bottom: 24px;">
      <div class="eyebrow">♥ · <b>Избранное</b></div>
      <h1>Отложено: <em><span id="favCount">0</span></em>.</h1>
      <p class="page-hero__lead">Работы, которые вы сохранили. Список хранится в этом браузере. Когда готовы — откройте работу и оформите заявку или попросите куратора придержать.</p>
    </section>

    <section class="catalog-grid-wrap">
      <div class="grid-works" id="favGrid"></div>
      <div class="favorites-empty" id="favEmpty" hidden>
        <h3>Пока пусто.</h3>
        <p>Нажимайте ♡ на работах в каталоге — они появятся здесь.</p>
        <a class="btn btn--accent" href="works.html">В каталог →</a>
      </div>
    </section>
  </main>

  <script src="works-index.js" defer></script>
{FOOTER}'''


def render_sitemap():
    urls = [
        ("", "1.0", "weekly"),
        ("works.html", "0.9", "weekly"),
        ("artists.html", "0.8", "monthly"),
        ("journal.html", "0.7", "monthly"),
    ]
    for issue in issues:
        if issue_has_page(issue):
            urls.append((f"zine-{iss_slug(issue)}.html", "0.8", "monthly"))
    for a in artists:
        urls.append((f"artist-{a['slug']}.html", "0.7", "monthly"))
    for c in collections:
        urls.append((f"collection-{c['slug']}.html", "0.7", "monthly"))
    for w in artworks:
        urls.append((f"work-{w['slug']}.html", "0.8", "weekly"))
    urls.append(("materials.html", "0.7", "weekly"))
    urls.append(("lenta.html", "0.6", "daily"))
    urls += [(f"lenta/{m['slug']}.html", "0.5", "monthly") for m in lenta if lenta_own(m)]
    for a in articles:
        urls.append((f"journal/{a['slug']}.html", "0.7", "weekly"))
    for rub_slug in RUBRICS:
        urls.append((f"journal/{rub_slug}.html", "0.6", "monthly"))
    body = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for path, prio, freq in urls:
        loc = re.sub(r"\.html$", "", path)  # чистый адрес без .html
        body += f"  <url>\n    <loc>{BASE_URL}/{loc}</loc>\n    <changefreq>{freq}</changefreq>\n    <priority>{prio}</priority>\n  </url>\n"
    body += "</urlset>\n"
    return body


# ─── Сборка ───
if __name__ == "__main__":
    # Убираем страницы работ/художников/статей, которых больше нет в данных или они скрыты
    keep = {f"work-{w['slug']}.html" for w in artworks} | {f"artist-{a['slug']}.html" for a in artists}
    stale = [p for p in list(ROOT.glob("work-*.html")) + list(ROOT.glob("artist-*.html")) if p.name not in keep]
    keep |= {f"zine-{iss_slug(i)}.html" for i in issues if issue_has_page(i)}
    stale += [p for p in ROOT.glob("zine-*.html") if p.name not in keep]
    keep_j = {f"{a['slug']}.html" for a in articles} | {f"{r}.html" for r in RUBRICS}
    stale += [p for p in (ROOT / "journal").glob("*.html") if p.name not in keep_j]
    for p in stale:
        p.unlink()
    if stale:
        print(f"  ✓ удалено старых страниц: {len(stale)} ({', '.join(p.name for p in stale)})")

    n = 0
    for art in artworks:
        (ROOT / f"work-{art['slug']}.html").write_text(clean_links(render_work_page(art)))
        n += 1
    print(f"  ✓ {n} страниц работ (work-*.html)")

    (ROOT / "works.html").write_text(clean_links(render_catalog()))
    print("  ✓ works.html — каталог из данных")

    for idx, a in enumerate(artists, start=1):
        (ROOT / f"artist-{a['slug']}.html").write_text(clean_links(render_artist_page(a, idx)))
    print(f"  ✓ {len(artists)} страниц художников (artist-*.html)")

    (ROOT / "artists.html").write_text(clean_links(render_artists_index()))
    print("  ✓ artists.html — индекс художников")

    for c in collections:
        (ROOT / f"collection-{c['slug']}.html").write_text(clean_links(render_collection(c)))
    print(f"  ✓ {len(collections)} страниц подборок (collection-*.html)")

    cards_index = {w["slug"]: clean_links(work_card(w)) for w in artworks}
    (ROOT / "works-index.js").write_text("window.PRSTNK_WORKS = " + json.dumps(cards_index, ensure_ascii=False) + ";\n")
    (ROOT / "favorites.html").write_text(clean_links(render_favorites()))
    print("  ✓ favorites.html + works-index.js — избранное")

    if update_index_home():
        print("  ✓ index.html — блок художников и счётчик на главной обновлены")

    (ROOT / "journal.html").write_text(clean_links(render_journal_index()))
    print(f"  ✓ journal.html — журнал ({len(issues)} вып., {len(materials)} постов в ленте)")

    check_article_slugs(articles)
    (ROOT / "journal").mkdir(exist_ok=True)
    for a in articles:
        (ROOT / "journal" / f'{a["slug"]}.html').write_text(clean_links(render_material_page(a)))
    print(f"  ✓ {len(articles)} страниц материалов (journal/<slug>.html)")

    (ROOT / "lenta.html").write_text(clean_links(render_lenta_page()))
    (ROOT / "lenta").mkdir(exist_ok=True)
    own = [m for m in lenta if lenta_own(m)]
    keep_l = {f"{m['slug']}.html" for m in own}
    for p_ in (ROOT / "lenta").glob("*.html"):
        if p_.name not in keep_l:
            p_.unlink()
    for m in own:
        (ROOT / "lenta" / f"{m['slug']}.html").write_text(clean_links(render_lenta_item(m)))
    print(f"  ✓ {len(own)} страниц новостей (lenta/*.html)")
    print("  ✓ lenta.html — вся лента")
    (ROOT / "materials.html").write_text(clean_links(render_materials_index()))
    print("  ✓ materials.html — все материалы")

    for rub_slug in RUBRICS:
        (ROOT / "journal" / f"{rub_slug}.html").write_text(clean_links(render_rubric_page(rub_slug)))
    print(f"  ✓ {len(RUBRICS)} страниц рубрик (journal/<rubric>.html)")

    zn = 0
    for issue in issues:
        if issue_materials(issue) and not issue.get("articles"):
            (ROOT / f"zine-{iss_slug(issue)}.html").write_text(clean_links(render_series_issue_page(issue)))
        elif issue_has_page(issue):
            (ROOT / f"zine-{iss_slug(issue)}.html").write_text(clean_links(render_issue_page(issue)))
            zn += 1
    print(f"  ✓ {zn} страниц выпусков (zine-*.html)")

    sitemap = render_sitemap()
    (ROOT / "sitemap.xml").write_text(sitemap)
    print(f"  ✓ sitemap.xml — {sitemap.count('<url>')} URL")

    print(f"\nГотово. {len(artworks)} работ, {len(artists)} художников, "
          f"{len(issues)} выпусков журнала.")
