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
import re
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

artworks = load_collection("artworks")
artists = load_collection("artists")
collections = load_collection("collections")
issues = load_collection("issues")        # выпуски журнала «ЁPRST»
materials = load_collection("materials")  # лента коротких постов


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


def _fmt_price(n):
    try:
        return f"{int(n):,}".replace(",", " ") + " ₽"
    except (ValueError, TypeError):
        return ""


def enrich_artwork(w):
    """Автозаполнение служебных полей, чтобы в админке их можно было не показывать.
    Смысловые поля (название, цена, год…) задаёт человек; всё техническое —
    SEO, текст брони, alt, цена прописью, реквизиты — генерится здесь при сборке."""
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

    # Дефолты-реквизиты (партнёр может переопределить через JSON, но в форме не нужны)
    w.setdefault("imageSize", "")
    w.setdefault("galleryImages", [])
    w.setdefault("collections", [])
    w.setdefault("featuredInCatalog", True)
    w.setdefault("featuredOnHome", False)
    w.setdefault("order", 99)
    if not w.get("dominantColor"):
        w["dominantColor"] = "#FA2A22"
    if not w.get("paper"):
        w["paper"] = "Hahnemühle 300 г/м², фактурная"
    if not w.get("signature"):
        w["signature"] = "карандашом, нижнее поле, справа"
    if not w.get("condition"):
        w["condition"] = "Mint, не оформлено в раму"
    if not w.get("certificate"):
        w["certificate"] = "сертификат подлинности от издательства PRSTNK"

    # Тип-зависимое
    if w.get("workType") == "unique":
        if not w.get("uniquenessNote"):
            w["uniquenessNote"] = "Повторов и допечаток не будет."
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
    ed = (f"{w.get('editionNumber','')}/{w.get('editionTotal','')}"
          if w.get("workType") == "editioned" else "1/1")
    if w.get("workType") == "unique":
        w["telegramReserveText"] = (f"Хочу забронировать уникальную работу «{w.get('title','')}» — "
                                    f"{aname}, {w.get('year','')}. Цена {w['priceFormatted']}.")
    else:
        w["telegramReserveText"] = (f"Хочу забронировать экземпляр №{ed} работы «{w.get('title','')}» — "
                                    f"{aname}, {w.get('year','')}. Цена {w['priceFormatted']}.")
    w["seoTitle"] = f"{aname}. «{w.get('title','')}», {w.get('year','')} — {w.get('technique','')} {ed} — PRSTNK"
    w["seoDescription"] = (f"«{w.get('title','')}» — {w.get('technique','')}, {aname}, {w.get('year','')}, "
                           f"{w.get('sheetSize','')}. Подпись автора, сертификат. {w['priceFormatted']}.")


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
def head(title, description, canonical, og_type="website", extra_meta="", og_image=None):
    img = og_image or f"{BASE_URL}/og-cover.svg"
    return f'''<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
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
        <a href="index.html#gifts">Подарки</a>
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
            Каждый лист подписан и пронумерован автором. В заказе — сертификат подлинности от издательства. Если что-то не так — забираем обратно в течение 14 дней.
          </p>
        </div>
        <div>
          <h4>Магазин</h4>
          <ul>
            <li><a href="works.html">Каталог</a></li>
            <li><a href="index.html#fit">Подбор на стену</a></li>
            <li><a href="index.html#gifts">Подарки</a></li>
            <li><a href="artists.html">Художники</a></li>
            <li><a href="index.html#plates">Готовые подборки</a></li>
          </ul>
        </div>
        <div>
          <h4>Издательство</h4>
          <ul>
            <li><a data-tg-text="Здравствуйте! Расскажите про издательство PRSTNK." data-analytics="footer-about">О проекте</a></li>
            <li><a href="index.html#how">Как купить</a></li>
            <li><a href="journal.html">Журнал «ЁPRST»</a></li>
            <li><a href="index.html#faq">FAQ</a></li>
            <li><a data-tg-text="Здравствуйте! Хочу обсудить сотрудничество с PRSTNK." data-analytics="footer-partnership">Сотрудничество</a></li>
          </ul>
        </div>
        <div>
          <h4>Связь</h4>
          <ul>
            <li><a href="mailto:hello@prstnk.ru" data-analytics="footer-email">hello@prstnk.ru</a></li>
            <li><a href="tel:+78120000000" data-analytics="footer-phone">+7 812 000 00 00</a></li>
            <li>наб. Обводного, 60</li>
            <li>пн–сб 12:00–20:00</li>
          </ul>
        </div>
      </div>
      <div class="footer-bottom">
        <span>© 2019—2026 PRSTNK · сделано в Санкт-Петербурге</span>
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
    и на github.io/prstnk/, и на prstnk.ru), пробелы и спецсимволы экранируются."""
    img = (art.get("mainImage") or "").strip()
    if img:
        from urllib.parse import quote
        img = quote(img.lstrip("/"), safe="/")  # «/images/works/a b.jpg» → «images/works/a%20b.jpg»
        alt = esc(art.get("alt") or art.get("title", ""))
        return (f'<img src="{img}" alt="{alt}" loading="lazy" '
                f'style="width:100%;height:100%;object-fit:cover;display:block;"/>')
    return svg_map.get(art["slug"], "")


def edition_dots(art):
    """Точки тиража: проданные (sold) + текущий (current) + доступные."""
    total = art["editionTotal"]
    num = art["editionNumber"]
    if not total:
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
          <div class="lot__status__note">Повторов и допечаток не будет</div>
        </div>
        <p class="lot__trust-note">Это уникальная авторская работа. Экземпляр существует в одном варианте, повторов и допечаток не будет.</p>'''
    # editioned
    total = art["editionTotal"]
    num = art["editionNumber"]
    avail = art["availableCount"]
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
    aname = art["artistName"]
    initials = aname.split()[0][0] + ". " + aname.split()[-1] if len(aname.split()) >= 2 else aname
    ed = (f'{art["editionNumber"]}/{art["editionTotal"]}'
          if art["workType"] == "editioned" else "1/1")
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
    elif art["availableCount"] == 1:
        badge = '<span class="work__badge work__badge--last">Последний экз.</span>'
    elif art["availableCount"] <= 4:
        badge = f'<span class="work__badge work__badge--last">Осталось {art["availableCount"]}</span>'
    stag = ' stagger' if stagger else ''
    stag_attr = f' data-stag-delay="{delay}"' if delay else ''
    href = f'work-{art["slug"]}.html'
    sub = (f'{art["technique"]} · {art["sheetSize"].replace(" см","").replace(" × ","×")} · тираж <b>{art["editionTotal"]}</b>'
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
            <div class="work__plate">
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
        eyebrow = f'№ {art["editionNumber"]} из {art["editionTotal"]} · {art["technique"]} · {art["year"]}'

    # имя на 2 строки
    parts = a["name"].split(" ", 1)
    author_h1 = f'{parts[0]}<br/>{parts[1]}.' if len(parts) == 2 else f'{a["name"]}.'

    # атрибуты
    attrib_rows = [
        ("Техника", art["technique"]),
        ("Размер листа", art["sheetSize"]),
    ]
    if art.get("imageSize"):
        attrib_rows.append(("Размер изображения", art["imageSize"]))
    attrib_rows.append(("Бумага", art["paper"]))
    if art["workType"] == "editioned":
        ap = art.get("artistProofs") or 0
        ed_str = f'<b>{art["editionTotal"]} экз.</b>' + (f' + {ap} авторских (a.p.)' if ap else '')
        attrib_rows.append(("Тираж", ed_str))
    else:
        attrib_rows.append(("Тираж", "<b>уникальная работа · 1/1</b>"))
    attrib_rows += [
        ("Подпись", art["signature"]),
        ("Состояние", art["condition"]),
        ("Сертификат", art["certificate"]),
    ]
    attrib_html = "\n          ".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in attrib_rows)

    # цена-строка
    if art["status"] == "sold":
        avail_html = '<div class="eyebrow" style="margin-bottom: 4px;">статус</div><div style="font-family: var(--f-mono); font-size: 13px; color: var(--prstnk-color);">продано</div>'
    elif art["status"] == "reserved":
        avail_html = '<div class="eyebrow" style="margin-bottom: 4px;">статус</div><div style="font-family: var(--f-mono); font-size: 13px; color: var(--ink-2);">забронировано</div>'
    elif art["workType"] == "unique":
        avail_html = '<div class="eyebrow" style="margin-bottom: 4px;">в наличии</div><div style="font-family: var(--f-mono); font-size: 13px; color: var(--ink-2);">1 экз. · отправим за 1–2 дня</div>'
    else:
        avail_html = f'<div class="eyebrow" style="margin-bottom: 4px;">в наличии</div><div style="font-family: var(--f-mono); font-size: 13px; color: var(--ink-2);">{art["availableCount"]} экз. · отправим за 1–2 дня</div>'

    # описание (если есть) — иначе нейтральный текст
    desc = art.get("description") or (
        f'«{art["title"]}» — {art["technique"]}, {a["name"]}, {art["year"]}. '
        f'{a["oneLiner"]} Лист отпечатан в мастерской и подписан автором карандашом.')

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
        <h2 class="stagger">Ещё <em>у {a["nameShort"].split(".")[-1].strip()}</em>.</h2>
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
      <div class="lot__stage stagger" data-stag-delay="0">
        <div class="sheet">
          <div class="sheet__plate">
            {svg}
          </div>
          <div class="sheet__sig">
            <span>{art['artistName'].split()[0][0]}. {art['artistName'].split()[-1]}, {art['year']}</span>
            <span>{(str(art['editionNumber'])+'/'+str(art['editionTotal'])) if art['workType']=='editioned' else '1/1'}</span>
          </div>
        </div>
      </div>

      <div class="lot__info stagger" data-stag-delay="0.10">
        <div class="eyebrow">{eyebrow}</div>
        <h1 class="lot__author"><a href="artist-{a['slug']}.html" style="color: inherit;">{author_h1}</a></h1>
        <h2 class="lot__title">«{art['title']}», <span class="lot__year">{art['year']}</span></h2>

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
            <li>Сертификат подлинности от издательства PRSTNK</li>
            <li>Архивный тубус + картон + открытка от куратора</li>
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
    ]
    total = len(artworks)
    avail = sum(1 for w in artworks if w["status"] == "available")
    min_price = min(w["price"] for w in artworks)
    min_price_str = f"{min_price:,}".replace(",", " ")  # 4800 → «4 800»

    # Чипсы техник (выбор один из) + чипсы-переключатели
    tech_chips = ['<button class="catalog-filter__chip is-active" data-group="tech" data-filter="all" data-analytics="catalog-filter">Все техники</button>']
    for gid, label in groups:
        if any(w["techniqueGroup"] == gid for w in artworks):
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
    title = "Каталог авторской графики — PRSTNK"
    desc = f"{total} работ авторской графики петербургских художников: офорт, литография, линогравюра, шелкография, монотипия. Подписано автором, от {min_price_str} ₽."

    return f'''{head(title, desc, canonical)}{HEADER}
  <main class="wrap">
    <nav class="crumbs" aria-label="Хлебные крошки">
      <a href="index.html">Главная</a><span class="sep">/</span>
      <span class="here">Каталог</span>
    </nav>

    <section class="page-hero">
      <div class="eyebrow">№ 04 · <b>Каталог</b></div>
      <h1>Все <em>{total} {"работа" if total==1 else ("работы" if total<5 else "работ")}</em>.<br/>Подписано автором.</h1>
      <p class="page-hero__lead">
        Полный каталог авторской графики PRSTNK: тиражные оттиски и уникальные работы. Каждый лист — оригинал, подписанный автором. В заказе — сертификат подлинности и архивный тубус.
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
          <p class="fit__lead">Покажите фото стены — Илья Кирин подберёт 3–5 листов по размеру, цвету и настроению. Бесплатно.</p>
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
    desc = f"{a['name']} — петербургский художник авторской графики. {', '.join(a['techniques'][:3])}. {one_clean}"
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
    desc = (f"{word_cap} петербургских художников авторской графики: Юрий Штапаков, "
            f"Пётр Швецов, Валерий Гриковский, Станислав Казимов, Нестор Энгельке и другие.")

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
      <h1>{word_cap} <em>{noun}</em>.<br/>От ленинградской школы до Север-7.</h1>
      <p class="page-hero__lead">
        У нас печатают мастера трёх поколений: одни учились у Пахомова и Бакакина в Мухинском, другие выросли на риzо и зине нулевых, третьи дебютировали недавно. Объединяет одно — каждый делает форму сам.
      </p>
      <div class="page-hero__stats">
        <div><b>{nvis}</b>художников</div>
        <div><b>{len(artworks)}</b>работ в каталоге</div>
        <div><b>с&nbsp;2019</b>работаем с авторами</div>
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
          <p class="fit__lead">Напишите что у вас на стене сейчас, какое настроение хотите получить — куратор Илья Кирин подберёт авторов под ваш интерьер.</p>
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
    """Выпуск получает отдельную страницу zine-<slug>.html, если в нём есть статьи."""
    return bool(issue.get("articles"))


def issue_cover_svg(issue):
    """Автообложка выпуска: чистая «печатная» композиция в выбранном цвете."""
    c = PALETTE.get(issue.get("coverColor", "alyi"), "#FA2A22")
    num = issue.get("number", "")
    season = (issue.get("period", "") or "").upper()
    return f'''<svg viewBox="0 0 400 530" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
            <rect width="400" height="530" fill="#F0EEE8"/>
            <rect x="44" y="56" width="206" height="276" fill="{c}"/>
            <g transform="translate(150,150)">
              <rect width="206" height="276" fill="#F8F6F1" stroke="#141413" stroke-width="2"/>
              <rect x="26" y="26" width="154" height="150" fill="{c}" opacity="0.16"/>
              <circle cx="103" cy="101" r="34" fill="{c}"/>
              <rect x="40" y="200" width="126" height="9" fill="#141413"/>
              <rect x="40" y="220" width="84" height="9" fill="#9B9587"/>
            </g>
            <text x="40" y="498" font-family="serif" font-weight="800" font-size="40" fill="#141413" letter-spacing="-2">№ {num}</text>
            <text x="148" y="498" font-family="monospace" font-size="12" fill="#6E6B61" letter-spacing="3">{season}</text>
          </svg>'''


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
    if al.get("slug"):
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


def render_journal_index():
    canonical = f"{BASE_URL}/journal.html"
    title = "Журнал «ЁPRST» — PRSTNK"
    desc = ("Журнал PRSTNK «ЁPRST»: раз в квартал выходит полный выпуск, между выпусками — "
            "короткие материалы в Telegram. Архив выпусков и лента постов.")

    featured = next((i for i in issues if i.get("current") and issue_has_page(i)), None)
    if not featured:
        featured = next((i for i in issues if issue_has_page(i)), None)

    feature_html = ""
    if featured:
        amc = featured.get("materialsCount") or len(featured.get("articles", []))
        note = f'{amc} {_plural(amc, "материал", "материала", "материалов")}' if amc else ""
        if featured.get("readingTime"):
            note = (note + " · " if note else "") + featured["readingTime"]
        feature_html = f'''    <section class="journal-feature">
      <a class="journal-feature__cover" href="zine-{iss_slug(featured)}.html" data-analytics="journal-feature-cover" aria-label="Открыть выпуск {featured['number']}">
          {issue_cover_visual(featured)}
      </a>
      <div class="journal-feature__info">
        <div class="journal-feature__eyebrow">актуальный выпуск · {featured['period']}</div>
        <h2>{featured.get('title', '')}</h2>
        <p class="journal-feature__lead">
          {featured.get('lead', '')}
        </p>
        <div class="journal-feature__cta-row">
          <a class="btn btn--big btn--accent" href="zine-{iss_slug(featured)}.html" data-analytics="journal-feature-cta">
            Открыть выпуск
            {ARROW}
          </a>
          <span class="gifts__note">{note}</span>
        </div>
      </div>
    </section>
