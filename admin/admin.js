/* ============================================================
   PRSTNK — своя админка.
   • Разделы и поля читаются из config.yml (тот же, что у старой Sveltia).
   • Вход — через GitHub (тот же «пропускной пункт» на Cloudflare).
   • Данные — JSON в репозитории; сохранение = коммит, сайт пересобирается
     GitHub Action'ом. Статус сборки виден в шапке.
   ============================================================ */
(function () {
  "use strict";

  const API = "https://api.github.com";
  const TOKEN_KEY = "prstnk-admin.token";
  const qs = new URLSearchParams(location.search);

  const S = {
    cfg: null, repo: "", branch: "main",
    token: null, user: null,
    data: {},            // name -> [{file, path, sha, data}]
    media: {},           // value-путь -> {path, b64, url}  (фото, ещё не сохранённые)
    build: null, lastSaveAt: 0,
    dirty: false, ctx: null,
  };

  /* ── Мелочи ──────────────────────────────────── */
  const $ = (s, r = document) => r.querySelector(s);
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "html") el.innerHTML = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else if (k === "value") el.value = v;
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat(Infinity)) {
      if (kid == null || kid === false) continue;
      el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    }
    return el;
  }
  const ICONS = {
    works: '<rect x="4" y="3" width="16" height="18" rx="1"/><path d="M4 15l4-4 4 4 3-3 5 5"/><circle cx="15" cy="8" r="1.5"/>',
    artists: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/>',
    collections: '<rect x="3" y="7" width="13" height="14" rx="1"/><path d="M8 7V4h13v13h-5"/>',
    issues: '<path d="M4 4h7a3 3 0 0 1 3 3v13a2 2 0 0 0-2-2H4z"/><path d="M20 4h-4a3 3 0 0 0-3 3"/><path d="M20 4v14h-6"/>',
    articles: '<path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
    materials: '<path d="M5 19a2 2 0 1 1 0-4 2 2 0 0 1 0 4zM4 4a16 16 0 0 1 16 16M4 10a10 10 0 0 1 10 10"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
    chev: '<path d="M9 6l6 6-6 6"/>',
    up: '<path d="M6 15l6-6 6 6"/>',
    down: '<path d="M6 9l6 6 6-6"/>',
    trash: '<path d="M4 7h16M10 11v6M14 11v6M5 7l1 13a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1l1-13M9 7V4h6v3"/>',
    x: '<path d="M6 6l12 12M18 6L6 18"/>',
    ext: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    out: '<path d="M15 4h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4M10 16l-4-4 4-4M6 12h10"/>',
    check: '<path d="M5 12l5 5L20 7"/>',
    alert: '<circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16h.01"/>',
    upload: '<path d="M12 16V4M7 9l5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/>',
    back: '<path d="M15 6l-6 6 6 6"/>',
    gh: '<path d="M9 19c-4.3 1.4-4.3-2.5-6-3m12 5v-3.5c0-1 .1-1.4-.5-2 2.8-.3 5.5-1.4 5.5-6a4.6 4.6 0 0 0-1.3-3.2 4.2 4.2 0 0 0-.1-3.2s-1.1-.3-3.5 1.3a12.3 12.3 0 0 0-6.2 0C6.5 2.8 5.4 3.1 5.4 3.1a4.2 4.2 0 0 0-.1 3.2A4.6 4.6 0 0 0 4 9.5c0 4.6 2.7 5.7 5.5 6-.6.6-.6 1.2-.5 2V21"/>',
  };
  const icon = (n, cls = "") => {
    const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("class", "i " + cls); s.setAttribute("aria-hidden", "true");
    s.innerHTML = ICONS[n] || ""; return s;
  };
  const NAV_ICON = { artworks: "works", artists: "artists", collections: "collections", issues: "issues", articles: "articles", materials: "materials" };

  const noEmoji = (s) => String(s || "").replace(/\p{Extended_Pictographic}️?\s*/gu, "").trim();
  const stripTags = (s) => String(s == null ? "" : s).replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();
  const clone = (o) => JSON.parse(JSON.stringify(o === undefined ? null : o));
  const fmtPrice = (n) => (n || n === 0) ? Number(n).toLocaleString("ru-RU").replace(/,/g, " ") + " ₽" : "—";
  const PALETTE = { alyi: ["Алый", "#FA2A22"], limon: ["Лимон", "#FFCC00"], kobalt: ["Кобальт", "#2A4BFF"], hvoya: ["Хвоя", "#2E5A2A"], fuxia: ["Фуксия", "#FF3DA0"], ugol: ["Уголь", "#161614"] };
  const STATUS = { available: "В наличии", reserved: "Бронь", sold: "Продана" };
  const STATUS_CHIP = { available: "В наличии", reserved: "Бронь", sold: "Продано" };
  // Как называть запись: «Добавить …» и заголовок новой
  const NOUN = {
    artworks: ["работу", "Новая работа"], artists: ["художника", "Новый художник"], collections: ["подборку", "Новая подборка"],
    issues: ["выпуск", "Новый выпуск"], articles: ["материал", "Новый материал"], materials: ["пост", "Новый пост"],
  };

  const TR = { а:"a",б:"b",в:"v",г:"g",д:"d",е:"e",ё:"e",ж:"zh",з:"z",и:"i",й:"i",к:"k",л:"l",м:"m",н:"n",о:"o",п:"p",р:"r",с:"s",т:"t",у:"u",ф:"f",х:"h",ц:"ts",ч:"ch",ш:"sh",щ:"shch",ъ:"",ы:"y",ь:"",э:"e",ю:"iu",я:"ia" };
  const slugify = (s) => String(s || "").toLowerCase().split("").map((c) => (c in TR ? TR[c] : c)).join("")
    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 80);

  function ago(iso) {
    const m = Math.round((Date.now() - new Date(iso)) / 60000);
    if (m < 1) return "только что";
    if (m < 60) return m + " мин назад";
    if (m < 60 * 24) return Math.round(m / 60) + " ч назад";
    return new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "long" });
  }

  // UTF-8 строка/байты <-> base64
  function bytesToB64(bytes) {
    let bin = ""; const CH = 0x8000;
    for (let i = 0; i < bytes.length; i += CH) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + CH));
    return btoa(bin);
  }
  const strToB64 = (s) => bytesToB64(new TextEncoder().encode(s));

  /* ── Тосты и модалки ─────────────────────────── */
  function toast(msg, bad) {
    const t = h("div", { class: "toast" + (bad ? " toast--bad" : "") }, icon(bad ? "alert" : "check"), h("div", {}, msg));
    $("#toasts").append(t);
    setTimeout(() => t.remove(), bad ? 7000 : 4000);
  }
  function modal({ title, text, ok = "Да", cancel = "Отмена", danger, noCancel }) {
    return new Promise((res) => {
      const close = (v) => { m.remove(); document.removeEventListener("keydown", onKey); res(v); };
      const onKey = (e) => { if (e.key === "Escape") close(false); };
      const okBtn = h("button", { class: "btn " + (danger ? "btn--accent" : "btn--primary"), onclick: () => close(true) }, ok);
      const m = h("div", { class: "modal", role: "dialog", "aria-modal": "true", onclick: (e) => { if (e.target === m) close(false); } },
        h("div", { class: "modal__card" }, h("h2", {}, title), text ? h("p", {}, text) : null,
          h("div", { class: "modal__btns" }, noCancel ? null : h("button", { class: "btn btn--ghost", onclick: () => close(false) }, cancel), okBtn)));
      document.body.append(m); document.addEventListener("keydown", onKey); okBtn.focus();
    });
  }
  let loading = 0;
  function busy(on) {
    loading += on ? 1 : -1;
    let bar = $(".loadbar");
    if (loading > 0 && !bar) document.body.append(h("div", { class: "loadbar" }));
    if (loading <= 0 && bar) bar.remove();
  }

  /* ── GitHub ──────────────────────────────────── */
  async function gh(path, opts = {}) {
    const r = await fetch(path.startsWith("http") ? path : API + path, {
      ...opts,
      headers: { Authorization: "Bearer " + S.token, Accept: "application/vnd.github+json", ...(opts.body ? { "Content-Type": "application/json" } : {}) },
      body: opts.body ? JSON.stringify(opts.body) : undefined,
      cache: "no-store",
    });
    if (r.status === 401) { logout("Сессия истекла — войдите ещё раз."); throw new Error("401"); }
    if (!r.ok) {
      let msg = r.status + ""; try { msg = (await r.json()).message || msg; } catch (e) {}
      const err = new Error(msg); err.status = r.status; throw err;
    }
    return r.status === 204 ? null : r.json();
  }
  const encPath = (p) => p.split("/").map(encodeURIComponent).join("/");

  async function loadAll() {
    const [owner, name] = S.repo.split("/");
    const cols = S.cfg.collections.filter((c) => c.folder);
    const parts = cols.map((c, i) => `c${i}: object(expression: ${JSON.stringify(S.branch + ":" + c.folder)}) { ... on Tree { entries { name type object { ... on Blob { oid text } } } } }`);
    const q = `query { repository(owner: ${JSON.stringify(owner)}, name: ${JSON.stringify(name)}) { ${parts.join("\n")} } }`;
    const r = await gh("/graphql", { method: "POST", body: { query: q } });
    if (r.errors) throw new Error(r.errors[0].message);
    cols.forEach((c, i) => {
      const ext = "." + (c.extension || "json");
      const entries = ((r.data.repository["c" + i] || {}).entries || []).filter((e) => e.type === "blob" && e.name.endsWith(ext));
      S.data[c.name] = entries.map((e) => {
        let data = {}; try { data = JSON.parse(e.object.text || "{}"); } catch (err) { data = { __broken: true }; }
        return { file: e.name, path: c.folder + "/" + e.name, sha: e.object.oid, data };
      });
    });
  }

  // Один коммит: несколько файлов (JSON + фото) и/или удаления.
  async function commit(files, deletions, message) {
    const R = `/repos/${S.repo}`;
    const blobs = [];
    for (const f of files) {
      const b = await gh(`${R}/git/blobs`, { method: "POST", body: { content: f.b64, encoding: "base64" } });
      blobs.push({ path: f.path, mode: "100644", type: "blob", sha: b.sha });
    }
    for (let attempt = 0; attempt < 4; attempt++) {
      const ref = await gh(`${R}/git/ref/heads/${S.branch}`);
      const head = await gh(`${R}/git/commits/${ref.object.sha}`);
      const tree = await gh(`${R}/git/trees`, { method: "POST", body: { base_tree: head.tree.sha, tree: [...blobs, ...deletions.map((p) => ({ path: p, mode: "100644", type: "blob", sha: null }))] } });
      const c = await gh(`${R}/git/commits`, { method: "POST", body: { message, tree: tree.sha, parents: [ref.object.sha] } });
      try {
        await gh(`${R}/git/refs/heads/${S.branch}`, { method: "PATCH", body: { sha: c.sha } });
        return Object.fromEntries(blobs.map((b) => [b.path, b.sha]));
      } catch (e) {
        if (e.status !== 422) throw e; // кто-то закоммитил параллельно — пробуем ещё раз поверх
      }
    }
    throw new Error("GitHub занят, попробуйте ещё раз через минуту");
  }

  async function remoteSha(path) {
    try { return (await gh(`/repos/${S.repo}/contents/${encPath(path)}?ref=${S.branch}`)).sha; }
    catch (e) { if (e.status === 404) return null; throw e; }
  }

  /* ── Статус сборки сайта ─────────────────────── */
  let buildTimer = null;
  async function pollBuild() {
    clearTimeout(buildTimer);
    try {
      const r = await gh(`/repos/${S.repo}/actions/workflows/build.yml/runs?branch=${S.branch}&per_page=1`);
      S.build = (r.workflow_runs || [])[0] || null;
      renderBuild();
    } catch (e) { /* статус — не критично */ }
    const running = S.build && S.build.status !== "completed";
    const recent = Date.now() - S.lastSaveAt < 4 * 60000;
    buildTimer = setTimeout(pollBuild, running || recent ? 10000 : 60000);
  }
  function buildEl() {
    const b = S.build;
    if (!b) return h("div", { class: "build" }, h("i", { class: "build__dot" }), h("div", {}, h("b", {}, "Статус сайта"), h("span", {}, "проверяем…")));
    let cls = "build--ok", title = "Сайт обновлён", sub = ago(b.updated_at);
    if (b.status !== "completed") { cls = "build--run"; title = "Сайт обновляется"; sub = "обычно 1–2 минуты"; }
    else if (b.conclusion !== "success") { cls = "build--bad"; title = "Сборка упала"; sub = "правки не попадают на сайт — нажмите, чтобы посмотреть"; }
    return h("a", { class: "build " + cls, href: b.html_url, target: "_blank", rel: "noopener", title: "Открыть на GitHub" },
      h("i", { class: "build__dot" }), h("div", {}, h("b", {}, title), h("span", {}, sub)));
  }
  function renderBuild() { document.querySelectorAll("[data-build]").forEach((slot) => slot.replaceChildren(buildEl())); }

  /* ── Вход ────────────────────────────────────── */
  function loginScreen(err) {
    $("#app").replaceChildren(h("main", { class: "login" },
      h("div", { class: "login__card" },
        h("div", { class: "mark" }, h("i", { class: "mark__plate" }), h("div", {}, h("div", { class: "mark__word" }, "PRSTNK"), h("div", { class: "mark__sub" }, "админка"))),
        h("h1", {}, "Вход в админку"),
        h("p", {}, "Работы, художники, подборки и журнал. Войдите через GitHub-аккаунт, у которого есть доступ к сайту."),
        err ? h("div", { class: "login__err", role: "alert" }, err) : null,
        h("button", { class: "btn btn--primary btn--block", onclick: login }, icon("gh"), "Войти через GitHub"),
        h("div", { class: "login__foot" }, "Что-то не так? ", h("a", { href: "/admin/old/" }, "Старая админка")))));
  }
  function login() {
    const base = (S.cfg.backend.base_url || "").replace(/\/$/, "");
    const url = `${base}/auth?provider=github&site_id=${encodeURIComponent(location.hostname)}&scope=repo`;
    const w = 600, hh = 720;
    const popup = window.open(url, "prstnk-auth", `width=${w},height=${hh},top=${(screen.height - hh) / 2},left=${(screen.width - w) / 2}`);
    if (!popup) return loginScreen("Браузер заблокировал окно входа — разрешите всплывающие окна для этого сайта.");
    const onMsg = (e) => {
      if (e.data === "authorizing:github") { popup.postMessage(e.data, e.origin); return; }
      const m = typeof e.data === "string" && e.data.match(/^authorization:github:(success|error):([\s\S]*)$/);
      if (!m) return;
      window.removeEventListener("message", onMsg);
      try { popup.close(); } catch (er) {}
      let payload = {}; try { payload = JSON.parse(m[2]); } catch (er) {}
      if (m[1] === "success" && payload.token) { S.token = payload.token; try { localStorage.setItem(TOKEN_KEY, S.token); } catch (er) {} boot(); }
      else loginScreen("GitHub не пустил: " + (payload.message || payload.error || "попробуйте ещё раз"));
    };
    window.addEventListener("message", onMsg);
  }
  function logout(msg) {
    try { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem("sveltia-cms.user"); } catch (e) {}
    S.token = null; S.dirty = false; clearTimeout(buildTimer);
    loginScreen(msg);
  }
  function savedToken() {
    try {
      const t = localStorage.getItem(TOKEN_KEY); if (t) return t;
      const sv = JSON.parse(localStorage.getItem("sveltia-cms.user") || "null"); // вход из старой админки тоже подходит
      return sv && sv.token;
    } catch (e) { return null; }
  }

  /* ── Описание разделов (поверх config.yml) ───── */
  // Группы полей — чтобы длинная форма читалась кусками. Не перечисленное идёт в «Ещё».
  const LAYOUT = {
    artworks: [
      ["Фото", ["mainImage", "orientation", "galleryImages"]],
      ["Главное", ["title", "artistId", "price", "status", "workType"]],
      ["Тираж", ["editionTotal", "editionNumber", "availableCount", "editionClosed"], (d) => d.workType !== "unique"],
      ["О работе", ["year", "technique", "techniqueGroup", "sheetSize", "imageSize", "description"]],
      ["Подробности", ["paper", "signature", "condition", "certificate", "specs"]],
      ["Размещение", ["featuredOnHome", "slug"]],
    ],
    artists: [
      ["Главное", ["name", "city", "birthYear", "oneLiner", "techniques"]],
      ["Биография", ["bio", "collections", "meta"]],
      ["Размещение", ["showInArtists", "featured"]],
      ["Имя в падежах", ["nameShort", "firstName", "gen"]],
      ["Адрес страницы", ["slug"]],
    ],
  };
  const HALF = new Set(["price", "year", "sheetSize", "imageSize", "editionTotal", "editionNumber", "availableCount", "city", "birthYear",
    "nameShort", "firstName", "period", "readingTime", "readMins", "author", "date", "tag", "number", "kicker", "tocTag", "role", "paper", "signature", "condition", "certificate"]);

  const colByName = (n) => S.cfg.collections.find((c) => c.name === n);
  const titleOf = (col, d) => stripTags(d[col.identifier_field || "title"]) || stripTags(d.title || d.name) || "Без названия";
  const labelOf = (f) => noEmoji(f.label || f.name);
  const isReq = (f) => f.required !== false && f.widget !== "boolean" && f.widget !== "hidden";

  function relOptions(f) {
    const items = S.data[f.collection] || [];
    const vf = f.value_field || "id";
    return items.map((it) => {
      const d = it.data;
      const v = d[vf] || (vf === "id" ? d.slug : null) || d[vf];
      const label = (f.display_fields || ["title"]).map((k) => stripTags(d[k])).filter(Boolean).join(" · ") || it.file;
      return { v, label, d };
    }).filter((o) => o.v).sort((a, b) => a.label.localeCompare(b.label, "ru"));
  }
  // Найти запись по значению связи (id, slug или — исторически — имя)
  function relFind(f, val) {
    if (val == null || val === "") return null;
    return relOptions(f).find((o) => o.v === val || (o.d && (o.d.slug === val || o.d.name === val || o.d.title === val))) || null;
  }
  const artistField = () => (colByName("artworks").fields || []).find((f) => f.name === "artistId");
  const artistName = (id) => { const o = relFind(artistField(), id); return o ? stripTags(o.d.name) : ""; };

  function imgSrc(v) {
    if (!v) return "";
    if (S.media[v]) return S.media[v].url;
    if (/^https?:/.test(v)) return v;
    return encodeURI("/" + String(v).replace(/^\//, ""));
  }
  const firstImage = (d) => d.mainImage || d.cover || d.coverImage || d.image || "";

  function siteUrl(col, d) {
    const slug = d.slug; if (!slug) return null;
    const p = { artworks: "work-", artists: "artist-", collections: "collection-" }[col.name];
    let path = p ? "/" + p + slug : col.name === "articles" ? "/journal/" + slug : col.name === "issues" ? "/zine-" + slug : null;
    if (!path) return null;
    return path + "?open=prstnk-preview"; // пока сайт под заглушкой — смотрим «изнутри»
  }

  /* ── Каркас ─────────────────────────────────── */
  function route() {
    const parts = location.hash.replace(/^#\/?/, "").split("/").map(decodeURIComponent);
    return { col: parts[1] && parts[0] === "c" ? parts[1] : null, mode: parts[2] || "list", file: parts[3] || null };
  }
  function shell(content) {
    const r = route();
    const cols = S.cfg.collections.filter((c) => c.folder);
    const navLink = (c, cls) => h("a", { href: "#/c/" + c.name, "aria-current": r.col === c.name ? "page" : null, class: cls },
      cls ? null : icon(NAV_ICON[c.name] || "articles"), noEmoji(c.label), cls ? null : h("span", { class: "count" }, (S.data[c.name] || []).length));
    const shop = cols.filter((c) => ["artworks", "artists", "collections"].includes(c.name));
    const mag = cols.filter((c) => !shop.includes(c));
    const side = h("aside", { class: "side" },
      h("a", { class: "mark", href: "#/" }, h("i", { class: "mark__plate" }), h("div", {}, h("div", { class: "mark__word" }, "PRSTNK"), h("div", { class: "mark__sub" }, "админка"))),
      h("nav", { class: "nav", "aria-label": "Разделы" }, h("div", { class: "nav__group" }, "Магазин"), shop.map((c) => navLink(c)), h("div", { class: "nav__group" }, "Журнал"), mag.map((c) => navLink(c))),
      h("div", { class: "side__foot" },
        h("div", { "data-build": "" }, buildEl()),
        h("div", { class: "user" }, S.user ? h("img", { src: S.user.avatar_url, alt: "" }) : null,
          h("div", { class: "user__name" }, S.user ? (S.user.name || S.user.login) : ""),
          h("button", { class: "btn btn--ghost btn--icon", title: "Выйти", "aria-label": "Выйти", onclick: () => logout() }, icon("out")))));
    const top = h("header", { class: "topbar" },
      h("div", { class: "topbar__row" }, h("a", { class: "mark", href: "#/" }, h("i", { class: "mark__plate" }), h("div", { class: "mark__word" }, "PRSTNK")),
        h("div", { "data-build": "", style: "margin-left:auto" }, buildEl()),
        h("button", { class: "btn btn--ghost btn--icon", "aria-label": "Выйти", onclick: () => logout() }, icon("out"))),
      h("nav", { class: "tabs", "aria-label": "Разделы" }, cols.map((c) => navLink(c, "tab"))));
    $("#app").replaceChildren(h("div", { class: "shell" }, side, h("div", { style: "min-width:0" }, top, h("main", { class: "main", id: "main" }, content))));
    const cur = $(".tabs [aria-current]"); if (cur) cur.scrollIntoView({ inline: "center", block: "nearest" });
  }

  /* ── Список записей ─────────────────────────── */
  const listState = {}; // фильтры по разделам (живут, пока открыта вкладка)
  function sorted(col) {
    return [...(S.data[col.name] || [])].sort((a, b) =>
      ((a.data.order ?? 99) - (b.data.order ?? 99)) || titleOf(col, a.data).localeCompare(titleOf(col, b.data), "ru"));
  }
  function viewList(col) {
    const st = listState[col.name] = listState[col.name] || { q: "", status: "", artist: "" };
    const items = sorted(col);
    const results = h("div", {});
    const draw = () => {
      const q = st.q.trim().toLowerCase();
      let list = items.filter((it) => !q || JSON.stringify(it.data).toLowerCase().includes(q) || it.file.toLowerCase().includes(q));
      if (col.name === "artworks") {
        if (st.status) list = list.filter((it) => (it.data.status || "available") === st.status);
        if (st.artist) list = list.filter((it) => { const o = relFind(artistField(), it.data.artistId); return o && o.v === st.artist; });
      }
      results.replaceChildren(!list.length ? h("div", { class: "empty" }, h("b", {}, items.length ? "Ничего не нашлось" : "Пока пусто"), items.length ? "Попробуйте другой запрос или сбросьте фильтры." : "Нажмите «Добавить», чтобы создать первую запись.")
        : col.name === "artworks" ? h("div", { class: "grid" }, list.map(workCard)) : h("div", { class: "rows" }, list.map((it) => rowFor(col, it))));
    };
    const filters = h("div", { class: "filters" },
      h("label", { class: "search" }, icon("search"), h("span", { class: "sr" }, "Поиск"),
        h("input", { type: "search", placeholder: "Поиск", value: st.q, oninput: (e) => { st.q = e.target.value; draw(); } })));
    if (col.name === "artworks") {
      const counts = {}; items.forEach((it) => { const s = it.data.status || "available"; counts[s] = (counts[s] || 0) + 1; });
      const chips = h("div", { class: "chips", role: "group", "aria-label": "Статус" });
      const drawChips = () => chips.replaceChildren(...[["", "Все", items.length], ...Object.entries(STATUS_CHIP).map(([k, v]) => [k, v, counts[k] || 0])].map(([k, v, n]) =>
        h("button", { class: "chip", "aria-pressed": String(st.status === k), onclick: () => { st.status = k; drawChips(); draw(); } }, v, h("span", { class: "n" }, n))));
      drawChips();
      const sel = h("select", { "aria-label": "Художник", onchange: (e) => { st.artist = e.target.value; draw(); } },
        h("option", { value: "" }, "Все художники"), relOptions(artistField()).map((o) => h("option", { value: o.v, selected: st.artist === o.v }, o.label)));
      filters.append(chips, sel);
    }
    draw();
    const noun = (NOUN[col.name] || [])[0] || "запись";
    shell([h("div", { class: "head" }, h("div", {}, h("h1", {}, noEmoji(col.label)), h("div", { class: "head__sub" }, items.length + " " + plural(items.length, ["запись", "записи", "записей"]))),
      col.create !== false ? h("div", { class: "head__actions" }, h("a", { class: "btn btn--accent", href: `#/c/${col.name}/new` }, icon("plus"), "Добавить " + noun)) : null),
      filters, results]);
  }
  const plural = (n, f) => f[(n % 10 === 1 && n % 100 !== 11) ? 0 : (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20)) ? 1 : 2];

  function workCard(it, opts = {}) {
    const d = it.data, src = imgSrc(d.mainImage), st = d.status || "available";
    const an = artistName(d.artistId);
    const sheet = h("div", { class: "card__sheet" + (src ? "" : " card__sheet--empty") },
      src ? h("img", { src, alt: "", loading: "lazy", onerror: (e) => { e.target.replaceWith(h("span", {}, "фото не открылось")); } }) : [icon("works"), "нет фото"]);
    const flags = h("div", { class: "card__flags" });
    if (!an && !opts.preview) flags.append(h("span", { class: "pill pill--warn" }, "нет художника"));
    if (flags.childNodes.length) sheet.append(flags);
    const body = h("div", { class: "card__body" },
      h("div", { class: "card__title" }, stripTags(d.title) || "Без названия"),
      h("div", { class: "card__meta" }, [an, d.year].filter(Boolean).join(" · ") || "—"),
      h("div", { class: "card__row" }, h("span", { class: "price" }, fmtPrice(d.price)), h("span", { class: "pill pill--" + st }, STATUS[st] || st)));
    return opts.preview ? h("div", { class: "card preview" }, sheet, body)
      : h("a", { class: "card", href: `#/c/artworks/e/${encodeURIComponent(it.file)}` }, sheet, body);
  }

  function rowFor(col, it) {
    const d = it.data;
    let sub = "", end = "";
    if (col.name === "artists") {
      const n = (S.data.artworks || []).filter((w) => { const o = relFind(artistField(), w.data.artistId); return o && (o.d === d); }).length;
      sub = [d.city, d.birthYear].filter(Boolean).join(" · "); end = n + " " + plural(n, ["работа", "работы", "работ"]);
      if (d.showInArtists === false) sub += " · скрыт";
    } else if (col.name === "collections") { sub = stripTags(d.subtitle); end = (d.works || []).length + " раб."; }
    else if (col.name === "issues") { sub = [d.period, stripTags(d.lead)].filter(Boolean).join(" · "); end = d.current ? "текущий" : ""; }
    else { sub = stripTags(d.lead || d.excerpt || d.subtitle || ""); end = d.date ? String(d.date).slice(0, 10) : ""; }
    const color = PALETTE[d.color || d.coverColor];
    const img = imgSrc(firstImage(d));
    const lead = img ? h("img", { class: "row__thumb", src: img, alt: "", loading: "lazy" })
      : col.name === "artists" ? h("span", { class: "row__ava", "aria-hidden": "true" }, stripTags(d.name).split(" ").map((w) => w[0]).slice(0, 2).join(""))
      : h("i", { class: "row__sw", style: color ? `background:${color[1]}` : null });
    const title = col.name === "issues" ? `№ ${d.number || "—"} · ${stripTags(d.title)}` : titleOf(col, d);
    return h("a", { class: "row", href: `#/c/${col.name}/e/${encodeURIComponent(it.file)}` }, lead,
      h("div", { class: "row__main" }, h("div", { class: "row__title" }, title), sub ? h("div", { class: "row__sub" }, sub) : null),
      end ? h("span", { class: "row__end" }, end) : null, icon("chev", "chev"));
  }

  /* ── Редактор ───────────────────────────────── */
  function defaultsFor(fields) {
    const o = {};
    for (const f of fields || []) {
      if (f.default !== undefined) o[f.name] = clone(f.default);
      else if (f.widget === "list") o[f.name] = [];
      else if (f.widget === "boolean") o[f.name] = false;
    }
    return o;
  }

  function viewEditor(col, file) {
    const isNew = !file;
    const entry = isNew ? null : (S.data[col.name] || []).find((it) => it.file === file);
    if (!isNew && !entry) { shell(h("div", { class: "empty" }, h("b", {}, "Запись не найдена"), h("a", { href: "#/c/" + col.name }, "Вернуться к списку"))); return; }
    const draft = isNew ? defaultsFor(col.fields) : clone(entry.data);
    if (col.name === "artworks" && draft.artistId) { const o = relFind(artistField(), draft.artistId); if (o) draft.artistId = o.v; }
    const ctx = S.ctx = { col, entry, draft, isNew, validators: [], slugTouched: !isNew, onChange: null };
    S.dirty = false;

    const stateEl = h("div", { class: "savebar__state" }, isNew ? "Новая запись" : "Изменений нет");
    const saveBtn = h("button", { class: "btn btn--primary", onclick: () => save(ctx) }, "Сохранить");
    ctx.saveBtn = saveBtn;
    const asideSlot = h("div", {});
    const formEl = h("div", { class: "form" });
    const errSlot = h("div", {});

    const drawAside = () => {
      if (col.name !== "artworks") return;
      const url = !isNew && siteUrl(col, entry.data);
      asideSlot.replaceChildren(h("div", { class: "aside__label" }, "Так в каталоге"), workCard({ data: draft }, { preview: true }),
        h("div", { class: "aside__links" }, url ? h("a", { href: url, target: "_blank", rel: "noopener" }, icon("ext"), "Открыть на сайте") : null));
    };
    const drawForm = () => { ctx.validators = []; formEl.replaceChildren(...buildForm(ctx)); };
    ctx.onChange = (structural) => {
      if (!S.dirty) { S.dirty = true; stateEl.textContent = "Есть несохранённые изменения"; stateEl.classList.add("is-dirty"); }
      if (structural) drawForm();
      // красная сводка ошибок исчезает, когда всё поправили
      if (ctx.errSlot && ctx.errSlot.childNodes.length && !document.querySelector(".f.is-bad")) ctx.errSlot.replaceChildren();
      drawAside();
    };
    ctx.redraw = drawForm;
    drawForm(); drawAside();

    const title = isNew ? ((NOUN[col.name] || [])[1] || "Новая запись") : titleOf(col, draft);
    const url = !isNew && siteUrl(col, entry.data);
    const aside = col.name === "artworks" ? h("aside", { class: "aside" }, asideSlot)
      : null;
    shell([
      h("div", { class: "crumbs" }, h("a", { href: "#/c/" + col.name }, icon("back"), noEmoji(col.label))),
      h("div", { class: "head" }, h("h1", { id: "ed-title" }, title),
        url && col.name !== "artworks" ? h("div", { class: "head__actions" }, h("a", { class: "btn btn--sm", href: url, target: "_blank", rel: "noopener" }, icon("ext"), "На сайте")) : null),
      h("div", { class: "editor" + (aside ? "" : " editor--wide") }, h("div", {}, errSlot, formEl), aside),
      h("div", { class: "savebar" }, stateEl,
        h("div", { class: "savebar__right" },
          !isNew && col.delete !== false ? h("button", { class: "btn btn--danger", onclick: () => remove(ctx) }, icon("trash"), h("span", {}, "Удалить")) : null,
          saveBtn)),
    ]);
    ctx.errSlot = errSlot;
    if (isNew) { const first = formEl.querySelector("input,textarea,select"); if (first && col.name !== "artworks") first.focus(); }
  }

  function buildForm(ctx) {
    const { col, draft } = ctx;
    const fields = (col.fields || []).filter((f) => f.widget !== "hidden");
    const layout = LAYOUT[col.name];
    const used = new Set();
    const sections = [];
    if (layout) {
      for (const [title, names, cond] of layout) {
        const fs = names.map((n) => fields.find((f) => f.name === n)).filter(Boolean);
        fs.forEach((f) => used.add(f.name));
        if (cond && !cond(draft)) continue;
        if (fs.length) sections.push([title, fs]);
      }
      const rest = fields.filter((f) => !used.has(f.name));
      if (rest.length) sections.push(["Ещё", rest]);
    } else sections.push([null, fields]);
    return sections.map(([title, fs]) => h("section", { class: "section" },
      title ? h("h2", { class: "section__title" }, title) : null,
      h("div", { class: "fields" }, fs.map((f) => fieldEl(f, draft, ctx, true)))));
  }

  // Поле формы: подпись + виджет + подсказка + ошибка. obj[f.name] — значение.
  function fieldEl(f, obj, ctx, top) {
    const id = "f" + Math.random().toString(36).slice(2, 9);
    const wrap = h("div", { class: "f" + ((HALF.has(f.name) || f.widget === "number") && f.widget !== "list" ? " f--half" : ""), "data-field": f.name });
    const isTitle = top && f.name === (ctx.col.identifier_field || "title") && f.widget === "string";
    const widget = makeWidget(f, obj, ctx, id, isTitle);
    const hint = hintFor(f, ctx);
    const err = h("div", { class: "f__err", role: "alert" });
    if (f.widget === "boolean") wrap.append(widget);
    else wrap.append(h(f.widget === "list" || f.widget === "object" || f.widget === "select" ? "div" : "label", { class: "f__label", for: id }, labelOf(f), isReq(f) ? h("span", { class: "req", "aria-hidden": "true" }, "*") : null), widget);
    if (hint && f.widget !== "boolean") wrap.append(h("div", { class: "f__hint" }, hint));
    wrap.append(err);
    // проверка
    ctx.validators.push({ el: wrap, f, check: () => validate(f, obj[f.name], ctx), err });
    return wrap;
  }

  function hintFor(f, ctx) {
    if (f.name === "slug") {
      const base = { artworks: "work-", artists: "artist-", collections: "collection-" }[ctx.col.name];
      return ctx.isNew ? "Заполнится сам из названия. Только латиница, цифры и дефисы." + (base ? ` Ссылка будет prstnk.ru/${base}…` : "")
        : "Если поменять — старая ссылка на страницу перестанет работать.";
    }
    return f.hint ? noEmoji(f.hint) : "";
  }

  function validate(f, v, ctx) {
    const empty = v == null || v === "" || (Array.isArray(v) && !v.length && f.widget !== "list");
    if (isReq(f) && empty && !(f.name === "slug" && ctx && ctx.isNew)) return "Заполните это поле";
    if (f.widget === "number" && v !== "" && v != null) {
      if (isNaN(v)) return "Нужно число";
      if (f.min != null && v < f.min) return "Не меньше " + f.min;
      if (f.max != null && v > f.max) return "Не больше " + f.max;
    }
    // художник обязан существовать (иначе падает сборка); ссылки на работы в подборках/статьях
    // сайт просто пропускает — их не блокируем, только подсвечиваем в списке
    if (f.widget === "relation" && v && !relFind(f, v) && f.collection !== "artworks") return "Выберите из списка";
    if (f.name === "slug" && v && !/^[a-z0-9]+(-[a-z0-9]+)*$/.test(v)) return "Только латинские буквы, цифры и дефисы";
    return "";
  }

  function makeWidget(f, obj, ctx, id, isTitle) {
    const set = (v, structural) => {
      if (v === undefined || v === null || (v === "" && f.widget === "number")) delete obj[f.name]; else obj[f.name] = v;
      // авто-адрес из названия (пока человек не трогал адрес сам)
      if (isTitle && ctx.isNew && !ctx.slugTouched && ctx.col.fields.some((x) => x.name === "slug" && x.widget !== "hidden")) {
        ctx.draft.slug = slugify(v);
        const s = document.querySelector('[data-field="slug"] input'); if (s) s.value = ctx.draft.slug;
      }
      if (f.name === "slug" && obj === ctx.draft) ctx.slugTouched = true;
      const wrap = document.querySelector(`[id="${id}"]`); const fw = wrap && wrap.closest(".f");
      if (fw && fw.classList.contains("is-bad")) { const e = validate(f, obj[f.name], ctx); if (!e) fw.classList.remove("is-bad"); }
      ctx.onChange(structural);
    };
    const v = obj[f.name];
    switch (f.widget) {
      case "text":
        return autoGrow(h("textarea", { id, class: "inp", rows: 3, value: v || "", oninput: (e) => set(e.target.value) }));
      case "markdown":
        return mdEditor(id, v || "", (val) => set(val));
      case "number": {
        const inp = h("input", { id, class: "inp inp--mono", type: "text", inputmode: "numeric", value: v ?? "", oninput: (e) => {
          const raw = e.target.value.replace(/\s/g, "").replace(",", ".");
          set(raw === "" ? "" : f.value_type === "int" ? (/^-?\d+$/.test(raw) ? parseInt(raw, 10) : NaN) : Number(raw));
        } });
        return f.name === "price" ? h("div", { class: "inp-suffix" }, inp, h("span", {}, "₽")) : inp;
      }
      case "boolean": {
        const hint = f.hint ? noEmoji(f.hint) : "";
        return h("label", { class: "tog", for: id }, h("input", { id, type: "checkbox", checked: !!v, onchange: (e) => set(e.target.checked) }),
          h("span", { class: "tog__track", "aria-hidden": "true" }), h("span", { class: "tog__text" }, labelOf(f), hint ? h("small", {}, hint) : null));
      }
      case "select": return selectWidget(f, v, id, set);
      case "relation": {
        const opts = relOptions(f);
        const cur = relFind(f, v);
        return h("select", { id, class: "inp", onchange: (e) => set(e.target.value) },
          h("option", { value: "" }, "— выберите —"),
          opts.map((o) => h("option", { value: o.v, selected: cur && cur.v === o.v }, o.label)),
          v && !cur ? h("option", { value: v, selected: true }, v + " — не найдено, выберите заново") : null);
      }
      case "image": return imageWidget(f, v, id, (val) => set(val));
      case "datetime": {
        const val = v ? String(v).slice(0, 10) : "";
        return h("input", { id, class: "inp inp--mono", type: "date", value: val, onchange: (e) => set(e.target.value) });
      }
      case "list": return listWidget(f, obj, ctx);
      case "object": {
        if (!obj[f.name] || typeof obj[f.name] !== "object") obj[f.name] = {};
        const o = obj[f.name];
        const inner = h("div", { class: "fields" }, (f.fields || []).filter((x) => x.widget !== "hidden").map((sf) => fieldEl(sf, o, ctx)));
        const hasVal = Object.values(o).some((x) => x !== "" && x != null);
        return f.collapsed ? h("details", { class: "obj", open: hasVal }, h("summary", {}, icon("chev"), hasVal ? "Заполнено" : "Добавить"), inner) : h("div", { class: "obj" }, inner);
      }
      default: {
        const inp = h("input", { id, class: "inp" + (isTitle ? " inp--title" : "") + (f.name === "slug" ? " inp--mono" : ""), type: "text", value: v ?? "", autocomplete: "off",
          oninput: (e) => set(f.name === "slug" ? e.target.value.trim().toLowerCase() : e.target.value) });
        return inp;
      }
    }
  }

  function autoGrow(ta) {
    // растёт под текст (в т.ч. когда поле было скрыто в свёрнутом блоке и стало видно)
    const fit = () => { if (!ta.offsetParent) return; ta.style.height = "auto"; ta.style.height = Math.min(Math.max(96, ta.scrollHeight + 2), innerHeight * 0.75) + "px"; };
    ta.addEventListener("input", fit); ta.addEventListener("focus", fit);
    new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && fit())).observe(ta);
    return ta;
  }

  function selectWidget(f, v, id, set) {
    const opts = (f.options || []).map((o) => (typeof o === "object" ? o : { label: String(o), value: o }));
    if (opts.length && opts.every((o) => PALETTE[o.value])) {
      const box = h("div", { class: "swatches", role: "radiogroup", id });
      opts.forEach((o) => box.append(h("button", { type: "button", class: "swatch", role: "radio", "aria-checked": String(v === o.value), "data-v": o.value,
        onclick: () => { box.querySelectorAll(".swatch").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.v === o.value))); set(o.value); } },
        h("i", { style: `background:${PALETTE[o.value][1]}` }), o.label)));
      return box;
    }
    if (opts.length <= 4) {
      const box = h("div", { class: "seg" + (f.name === "status" ? " seg--status" : ""), role: "radiogroup", id });
      opts.forEach((o) => box.append(h("button", { type: "button", role: "radio", "aria-checked": String(v === o.value), "data-v": o.value,
        onclick: () => { box.querySelectorAll("button").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.v === String(o.value)))); set(o.value, f.name === "workType"); } }, o.label)));
      return box;
    }
    return h("select", { id, class: "inp", onchange: (e) => set(e.target.value) }, h("option", { value: "" }, "— выберите —"),
      opts.map((o) => h("option", { value: o.value, selected: v === o.value }, o.label)));
  }

  function mdEditor(id, value, onInput) {
    const ta = autoGrow(h("textarea", { id, value, oninput: (e) => onInput(e.target.value) }));
    const wrapSel = (before, after = before, ph = "текст") => {
      const s = ta.selectionStart, e = ta.selectionEnd, sel = ta.value.slice(s, e) || ph;
      ta.setRangeText(before + sel + after, s, e, "end"); ta.focus(); ta.dispatchEvent(new Event("input"));
    };
    const linePrefix = (p) => {
      const s = ta.value.lastIndexOf("\n", ta.selectionStart - 1) + 1;
      ta.setRangeText(p, s, s, "end"); ta.focus(); ta.dispatchEvent(new Event("input"));
    };
    const b = (label, title, fn, style) => h("button", { type: "button", title, "aria-label": title, style, onclick: fn }, label);
    return h("div", { class: "md" }, h("div", { class: "md__bar" },
      b("Ж", "Жирный", () => wrapSel("**"), "font-weight:700"),
      b("К", "Курсив", () => wrapSel("*"), "font-style:italic"),
      b("Заголовок", "Подзаголовок раздела", () => linePrefix("### ")),
      b("• Список", "Список", () => linePrefix("- ")),
      b("1. Список", "Нумерованный список", () => linePrefix("1. ")),
      b("Ссылка", "Ссылка", () => wrapSel("[", "](https://)", "текст ссылки"))), ta);
  }

  /* Фото: перетащить / выбрать файл. Сохраняется вместе с записью. */
  function imageWidget(f, v, id, set) {
    const box = h("div", {});
    const draw = (val) => {
      if (!val) {
        const input = h("input", { id, type: "file", accept: "image/*", "aria-label": labelOf(f), onchange: (e) => e.target.files[0] && take(e.target.files[0]) });
        const drop = h("div", { class: "drop" }, h("div", { class: "drop__cta" }, icon("upload"), h("b", {}, "Перетащите фото сюда"), "или нажмите, чтобы выбрать файл"), input);
        drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("is-over"); });
        drop.addEventListener("dragleave", () => drop.classList.remove("is-over"));
        drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("is-over"); const fl = e.dataTransfer.files[0]; if (fl) take(fl); });
        box.replaceChildren(drop);
      } else {
        const pending = !!S.media[val];
        const repl = h("input", { type: "file", accept: "image/*", class: "sr", onchange: (e) => e.target.files[0] && take(e.target.files[0]) });
        box.replaceChildren(h("div", { class: "photo" },
          h("img", { class: "photo__img", src: imgSrc(val), alt: "", onerror: (e) => { e.target.alt = "не открылось"; } }),
          h("div", { class: "photo__side" },
            pending ? h("span", { class: "photo__badge" }, "загрузится при сохранении") : null,
            h("div", { class: "photo__name" }, decodeURIComponent(String(val).split("/").pop())),
            h("label", { class: "btn btn--sm" }, repl, icon("upload"), "Заменить"),
            h("button", { type: "button", class: "btn btn--sm btn--danger", onclick: () => { set(""); draw(""); } }, icon("x"), "Убрать"))));
      }
    };
    const take = async (file) => {
      try {
        busy(true);
        const val = await stageImage(file);
        set(val); draw(val);
      } catch (e) { toast("Не получилось взять фото: " + e.message, true); }
      finally { busy(false); }
    };
    draw(v);
    return box;
  }

  async function stageImage(file) {
    if (!/^image\//.test(file.type) && !/\.(jpe?g|png|webp|gif|heic)$/i.test(file.name)) throw new Error("это не картинка");
    let blob = file, ext = (file.name.split(".").pop() || "jpg").toLowerCase();
    // Большие фото ужимаем до 3000 px по длинной стороне — сайт грузится быстрее, качество для экрана то же
    try {
      const bmp = await createImageBitmap(file);
      const max = 3000, k = Math.min(1, max / Math.max(bmp.width, bmp.height));
      if (k < 1 || ext === "heic" || file.size > 4e6) {
        const c = document.createElement("canvas");
        c.width = Math.round(bmp.width * k); c.height = Math.round(bmp.height * k);
        c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
        blob = await new Promise((r) => c.toBlob(r, "image/jpeg", 0.9)); ext = "jpg";
      }
    } catch (e) { /* браузер не умеет разобрать — грузим как есть */ }
    if (blob.size > 25e6) throw new Error("файл больше 25 МБ");
    const base = slugify(file.name.replace(/\.[^.]+$/, "")).slice(0, 50) || "foto";
    const name = `${base}-${Date.now().toString(36)}.${ext === "jpeg" ? "jpg" : ext}`;
    const folder = (S.cfg.media_folder || "images").replace(/^\/|\/$/g, "");
    const pub = "/" + (S.cfg.public_folder || folder).replace(/^\/|\/$/g, "");
    const val = `${pub}/${name}`;
    S.media[val] = { path: `${folder}/${name}`, b64: bytesToB64(new Uint8Array(await blob.arrayBuffer())), url: URL.createObjectURL(blob) };
    return val;
  }

  /* Списки: строки, объекты, блоки разных типов */
  function listWidget(f, obj, ctx) {
    if (!Array.isArray(obj[f.name])) obj[f.name] = [];
    const arr = obj[f.name];
    const box = h("div", { class: "list" });
    const typeKey = f.typeKey || "type";
    const single = f.field && !f.fields && !f.types;
    const noun = noEmoji(f.label_singular || (single ? f.field.label : "") || "строку").toLowerCase();
    const open = ctx.openItems = ctx.openItems || new WeakSet();

    const draw = () => {
      box.replaceChildren();
      arr.forEach((item, i) => {
        const tools = h("div", { class: "item__tools" },
          i > 0 ? h("button", { type: "button", class: "btn btn--ghost", title: "Выше", "aria-label": "Переместить выше", onclick: () => { arr.splice(i - 1, 0, arr.splice(i, 1)[0]); draw(); ctx.onChange(); } }, icon("up")) : null,
          i < arr.length - 1 ? h("button", { type: "button", class: "btn btn--ghost", title: "Ниже", "aria-label": "Переместить ниже", onclick: () => { arr.splice(i + 1, 0, arr.splice(i, 1)[0]); draw(); ctx.onChange(); } }, icon("down")) : null,
          h("button", { type: "button", class: "btn btn--ghost", title: "Удалить", "aria-label": "Удалить", onclick: async () => {
            const filled = single ? item !== "" && item != null : Object.values(item || {}).some((x) => x !== "" && x != null && !(Array.isArray(x) && !x.length));
            if (filled && !(await modal({ title: "Удалить " + noun + "?", text: "Это уберёт строку из записи. Насовсем — после сохранения.", ok: "Удалить", danger: true }))) return;
            arr.splice(i, 1); draw(); ctx.onChange();
          } }, icon("trash")));
        if (single) {
          const holder = { v: item };
          const sf = { ...f.field, name: "v", required: f.field.required };
          const w = makeWidget(sf, holder, { ...ctx, onChange: (s) => { if (holder.v === undefined) holder.v = ""; arr[i] = holder.v; ctx.onChange(s); } }, "f" + Math.random().toString(36).slice(2, 9), false);
          box.append(h("div", { class: "item--inline" }, h("div", { class: "grow" }, w), tools));
          return;
        }
        if (!item || typeof item !== "object") arr[i] = item = {};
        const type = f.types ? f.types.find((t) => t.name === item[typeKey]) : null;
        const fields = (type ? type.fields : f.fields) || [];
        const sum = summaryOf(f, item, fields) || "пока пусто";
        const isOpen = open.has(item);
        const el = h("div", { class: "item" + (isOpen ? "" : " is-closed") });
        const toggle = h("button", { type: "button", class: "item__toggle", "aria-expanded": String(isOpen), onclick: () => {
          if (open.has(item)) open.delete(item); else open.add(item);
          el.classList.toggle("is-closed"); toggle.setAttribute("aria-expanded", String(open.has(item)));
        } }, type ? h("span", { class: "item__type" }, noEmoji(type.label)) : null, h("span", {}, sum));
        el.append(h("div", { class: "item__head" }, toggle, tools),
          h("div", { class: "item__body" }, h("div", { class: "fields" }, fields.filter((x) => x.widget !== "hidden").map((sf) => fieldEl(sf, item, { ...ctx, onChange: (s) => { ctx.onChange(s); } })))));
        box.append(el);
      });
      const add = (type) => {
        let item;
        if (single) item = f.field.default ?? "";
        else { item = defaultsFor(type ? type.fields : f.fields); if (type) item[typeKey] = type.name; open.add(item); }
        arr.push(item); draw(); ctx.onChange();
        const last = box.querySelectorAll(":scope > .item, :scope > .item--inline"); const n = last[last.length - 1];
        const inp = n && n.querySelector("input:not([type=file]),textarea,select"); if (inp) inp.focus();
      };
      box.append(h("div", { class: "addrow" }, f.types
        ? f.types.map((t) => h("button", { type: "button", class: "btn btn--sm", onclick: () => add(t) }, icon("plus"), noEmoji(t.label)))
        : h("button", { type: "button", class: "btn btn--sm", onclick: () => add() }, icon("plus"), "Добавить " + noun)));
    };
    draw();
    return box;
  }
  function summaryOf(f, item, fields) {
    if (f.summary) {
      const s = stripTags(f.summary.replace(/\{\{\s*fields\.(\w+)\s*\}\}/g, (_, k) => {
        const v = item[k]; if (k === "work") { const o = relFind(fields.find((x) => x.name === "work") || {}, v); return o ? o.label : v || ""; }
        return v == null ? "" : String(v);
      })).replace(/^[:\s·]+|[:\s·]+$/g, "");
      if (s) return s;
    }
    for (const sf of fields) {
      const v = item[sf.name];
      if (typeof v === "string" && v.trim() && sf.widget !== "image") return stripTags(v).replace(/^[#>*\-\s]+|[*_]{1,2}/g, "").slice(0, 90);
    }
    return "";
  }

  /* ── Сохранение ─────────────────────────────── */
  function cleanup(o) {
    if (Array.isArray(o)) return o.map(cleanup);
    if (o && typeof o === "object") {
      const r = {};
      for (const [k, v] of Object.entries(o)) { if (v === null || v === undefined || (typeof v === "number" && isNaN(v))) continue; r[k] = cleanup(v); }
      return r;
    }
    return o;
  }
  function collectMedia(o, out = new Set()) {
    if (typeof o === "string" && S.media[o]) out.add(o);
    else if (o && typeof o === "object") Object.values(o).forEach((v) => collectMedia(v, out));
    return out;
  }

  async function save(ctx) {
    const { col, draft, isNew } = ctx;
    // автозаполнение служебного — то, на чём раньше падала сборка
    const hasField = (n) => col.fields.some((x) => x.name === n);
    if (hasField("slug") && !draft.slug) {
      draft.slug = col.name === "issues" ? String(draft.number || "") : slugify(draft[col.identifier_field || "title"] || draft.title || draft.name);
    }
    if (hasField("id") && !draft.id) draft.id = draft.slug;
    if (col.name === "artworks" && draft.artistId) { const o = relFind(artistField(), draft.artistId); if (o) draft.artistId = o.v; }
    for (const f of col.fields) if (f.widget === "hidden" && draft[f.name] === undefined && f.default !== undefined) draft[f.name] = clone(f.default);

    // проверка
    const bad = [];
    ctx.validators.filter((v) => v.el.isConnected).forEach((v) => {
      const e = v.check();
      v.el.classList.toggle("is-bad", !!e); v.err.textContent = e;
      if (e) bad.push(v);
    });
    const ext = "." + (col.extension || "json");
    let file = ctx.entry ? ctx.entry.file : null;
    if (isNew) {
      const tpl = col.slug || "{{slug}}";
      const base = tpl.replace(/\{\{\s*(\w+)\s*\}\}/g, (_, k) => k === "slug" ? (draft.slug || "") : slugify(String(draft[k] ?? ""))) || slugify(String(Date.now()));
      file = base + ext;
      const clash = (S.data[col.name] || []).find((it) => it.file === file || (draft.slug && it.data.slug === draft.slug));
      if (clash) {
        const sv = ctx.validators.find((v) => v.f.name === "slug" || v.f.name === "number");
        if (sv) { sv.el.classList.add("is-bad"); sv.err.textContent = "Такой адрес уже занят: «" + titleOf(col, clash.data) + "»"; bad.push(sv); }
        else bad.push({ el: null, f: { label: "Адрес" } });
      }
    } else if (draft.slug && (S.data[col.name] || []).some((it) => it !== ctx.entry && it.data.slug === draft.slug)) {
      const sv = ctx.validators.find((v) => v.f.name === "slug");
      if (sv) { sv.el.classList.add("is-bad"); sv.err.textContent = "Такой адрес уже у другой записи"; bad.push(sv); }
    }
    if (bad.length) {
      ctx.errSlot.replaceChildren(h("div", { class: "errsum", role: "alert" }, h("b", {}, "Не сохранено — поправьте " + bad.length + " " + plural(bad.length, ["поле", "поля", "полей"])),
        bad.map((v, i) => [i ? ", " : "", v.el ? h("a", { href: "#", onclick: (e) => { e.preventDefault(); v.el.scrollIntoView({ block: "center", behavior: "smooth" }); const x = v.el.querySelector("input,select,textarea,button"); if (x) x.focus({ preventScroll: true }); } }, labelOf(v.f)) : labelOf(v.f)])));
      const first = bad.find((v) => v.el); if (first) { first.el.scrollIntoView({ block: "center", behavior: "smooth" }); }
      return;
    }
    ctx.errSlot.replaceChildren();

    const path = col.folder + "/" + file;
    const btn = ctx.saveBtn; btn.disabled = true; btn.replaceChildren(h("i", { class: "spin" }), "Сохраняем…"); busy(true);
    try {
      // кто-то (Настя, бот заявок) мог поменять файл, пока он был открыт
      const now = await remoteSha(path);
      if (isNew ? now : now && now !== ctx.entry.sha) {
        const ok = await modal({ title: isNew ? "Такой файл уже есть" : "Запись изменили в другом месте",
          text: isNew ? "Похоже, запись с таким адресом только что создали. Поменяйте адрес." : "Пока вы редактировали, её поменял кто-то ещё (или бот заявок поменял статус). Если сохранить, ваша версия заменит ту.",
          ok: isNew ? "Понятно" : "Сохранить мою версию", noCancel: isNew });
        if (isNew || !ok) return;
      }
      let data = cleanup(draft);
      if (isNew) { // в новом файле — поля в том же порядке, что в форме
        const ord = {}; col.fields.forEach((f, i) => { ord[f.name] = i; });
        data = Object.fromEntries(Object.entries(data).sort(([a], [b]) => (ord[a] ?? 999) - (ord[b] ?? 999)));
      }
      const media = [...collectMedia(data)];
      const files = [{ path, b64: strToB64(JSON.stringify(data, null, 2) + "\n") }, ...media.map((m) => ({ path: S.media[m].path, b64: S.media[m].b64 }))];
      const label = noEmoji(col.label_singular || col.label);
      const shas = await commit(files, [], `${isNew ? "Create" : "Update"} ${label} “${titleOf(col, data)}”${media.length ? " +" + media.length + " фото" : ""}`);
      media.forEach((m) => { S.media[m].b64 = null; }); // превью оставляем до перезагрузки — на сайте фото появится после сборки
      if (isNew) S.data[col.name].push(ctx.entry = { file, path, sha: shas[path], data });
      else { ctx.entry.data = data; ctx.entry.sha = shas[path]; }
      S.dirty = false; S.lastSaveAt = Date.now();
      toast("Сохранено. Сайт обновится через 1–2 минуты.");
      setTimeout(pollBuild, 3000);
      if (isNew) { location.replace(`#/c/${col.name}/e/${encodeURIComponent(file)}`); }
      else render();
    } catch (e) {
      if (e.message !== "401") toast("Не сохранилось: " + e.message + ". Изменения на месте — попробуйте ещё раз.", true);
    } finally { busy(false); if (btn.isConnected) { btn.disabled = false; btn.replaceChildren("Сохранить"); } }
  }

  async function remove(ctx) {
    const { col, entry } = ctx;
    const d = entry.data, t = titleOf(col, d);
    if (col.name === "artists") {
      const n = (S.data.artworks || []).filter((w) => { const o = relFind(artistField(), w.data.artistId); return o && o.d === d; }).length;
      if (n) return modal({ title: "Сначала работы", text: `У художника ${n} ${plural(n, ["работа", "работы", "работ"])} в каталоге. Удалите их или перенесите на другого автора — иначе сайт не соберётся.`, ok: "Понятно", noCancel: true });
    }
    let extra = "";
    if (col.name === "artworks") {
      const inCols = (S.data.collections || []).filter((c) => (c.data.works || []).includes(d.slug)).map((c) => "«" + stripTags(c.data.title) + "»");
      if (inCols.length) extra = " Она есть в подборках " + inCols.join(", ") + " — оттуда пропадёт.";
    }
    if (!(await modal({ title: `Удалить «${t}»?`, text: "Запись исчезнет с сайта после пересборки. Вернуть можно только через историю на GitHub." + extra, ok: "Удалить", danger: true }))) return;
    busy(true);
    try {
      await commit([], [entry.path], `Delete ${noEmoji(col.label_singular || col.label)} “${t}”`);
      S.data[col.name] = S.data[col.name].filter((it) => it !== entry);
      S.dirty = false; S.lastSaveAt = Date.now();
      toast("Удалено."); setTimeout(pollBuild, 3000);
      location.hash = "#/c/" + col.name;
    } catch (e) { if (e.message !== "401") toast("Не удалилось: " + e.message, true); }
    finally { busy(false); }
  }

  /* ── Навигация с защитой несохранённого ─────── */
  function render() {
    const r = route();
    const col = r.col && colByName(r.col);
    if (!col) { location.replace("#/c/" + S.cfg.collections[0].name); return; }
    if (r.mode === "new") viewEditor(col, null);
    else if (r.mode === "e") viewEditor(col, r.file);
    else { S.ctx = null; viewList(col); }
    window.scrollTo(0, 0);
  }
  let lastHash = location.hash;
  window.addEventListener("hashchange", async () => {
    if (S.dirty) {
      const target = location.hash;
      history.replaceState(null, "", lastHash);
      if (!(await modal({ title: "Уйти без сохранения?", text: "Изменения в этой записи пропадут.", ok: "Уйти", cancel: "Остаться", danger: true }))) return;
      S.dirty = false; lastHash = target; location.hash = target; return;
    }
    lastHash = location.hash; render();
  });
  window.addEventListener("beforeunload", (e) => { if (S.dirty) { e.preventDefault(); e.returnValue = ""; } });
  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s" && S.ctx) { e.preventDefault(); save(S.ctx); }
  });
  document.addEventListener("visibilitychange", () => { if (!document.hidden && S.token) pollBuild(); });

  /* ── Старт ──────────────────────────────────── */
  async function boot() {
    if (!S.cfg) {
      const txt = await (await fetch("config.yml", { cache: "no-store" })).text();
      S.cfg = jsyaml.load(txt);
      S.repo = S.cfg.backend.repo;
      S.branch = qs.get("branch") || S.cfg.backend.branch || "main"; // ?branch=… — для проверок на тестовой ветке
    }
    S.token = S.token || savedToken();
    if (!S.token) return loginScreen();
    $("#app").replaceChildren(h("div", { class: "login" }, h("div", { class: "mark" }, h("i", { class: "mark__plate" }), h("div", {}, h("div", { class: "mark__word" }, "PRSTNK"), h("div", { class: "mark__sub" }, "загружаем каталог…")))));
    busy(true);
    try {
      const [user, repo] = await Promise.all([gh("/user"), gh(`/repos/${S.repo}`)]);
      S.user = user;
      if (!repo.permissions || !repo.permissions.push) return logout(`У аккаунта ${user.login} нет права изменять сайт. Попросите владельца добавить его в репозиторий.`);
      await loadAll();
    } catch (e) {
      if (e.message === "401") return;
      return loginScreen("Не удалось загрузить данные: " + e.message);
    } finally { busy(false); }
    render(); pollBuild();
  }
  boot().catch((e) => { $("#app").textContent = "Ошибка запуска: " + e.message; });
})();
