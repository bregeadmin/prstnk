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
BASE_URL = "https://bregeadmin.github.io/prstnk"

def load_collection(name):
    """Читает все JSON из data/<name>/ и сортирует по полю order."""
    folder = ROOT / "data" / name
    items = [json.loads(p.read_text()) for p in folder.glob("*.json")]
    return sorted(items, key=lambda x: x.get("order", 0))

artworks = load_collection("artworks")
artists = load_collection("artists")
collections = load_collection("collections")

artists_by_id = {a["id"]: a for a in artists}
artworks_by_slug = {w["slug"]: w for w in artworks}

# Нормализация: имя/slug художника всегда берём из artistId (единый источник).
# Так в CMS достаточно выбрать художника — имя подставится при сборке.
for _w in artworks:
    _a = artists_by_id.get(_w.get("artistId"))
    if _a:
        _w["artistName"] = _a["name"]
        _w["artistSlug"] = _a["slug"]

# Пересчёт привязки работ к художникам (workSlugs / worksCount) из актуальных данных
for _a in artists:
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
            <li><a href="journal.html">Журнал «Во дела»</a></li>
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


def plate_visual(art):
    """Визуал работы: реальное фото (если загружено) или SVG-заглушка."""
    img = (art.get("mainImage") or "").strip()
    if img:
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
    """CTA в зависимости от статуса и типа."""
    status = art["status"]
    tg = esc(art["telegramReserveText"])
    if status == "sold":
        return f'''        <div class="lot__cta">
          <a class="btn btn--big btn--ghost" data-tg-text="Здравствуйте! Работа «{esc(art['title'])}» продана. Подскажите, появится ли что-то похожее у {esc(art['artistName'])}?" data-analytics="lot-sold-ask" data-lot-slug="{art['slug']}">Работа продана · спросить о похожей</a>
        </div>'''
    cta_label = "Забронировать работу" if art["workType"] == "unique" else "Забронировать экземпляр"
    if status == "reserved":
        cta_label = "Уже забронирована · встать в лист ожидания"
        tg = f"Здравствуйте! Работа «{esc(art['title'])}» — {esc(art['artistName'])} забронирована. Хочу встать в лист ожидания, если бронь снимется."
    return f'''        <div class="lot__cta">
          <a class="btn btn--big btn--accent" data-tg-text="{tg}" data-analytics="lot-reserve" data-lot-slug="{art['slug']}" data-work-type="{art['workType']}">
            {cta_label}
            <svg width="18" height="14" viewBox="0 0 18 14" fill="none" aria-hidden="true"><path d="M1 7H17M17 7L11 1M17 7L11 13" stroke="currentColor" stroke-width="2"/></svg>
          </a>
          <button class="btn btn--big btn--ghost" aria-label="Сохранить в избранное" data-analytics="lot-wishlist" data-lot-slug="{art['slug']}">♡</button>
        </div>
        <div class="lot__cta-extra">
          <a class="btn btn--ghost" data-tg-text="Здравствуйте! Хочу подобрать раму для «{esc(art['title'])}» — {esc(art['artistName'])}, {art['year']}, {esc(art['sheetSize'])}." data-analytics="lot-frame" data-lot-slug="{art['slug']}">Подобрать раму</a>
          <a class="btn btn--ghost" data-tg-text="Здравствуйте! Есть вопрос по «{esc(art['title'])}» — {esc(art['artistName'])}, {art['year']}." data-analytics="lot-curator-question" data-lot-slug="{art['slug']}">Задать вопрос куратору</a>
        </div>'''


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
    return f'''<a class="{cls}{stag}" href="{href}" data-work-color="{art['dominantColor']}"{stag_attr} data-analytics="work-card" data-work-slug="{art['slug']}">
          {badge}
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
    # группировка
    groups = [
        ("lithography", "Литография", "камень · вода · масло"),
        ("silkscreen", "Шелкография", "шёлк · краска · экран"),
        ("linocut", "Линогравюра и ксилография", "резец · линолеум · топор"),
        ("etching", "Офорт", "цинк · кислота · игла"),
        ("graphics", "Графика и монотипия", "рисунок · валик · стекло"),
    ]
    filter_labels = {
        "lithography": "Литография", "silkscreen": "Шелкография",
        "linocut": "Линогравюра", "etching": "Офорт", "graphics": "Графика и монотипия",
    }
    total = len(artworks)
    avail = sum(1 for w in artworks if w["status"] == "available")
    min_price = min(w["price"] for w in artworks)
    min_price_str = f"{min_price:,}".replace(",", " ")  # 4800 → «4 800»

    chips = ['<button class="catalog-filter__chip is-active" data-filter="all" data-analytics="catalog-filter" data-filter-id="all">Все техники</button>']
    for gid, label in [(g[0], filter_labels[g[0]]) for g in groups]:
        chips.append(f'<button class="catalog-filter__chip" data-filter="{gid}" data-analytics="catalog-filter" data-filter-id="{gid}">{label}</button>')

    sections = []
    for gid, gname, gmeta in groups:
        items = [w for w in artworks if w["techniqueGroup"] == gid]
        if not items:
            continue
        n = len(items)
        word = "лист" if n == 1 else ("листа" if n < 5 else "листов")
        cards = "\n        ".join(work_card(w) for w in items)
        sections.append(f'''    <section class="catalog-section" data-technique="{gid}">
      <div class="catalog-section__head">
        <h2>{gname}. <em>{n} {word}</em>.</h2>
        <span class="meta">{gmeta}</span>
      </div>
      <div class="grid-works">
        {cards}
      </div>
    </section>''')

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

    <div class="catalog-filter" role="tablist" aria-label="Фильтр по технике">
      {"".join(chr(10)+"      "+c for c in chips)}
    </div>

{chr(10).join(sections)}

    <section class="fit-block" style="padding: 56px 0;">
      <div class="fit__grid">
        <div class="fit__left">
          <div class="eyebrow">Не нашли своё?</div>
          <h2 style="font-size: clamp(32px, 4.4vw, 56px); margin-top: 16px;">Куратор подберёт <em>под стену</em>.</h2>
          <p class="fit__lead">Покажите фото стены — Илья Кирин подберёт 3–5 листов по размеру, цвету и настроению. Бесплатно.</p>
          <a class="btn btn--big btn--accent fit__cta" data-tg-text="Здравствуйте! Хочу подбор работы по фото стены." data-analytics="catalog-fit">
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

    meta_dl = "\n          ".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in a.get("meta", {}).items())
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
    title = "Художники PRSTNK — двенадцать имён ленинградской школы"
    desc = "Двенадцать петербургских художников авторской графики: Юрий Штапаков, Пётр Швецов, Валерий Гриковский, Станислав Казимов, Нестор Энгельке и другие."

    cards = []
    for idx, a in enumerate(artists, start=1):
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
      <h1>Двенадцать <em>имён</em>.<br/>От ленинградской школы до Север-7.</h1>
      <p class="page-hero__lead">
        У нас печатают мастера трёх поколений: одни учились у Пахомова и Бакакина в Мухинском, другие выросли на риzо и зине нулевых, третьи дебютировали недавно. Объединяет одно — каждый делает форму сам.
      </p>
      <div class="page-hero__stats">
        <div><b>{len(artists)}</b>художников</div>
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


def render_sitemap():
    urls = [
        ("", "1.0", "weekly"),
        ("works.html", "0.9", "weekly"),
        ("artists.html", "0.8", "monthly"),
        ("journal.html", "0.7", "monthly"),
        ("zine-04.html", "0.8", "monthly"),
    ]
    for a in artists:
        urls.append((f"artist-{a['slug']}.html", "0.7", "monthly"))
    for w in artworks:
        urls.append((f"work-{w['slug']}.html", "0.8", "weekly"))
    body = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for path, prio, freq in urls:
        body += f"  <url>\n    <loc>{BASE_URL}/{path}</loc>\n    <changefreq>{freq}</changefreq>\n    <priority>{prio}</priority>\n  </url>\n"
    body += "</urlset>\n"
    return body


# ─── Сборка ───
if __name__ == "__main__":
    n = 0
    for art in artworks:
        (ROOT / f"work-{art['slug']}.html").write_text(render_work_page(art))
        n += 1
    print(f"  ✓ {n} страниц работ (work-*.html)")

    (ROOT / "works.html").write_text(render_catalog())
    print("  ✓ works.html — каталог из данных")

    for idx, a in enumerate(artists, start=1):
        (ROOT / f"artist-{a['slug']}.html").write_text(render_artist_page(a, idx))
    print(f"  ✓ {len(artists)} страниц художников (artist-*.html)")

    (ROOT / "artists.html").write_text(render_artists_index())
    print("  ✓ artists.html — индекс художников")

    (ROOT / "sitemap.xml").write_text(render_sitemap())
    print(f"  ✓ sitemap.xml — {5 + len(artists) + len(artworks)} URL")

    print(f"\nГотово. {len(artworks)} работ, {len(artists)} художников.")
