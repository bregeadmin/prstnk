"""Тянет посты публичного телеграм-канала в data/lenta_channel.json.
Запуск: python tools/fetch_lenta.py
Безопасен для CI: при любой ошибке выходит без падения и не трогает существующий json."""
import json, re, html, sys, urllib.request
from pathlib import Path

CHANNEL = "prstnk_eprst"
LIMIT = 8
OUT = Path(__file__).resolve().parent.parent / "data" / "lenta_channel.json"
URL = f"https://t.me/s/{CHANNEL}"

def _text(chunk):
    m = re.search(r'tgme_widget_message_text[^>]*>(.*?)</div>', chunk, re.S)
    if not m:
        return ""
    t = re.sub(r'<br\s*/?>', '\n', m.group(1))   # переносы строк сохраняем
    t = re.sub(r'<[^>]+>', '', t)
    return html.unescape(t).strip()

def _clip(s, n):
    s = s.strip()
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"

def _attr(chunk, pattern):
    m = re.search(pattern, chunk, re.S)
    return m.group(1) if m else ""

def parse_channel_html(page_html, limit=LIMIT):
    """Чистая функция: HTML страницы t.me/s/<channel> → список постов (новые первыми)."""
    chunks = re.split(r'tgme_widget_message_wrap', page_html)[1:]
    posts = []
    for ch in chunks:
        url = _attr(ch, r'tgme_widget_message_date"[^>]*href="([^"]+)"')
        if not url:
            continue
        text = _text(ch)
        date = _attr(ch, r'<time[^>]*datetime="([^"]+)"')
        photo = _attr(ch, r'tgme_widget_message_photo_wrap[^>]*style="[^"]*background-image:url\(.([^\')]+)')
        # хэштег → тег/полка (берём первый), затем убираем хэштеги из текста
        tag_m = re.search(r'#([A-Za-zА-Яа-яЁё0-9_]+)', text)
        tag = f'#{tag_m.group(1)}' if tag_m else ""
        clean = re.sub(r'#[A-Za-zА-Яа-яЁё0-9_]+', '', text)
        lines = [ln for ln in (x.strip() for x in clean.split("\n")) if ln]
        title = _clip(lines[0], 90) if lines else ""        # 1-я строка → заголовок
        excerpt = _clip(" ".join(lines[1:]), 180)            # остальное → описание
        posts.append({"title": title, "excerpt": excerpt, "date": date[:10],
                      "url": url, "tag": tag, "photo": photo})
    posts.reverse()  # новые сверху
    return posts[:limit]

def fetch():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (prstnk-build)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")

def main():
    try:
        posts = parse_channel_html(fetch())
    except Exception as e:
        print(f"::notice::Лента: не удалось забрать канал ({e}). Оставляю прежние данные.")
        return 0
    if not posts:
        print("::notice::Лента: канал пуст или не распарсился. Оставляю прежние данные.")
        return 0
    OUT.write_text(json.dumps(posts, ensure_ascii=False, indent=2) + "\n")
    print(f"Лента: записано {len(posts)} постов в {OUT.name}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