'''

    archive = [i for i in issues if i is not featured]
    archive_html = ""
    if archive:
        cards = []
        for it in archive:
            meta = f'№ {it["number"]} · {it["period"]}'
            if it.get("archiveNote"):
                meta += f' · {it["archiveNote"]}'
            amc = it.get("materialsCount") or len(it.get("articles", []))
            if amc:
                meta += f' · {amc} {_plural(amc, "материал", "материала", "материалов")}'
            if issue_has_page(it):
                link = f'href="zine-{iss_slug(it)}.html"'
            elif it.get("tgText"):
                link = f'data-tg-text="{esc(it["tgText"])}"'
            else:
                link = "data-tg-open"
            cards.append(f'''<a class="journal-archive__card" {link} data-analytics="archive-card" data-issue="{it['number']}">
          <div class="journal-archive__cover">
            {issue_cover_svg(it)}
          </div>
          <div class="journal-archive__meta">{meta}</div>
          <h3 class="journal-archive__title">{it.get("title", "")}</h3>
        </a>''')
        total_mat = sum((i2.get("materialsCount") or len(i2.get("articles", []))) for i2 in archive)
        nnum = len(archive)
        head_meta = (f'{nnum} {_plural(nnum, "номер", "номера", "номеров")} · '
                     f'{total_mat} {_plural(total_mat, "материал", "материала", "материалов")}')
        archive_html = f'''    <section class="journal-archive">
      <div class="section-head" style="padding: 0 0 36px;">
        <h2 class="stagger">Архив <em>выпусков</em>.</h2>
        <div class="section-head__right">
          <span>{head_meta}</span>
        </div>
      </div>
      <div class="journal-archive__grid">
        {"".join(chr(10) + "        " + c for c in cards)}
      </div>
    </section>
