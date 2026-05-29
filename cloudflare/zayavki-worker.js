// ============================================================
// PRSTNK — воркер заявок + управление статусом работы из Telegram.
//
// 1) Принимает POST-форму с сайта (поля + фото) → шлёт в группу «PRSTNK Заявки».
//    Если в заявке есть работа (slug) — под сообщением кнопки:
//    🟡 Бронь · 🟢 Снять · ⚫️ Продано.
// 2) Принимает вебхук Telegram (нажатие кнопки) → меняет status работы
//    в data/artworks/<slug>.json через GitHub API → сайт пересобирается (~1–2 мин).
//
// Переменные (Cloudflare → Worker → Settings → Variables):
//   BOT_TOKEN       — токен бота от @BotFather                 (Secret)
//   CHAT_ID         — id группы заявок (напр. -100…)           (Plaintext)
//   ALLOWED_ORIGIN  — https://prstnk.ru                        (Plaintext)
//   GH_TOKEN        — GitHub token (Contents: read/write)      (Secret)
//   GH_REPO         — bregeadmin/prstnk (по умолчанию)         (необязательно)
//   GH_BRANCH       — main (по умолчанию)                      (необязательно)
//
// Один раз после деплоя открыть: <адрес воркера>/set-webhook
// ============================================================

const STATUS = {
  available: "🟢 снова в наличии",
  reserved: "🟡 забронировано",
  sold: "⚫️ продано",
};

function keyboard(slug) {
  return {
    inline_keyboard: [[
      { text: "🟡 Бронь", callback_data: `set:reserved:${slug}` },
      { text: "🟢 Снять", callback_data: `set:available:${slug}` },
      { text: "⚫️ Продано", callback_data: `set:sold:${slug}` },
    ]],
  };
}

