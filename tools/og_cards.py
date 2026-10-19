"""Карточки превью ссылок (Telegram, WhatsApp, VK): images/og/<страница>.jpg, 1200×630.

Запуск после изменений в данных (нужны Chrome и локальный сервер на :8771):
    python3 tools/og_cards.py
build.py сам подхватывает готовые карточки по адресу страницы."""
import json, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build as B  # noqa: E402

TMP = ROOT / "_og_tmp"
SRV = "http://localhost:8771"
esc = B.esc


def src(p):
    from urllib.parse import quote
    return "/" + quote(str(p or "").lstrip("/"), safe="/")

CSS = """@import url('/fonts.css');
:root{--alyi:#FA2A22;--limon:#FFCC00;--kobalt:#2A4BFF;--hvoya:#2E5A2A;--fuxia:#FF3DA0;--ugol:#161614;--cream:#F8F6F1}
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1200px;height:630px;overflow:hidden;background:var(--cream);color:var(--ugol)}
.c{position:relative;width:1200px;height:630px;overflow:hidden;display:flex}
.fd{font-family:"Unbounded","Onest",sans-serif}.ft{font-family:"Onest",sans-serif}.fm{font-family:"JetBrains Mono",monospace;text-transform:uppercase;letter-spacing:.08em}
.bar{position:absolute;left:0;right:0;top:0;height:14px;background:var(--acc)}
.brand{display:flex;align-items:center;gap:14px;font-size:26px;font-weight:800;letter-spacing:-.02em}
.brand svg{width:22px;height:30px}
.brand small{font-family:"JetBrains Mono",monospace;font-weight:400;font-size:15px;letter-spacing:.06em;color:rgba(22,22,20,.55)}
.photo{position:relative;flex:0 0 auto;height:630px;overflow:hidden}
.photo img{width:100%;height:100%;object-fit:cover;display:block}
.panel{flex:1;display:flex;flex-direction:column;justify-content:space-between;padding:58px 56px 44px}
.kick{font-size:16px;color:var(--accd)}
.t{font-weight:800;letter-spacing:-.035em;line-height:.98;text-wrap:balance}
.t em{font-style:italic;color:var(--accd)}
.lead{font-size:22px;line-height:1.35;color:rgba(22,22,20,.72);display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
"""
MARK = ('<svg viewBox="0 0 60 80"><rect x="2" y="2" width="9" height="76" fill="none" stroke="#161614" stroke-width="2.4"/>'
        '<rect x="13" y="0" width="34" height="80" fill="var(--acc)"/><rect x="49" y="2" width="9" height="76" fill="none" stroke="#161614" stroke-width="2.4"/></svg>')
BRAND = f'<div class="brand fd">{MARK}PRSTNK <small>[ простенок ]</small></div>'
DARK = {"limon": "#B38F00", "kobalt": "#2A4BFF", "fuxia": "#E0218A", "alyi": "#E8231B", "hvoya": "#2E5A2A", "ugol": "#161614"}


def page(acc, body):
    return (f'<!doctype html><meta charset="utf-8"><style>{CSS}</style>'
            f'<div class="c" style="--acc:var(--{acc});--accd:{DARK.get(acc, "#E8231B")}">{body}</div>')


def t_photo(img, kicker, title, lead, acc="alyi", width=600, size=58):
    return page(acc, f'''<div class="photo" style="width:{width}px"><img src="{src(img)}"></div>
<div class="bar" style="left:{width}px"></div>
<div class="panel"><div><div class="kick fm">{kicker}</div>
<div class="t fd" style="font-size:{size}px;margin-top:22px">{title}</div></div>
<div><div class="lead ft">{esc(lead)}</div><div style="margin-top:26px">{BRAND}</div></div></div>''')


def t_work(w):
    img = w.get("mainImage", "")
    acc = w.get("color") if w.get("color") in DARK else "alyi"
    kind = "уникальная работа" if w.get("workType") == "unique" else "тираж"
    size = str(w.get("sheetSize", "")).strip()
    if size and not size.endswith("см"):
        size += " см"
    return page(acc, f'''<div class="photo" style="width:560px;background:#E9E5DC;display:flex;align-items:center;justify-content:center;padding:44px">
<img src="{src(img)}" style="width:100%;height:100%;object-fit:contain;filter:drop-shadow(0 18px 26px rgba(20,20,19,.28))"></div>
<div class="bar" style="left:560px"></div>
<div class="panel"><div><div class="kick fm">{esc(w.get("artistName", ""))} · {esc(str(w.get("year", "")))}</div>
<div class="t fd" style="font-size:{56 if len(w.get("title", "")) < 22 else 42}px;margin-top:22px">{esc(w.get("title", ""))}</div>
<div class="ft" style="font-size:21px;line-height:1.35;color:rgba(22,22,20,.7);margin-top:18px">{esc(str(w.get("technique", "")).strip().rstrip("."))}{", " + esc(size) if size else ""}</div></div>
<div><div style="display:flex;align-items:baseline;gap:16px;flex-wrap:wrap"><span class="fd" style="font-size:40px;font-weight:800;letter-spacing:-.02em;white-space:nowrap">{esc(w.get("priceFormatted", ""))}</span>
<span class="fm" style="font-size:14px;color:rgba(22,22,20,.55);white-space:nowrap">оригинал · {kind}</span></div>
<div style="margin-top:22px">{BRAND}</div></div></div>''')