'''

    feed_html = ""
    if materials:
        fcards = []
        for m in materials:
            color = PALETTE.get(m.get("color", "alyi"), "#FA2A22")
            img = (m.get("image") or "").strip()
            if img:
                from urllib.parse import quote
                img_q = quote(img.lstrip("/"), safe="/")
                cover = (f'<img src="{img_q}" alt="{esc(m.get("title", ""))}" '
                         f'loading="lazy" style="width:100%;height:100%;object-fit:cover;display:block;"/>')
            else:
                cover = f'''<svg viewBox="0 0 400 300" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
              <rect width="400" height="300" fill="#F0EEE8"/>
              <circle cx="120" cy="150" r="74" fill="{color}"/>
              <rect x="190" y="70" width="150" height="160" fill="{color}" opacity="0.55"/>
            </svg>'''
            meta = fmt_date_ru(m.get("date", ""))
            if m.get("tag"):
                meta = (meta + " · " if meta else "") + m["tag"]
            excerpt = f'<p class="feed-card__excerpt">{m["excerpt"]}</p>' if m.get("excerpt") else ""
            url = (m.get("url") or "").strip()
            if url:
                link = f'href="{esc(url)}" target="_blank" rel="noopener"'
            elif m.get("tgText"):
                link = f'data-tg-text="{esc(m["tgText"])}"'
            else:
                link = "data-tg-open"
            fcards.append(f'''<a class="feed-card" {link} data-analytics="feed-card" data-material="{m.get("slug", "")}">
          <div class="feed-card__cover">{cover}</div>
          <div class="feed-card__meta">{meta}</div>
          <h3 class="feed-card__title">{m.get("title", "")}</h3>
          {excerpt}
          <span class="feed-card__cta">Читать в Telegram →</span>
        </a>''')
        feed_html = f'''    <section class="journal-feed">
      <div class="section-head" style="padding: 0 0 36px;">
        <h2 class="stagger">Между выпусками. <em>Лента</em>.</h2>
        <div class="section-head__right">
          <span>Короткие материалы и репортажи</span>
        </div>
      </div>
      <div class="feed-grid">
        {"".join(chr(10) + "        " + c for c in fcards)}
      </div>
    </section>