function tg(api, method, body) {
  return fetch(`${api}/${method}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function setArtworkStatus(env, slug, status) {
  const ghToken = env.GH_TOKEN || env.gh_token;
  if (!ghToken) return { ok: false, error: "нет GH_TOKEN" };
  const repo = env.GH_REPO || "bregeadmin/prstnk";
  const branch = env.GH_BRANCH || "main";
  const base = `https://api.github.com/repos/${repo}/contents/data/artworks/${slug}.json`;
  const headers = {
    Authorization: `Bearer ${ghToken}`,
    Accept: "application/vnd.github+json",
    "User-Agent": "prstnk-orders",
  };
  const g = await fetch(`${base}?ref=${branch}`, { headers });
  if (!g.ok) return { ok: false, error: `get ${g.status}` };
  const file = await g.json();
  let obj;
  try {
    const decoded = new TextDecoder().decode(
      Uint8Array.from(atob(file.content.replace(/\n/g, "")), (c) => c.charCodeAt(0))
    );
    obj = JSON.parse(decoded);
  } catch (e) {
    return { ok: false, error: "parse" };
  }
  obj.status = status;
  const text = JSON.stringify(obj, null, 2) + "\n";
  const b64 = btoa(String.fromCharCode(...new TextEncoder().encode(text)));
  const p = await fetch(base, {
    method: "PUT",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify({
      message: `Статус ${slug} → ${status} (из Telegram)`,
      content: b64,
      sha: file.sha,
      branch,
    }),
  });
  if (!p.ok) return { ok: false, error: `put ${p.status}` };
  return { ok: true };
}

export default {
  async fetch(request, env) {
    const TOKEN = env.BOT_TOKEN || env.bot_token;
    const CHAT = env.CHAT_ID || env.chat_id;
    const origin = env.ALLOWED_ORIGIN || env.allowed_origin || "*";
    const cors = {
      "Access-Control-Allow-Origin": origin,
      "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };
    if (request.method === "OPTIONS") return new Response(null, { headers: cors });

    const url = new URL(request.url);
    const api = `https://api.telegram.org/bot${TOKEN}`;
    const jsonResp = (o, status = 200) =>
      new Response(JSON.stringify(o), { status, headers: { ...cors, "Content-Type": "application/json" } });

    // Однократная привязка вебхука к этому воркеру
    if (request.method === "GET" && url.pathname === "/set-webhook") {
      const hook = `${url.origin}/`;
      const r = await fetch(
        `${api}/setWebhook?url=${encodeURIComponent(hook)}&allowed_updates=${encodeURIComponent('["callback_query"]')}`
      );
      return jsonResp(await r.json());
    }
    if (request.method === "GET" && url.pathname === "/chatid") {
      const r = await fetch(`${api}/getUpdates`);
      const data = await r.json();
      const chats = (data.result || []).map((u) => {
        const m = u.message || u.channel_post || u.my_chat_member || {};
        const c = m.chat || {};
        return { id: c.id, type: c.type, title: c.title || c.username || "" };
      });
      return jsonResp({ chats });
    }
    if (request.method !== "POST") {
      return new Response("PRSTNK — приём заявок работает.", { headers: cors });
    }

    const ctype = request.headers.get("content-type") || "";

    // ── Вебхук Telegram: нажатие кнопки ──
    if (ctype.includes("application/json")) {
      const update = await request.json().catch(() => null);
      const cq = update && update.callback_query;
      if (!cq) return jsonResp({ ok: true });
      const fromChat = cq.message && cq.message.chat && String(cq.message.chat.id);
      if (fromChat !== String(CHAT)) {
        await tg(api, "answerCallbackQuery", { callback_query_id: cq.id, text: "Нет доступа", show_alert: true });
        return jsonResp({ ok: true });
      }
      const m = (cq.data || "").match(/^set:(available|reserved|sold):(.+)$/);
      if (!m) {
        await tg(api, "answerCallbackQuery", { callback_query_id: cq.id });
        return jsonResp({ ok: true });
      }
      const status = m[1];
      const slug = m[2];
      const res = await setArtworkStatus(env, slug, status);
      await tg(api, "answerCallbackQuery", {
        callback_query_id: cq.id,
        text: res.ok ? `Готово: ${STATUS[status]}` : `Ошибка: ${res.error || ""}`,
        show_alert: !res.ok,
      });
      if (res.ok) {
        const orig = cq.message.text || cq.message.caption || "";
        const baseText = orig.split("\n— статус:")[0];
        const newText = `${baseText}\n— статус: ${STATUS[status]} (на сайте через ~1–2 мин)`;
        const method = cq.message.caption !== undefined ? "editMessageCaption" : "editMessageText";
        const field = method === "editMessageCaption" ? "caption" : "text";
        await tg(api, method, {
          chat_id: CHAT,
          message_id: cq.message.message_id,
          [field]: newText,
          reply_markup: keyboard(slug),
        });
      }
      return jsonResp({ ok: true });
    }

    // ── Заявка с сайта ──
    try {
      const form = await request.formData();
      const type = (form.get("type") || "Заявка").toString();
      const slug = (form.get("slug") || "").toString().trim();
      const labels = {
        name: "Имя", contact: "Связь", phone: "Телефон", city: "Город",
        delivery: "Доставка", work: "Работа", price: "Цена", budget: "Бюджет",
        room: "Комната", size: "Размер стены", comment: "Комментарий", page: "Страница",
      };
      const lines = [`🟥 ${type}`];
      for (const [k, v] of form.entries()) {
        if (k === "photo" || k === "type" || k === "slug") continue;
        const val = (v || "").toString().trim();
        if (val) lines.push(`${labels[k] || k}: ${val}`);
      }
      const text = lines.join("\n").slice(0, 1000);
      const reply_markup = slug ? keyboard(slug) : undefined;
      const photo = form.get("photo");
      let resp;
      if (photo && typeof photo === "object" && photo.size > 0) {
        const fd = new FormData();
        fd.append("chat_id", CHAT);
        fd.append("caption", text);
        fd.append("photo", photo, photo.name || "photo.jpg");
        if (reply_markup) fd.append("reply_markup", JSON.stringify(reply_markup));
        resp = await fetch(`${api}/sendPhoto`, { method: "POST", body: fd });
      } else {
        resp = await tg(api, "sendMessage", { chat_id: CHAT, text, reply_markup });
      }
      const ok = resp.ok;
      return jsonResp({ ok }, ok ? 200 : 502);
    } catch (e) {
      return jsonResp({ ok: false, error: String(e) }, 500);
    }
  },
};