def t_brand(title, sub, imgs, acc="alyi", kicker=""):
    tiles = "".join(f'<div style="flex:1;overflow:hidden;border-radius:6px;background:#E9E5DC"><img src="{src(i)}" style="width:100%;height:100%;object-fit:cover;display:block"></div>' for i in imgs[:3])
    return page(acc, f'''<div class="bar"></div>
<div class="panel" style="flex:0 0 640px;padding-top:66px"><div>{f'<div class="kick fm">{kicker}</div>' if kicker else ""}
<div class="t fd" style="font-size:64px;margin-top:20px">{title}</div>
<div class="lead ft" style="margin-top:24px">{esc(sub)}</div></div><div>{BRAND}</div></div>
<div style="flex:1;display:flex;flex-direction:column;gap:12px;padding:48px 48px 40px 0">{tiles}</div>''')


def t_issue(issue, arts):
    cover = issue.get("coverImage", "")
    cities = "".join(f'<div class="fd" style="font-size:34px;font-weight:800;letter-spacing:-.03em;color:{DARK.get(a.get("accent"), "#161614")}">{esc(B.strip_tags(a.get("title", "")).split(":")[0])}</div>' for a in arts)
    return page("alyi", f'''<div class="photo" style="width:473px"><img src="{src(cover)}"></div><div class="bar" style="left:473px"></div>
<div class="panel"><div><div class="kick fm">Журнал ЁPRST · выпуск № {esc(issue.get("number", ""))} · {esc(issue.get("period", ""))}</div>
<div class="t fd" style="font-size:60px;margin-top:22px">{issue.get("title", "")}</div>
<div style="display:flex;gap:28px;margin-top:30px">{cities}</div></div><div>{BRAND}</div></div>''')


def title_em(a):
    h = esc(a.get("title", ""))
    em = a.get("titleEm", "")
    return h.replace(esc(em), f"<em>{esc(em)}</em>", 1) if em else h


def cards():
    works_img = [w.get("mainImage") for w in B.artworks if w.get("mainImage")]
    out = {}
    feat = [w for w in B.artworks if w.get("mainImage")][:3]
    out["index"] = t_brand("Большое искусство на <em>маленькой</em> стене.", "Только оригиналы петербургских художников: живопись, графика, авторская печать и объекты.", [w["mainImage"] for w in feat], kicker="Оригиналы · Санкт-Петербург")
    out["works"] = t_brand("Каталог <em>оригиналов</em>.", f"{len(B.artworks)} работ петербургских художников: уникальные работы и небольшие тиражи. Каждую подписывает автор.", works_img[3:6], kicker="Каталог PRSTNK")
    out["artists"] = t_brand("Художники <em>Простенка</em>.", ", ".join(a["name"] for a in B.artists) + ".", works_img[6:9], kicker="Художники")
    out["favorites"] = t_brand("Избранное.", "Работы, которые вы отложили.", works_img[:3])
    for a in B.artists:
        ws = [w["mainImage"] for w in B.artworks if w.get("artistId") == a.get("id") and w.get("mainImage")]
        out[f"artist-{a['slug']}"] = t_brand(esc(a["name"]) + ".", B.re.sub(r"<[^>]+>", "", a.get("oneLiner", "")), ws, kicker="Художник PRSTNK")
    for w in B.artworks:
        if w.get("mainImage"):
            out[f"work-{w['slug']}"] = t_work(w)
    for c in getattr(B, "collections", []):
        ws = [w["mainImage"] for w in B.artworks if w.get("id") in (c.get("works") or []) or w.get("slug") in (c.get("works") or [])]
        if ws:
            out[f"collection-{c['slug']}"] = t_brand(esc(c.get("title", "")), c.get("description", ""), ws, kicker="Подборка PRSTNK")
    for a in B.articles:
        if a.get("cover"):
            out[f"journal_{a['slug']}"] = t_photo(a["cover"], "Журнал ЁPRST · " + esc(a.get("issueLabel", "").replace("ЁPRST · ", "") or B.rubric_label(a.get("rubric", ""))), title_em(a), a.get("lead", ""), a.get("accent", "alyi"))
    cur = next((i for i in B.issues if i.get("current")), None)
    if cur and cur.get("coverImage"):
        arts = B.issue_materials(cur)
        out[f"zine-{B.iss_slug(cur)}"] = t_issue(cur, arts)
        jtitle = "Журнал <em>ЁPRST</em>."
        out["journal"] = t_issue(cur, arts).replace(cur.get("title", ""), cur.get("title", ""))
        out["materials"] = out["journal"]
        for r in B.RUBRICS:
            out[f"journal_{r}"] = out["journal"]
    for m in B.lenta:
        if B.lenta_own(m) and B.lenta_img(m):
            out[f"lenta_{m['slug']}"] = t_photo(B.lenta_img(m), "Лента ЁPRST · " + esc(m.get("tag", "")), esc(m.get("title", "")), m.get("excerpt", ""), "alyi", size=50)
    own = [m for m in B.lenta if B.lenta_own(m) and B.lenta_img(m)]
    if own:
        out["lenta"] = t_brand("Лента. <em>Новости искусства</em>.", "Петербург, Лондон, Берлин, Милан: короткие новости между выпусками журнала.", [B.lenta_img(m) for m in own[:3]], kicker="Журнал ЁPRST")
    return out


if __name__ == "__main__":
    only = set(sys.argv[1:])
    shutil.rmtree(TMP, ignore_errors=True); TMP.mkdir()
    jobs = []
    for key, html in cards().items():
        if only and key not in only:
            continue
        (TMP / f"{key}.html").write_text(html)
        jobs.append({"url": f"{SRV}/_og_tmp/{key}.html", "out": str(ROOT / "images" / "og" / f"{key}.jpg")})
    (TMP / "jobs.json").write_text(json.dumps(jobs))
    subprocess.run(["node", str(ROOT / "tools" / "og-render.mjs"), str(TMP / "jobs.json")], check=True)
    shutil.rmtree(TMP, ignore_errors=True)