'''

    return f'''{head(title, desc, canonical)}{HEADER}
  <main class="wrap">
    <nav class="crumbs" aria-label="Хлебные крошки">
      <a href="index.html">Главная</a><span class="sep">/</span>
      <span class="here">Журнал «ЁPRST»</span>
    </nav>

    <section class="page-hero" style="padding-bottom: 32px;">
      <div class="eyebrow">№ 06 · <b>Журнал</b></div>
      <h1>«<em>ЁPRST</em>».<br/>Журнал про авторскую графику.</h1>
      <p class="page-hero__lead">
        Раз в квартал собираем полный выпуск: интервью с художниками, репортажи из мастерских, кураторские разборы. Между выпусками — короткие посты в Telegram. Без снобизма, иногда с матом.
      </p>
    </section>

{feature_html}{archive_html}{feed_html}  </main>

  <section class="journal-telegram">
    <div class="journal-telegram__inner">
      <div class="journal-telegram__text">
        Между выпусками — короткие посты, анонсы тиражей и репортажи из мастерских <em>в Telegram-канале</em>.
      </div>
      <a class="btn btn--big btn--accent"
         data-tg-text="Здравствуйте! Хочу подписаться на канал PRSTNK."
         data-analytics="journal-telegram-cta">
        Подписаться на канал
        {ARROW}
      </a>
    </div>
  </section>

