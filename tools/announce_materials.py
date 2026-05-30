"""Анонсит НОВЫЕ материалы сайта в телеграм-канал @prstnk_eprst.

Запуск (в CI): нужен секрет TG_BOT_TOKEN (env). Без токена скрипт ничего
не публикует — только при первом запуске «засевает» список уже вышедших
материалов, чтобы при включении не заспамить канал старыми статьями.

Уже анонсированные слаги хранятся в data/announced.json (чтобы не дублировать).
Безопасен для CI: при любой ошибке не валит сборку.
"""
import json, os, sys, urllib.request, urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "data" / "articles"
STATE = ROOT / "data" / "announced.json"
CHANNEL = "@prstnk_eprst"
SITE = "https://prstnk.ru"


def load_articles():
    out = []
    if ARTICLES_DIR.exists():
        for p in sorted(ARTICLES_DIR.glob("*.json")):
            try:
                out.append(json.loads(p.read_text()))
            except Exception:
                pass
    return out


def load_announced():
    if STATE.exists():
        try:
            return set(json.loads(STATE.read_text()))
        except Exception:
            return set()
    return set()


def save_announced(slugs):
    STATE.write_text(json.dumps(sorted(slugs), ensure_ascii=False, indent=2) + "\n")


def new_materials(articles, announced):
    """Материалы, которых ещё не анонсировали (по slug)."""
    return [a for a in articles
            if a.get("slug") and a.get("slug") not in announced]


def build_message(a):
    """Текст анонса: заголовок + лид + ссылка на материал."""
    title = (a.get("title") or "").strip()
    lead = (a.get("lead") or "").strip()
    url = f"{SITE}/journal/{a.get('slug', '')}"
    parts = [f"📝 {title}"] if title else []
    if lead:
        parts.append(lead)
    parts.append(url)
    return "\n\n".join(parts)


def send(token, text):
    data = urllib.parse.urlencode({
        "chat_id": CHANNEL,
        "text": text,
        "disable_web_page_preview": "false",
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage", data=data)
    with urllib.request.urlopen(req, timeout=20) as r:
        body = json.loads(r.read().decode("utf-8", "replace"))
        return bool(body.get("ok"))


def main():
    token = os.environ.get("TG_BOT_TOKEN", "").strip()
    articles = load_articles()
    announced = load_announced()

    if not token:
        # Токена нет — ничего не публикуем. Но если состояния ещё нет,
        # засеваем текущими материалами (чтобы при включении не заспамить старым).
        if not STATE.exists():
            save_announced({a["slug"] for a in articles if a.get("slug")})
            print("announced.json засеян текущими материалами "
                  "(TG_BOT_TOKEN нет — анонсы не публикуются).")
        else:
            print("TG_BOT_TOKEN не задан — анонсы пропущены.")
        return 0

    fresh = new_materials(articles, announced)
    sent = 0
    for a in fresh:
        try:
            if send(token, build_message(a)):
                announced.add(a["slug"])
                sent += 1
        except Exception as e:
            print(f"::notice::Не удалось заанонсить {a.get('slug')}: {e}")
    save_announced(announced)
    print(f"Анонсировано новых материалов: {sent}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