{FOOTER}'''


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
        word = _plural(cn, "лист", "листа", "листов")
        plates.append(
            f'      <a class="plate plate--{c.get("color", "alyi")}" href="collection-{c["slug"]}.html" data-analytics="plate" data-plate-id="{c["slug"]}">\n'
            f'        <span class="plate__num">№ {i:02d} · {cn} {word}</span>\n'
            f'        <span class="plate__title">{c["title"]}</span>\n'
            f'        <span class="plate__meta">{c.get("subtitle", "")}</span>\n'
            f'      </a>')
    plates_block = "<!--PLATES-START-->\n" + "\n".join(plates) + "\n      <!--PLATES-END-->"
    html = re.sub(r"<!--PLATES-START-->.*?<!--PLATES-END-->", lambda m: plates_block, html, flags=re.DOTALL)

    path.write_text(clean_links(html))
    return True


def render_collection(coll):
    slug = coll["slug"]
    canonical = f"{BASE_URL}/collection-{slug}.html"
    works = [artworks_by_slug[s] for s in coll.get("works", []) if s in artworks_by_slug]
    n = len(works)
    title = f"{coll['title']} — подборка PRSTNK"
    desc = coll.get("description") or f"Кураторская подборка «{coll['title']}»: {n} работ авторской графики PRSTNK."
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
    body = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for path, prio, freq in urls:
        loc = re.sub(r"\.html$", "", path)  # чистый адрес без .html
        body += f"  <url>\n    <loc>{BASE_URL}/{loc}</loc>\n    <changefreq>{freq}</changefreq>\n    <priority>{prio}</priority>\n  </url>\n"
    body += "</urlset>\n"
    return body


# ─── Сборка ───
if __name__ == "__main__":
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

    zn = 0
    for issue in issues:
        if issue_has_page(issue):
            (ROOT / f"zine-{iss_slug(issue)}.html").write_text(clean_links(render_issue_page(issue)))
            zn += 1
    print(f"  ✓ {zn} страниц выпусков (zine-*.html)")

    sitemap = render_sitemap()
    (ROOT / "sitemap.xml").write_text(sitemap)
    print(f"  ✓ sitemap.xml — {sitemap.count('<url>')} URL")

    print(f"\nГотово. {len(artworks)} работ, {len(artists)} художников, "
          f"{len(issues)} выпусков журнала.")
