// ============================================================
// PRSTNK — воркер приёма заявок с сайта → Telegram-группа.
//
// Принимает POST-форму (поля + необязательное фото) со страниц
// prstnk.ru и отправляет ботом в группу «PRSTNK Заявки».
//
// Переменные окружения (Cloudflare → Worker → Settings → Variables):
//   BOT_TOKEN       — токен бота от @BotFather        (тип: Secret)
//   CHAT_ID         — id группы заявок, напр. -1001234567890  (Plaintext)
//   ALLOWED_ORIGIN  — https://prstnk.ru               (Plaintext, для CORS)
//
// Эндпоинты:
//   POST /          — принять заявку (multipart/form-data; поле photo — файл)
//   GET  /chatid    — показать id чатов, которые «видел» бот (помощь в настройке)
// ============================================================

export default {
  async fetch(request, env) {
    const TOKEN = env.BOT_TOKEN || env.bot_token;
    const CHAT = CHAT || env.chat_id;
    const origin = env.ALLOWED_ORIGIN || env.allowed_origin || "*";
    const cors = {
      "Access-Control-Allow-Origin": origin,
      "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: cors });
    }

    const url = new URL(request.url);

    // Подсказка для настройки: какие чаты видел бот
    if (request.method === "GET" && url.pathname === "/chatid") {
      const r = await fetch(`https://api.telegram.org/bot${TOKEN}/getUpdates`);
      const data = await r.json();
      const chats = (data.result || []).map((u) => {
        const m = u.message || u.channel_post || u.my_chat_member || {};
        const c = m.chat || {};
        return { id: c.id, type: c.type, title: c.title || c.username || "" };
      });
      return new Response(JSON.stringify({ chats }, null, 2), {
        headers: { ...cors, "Content-Type": "application/json" },
      });
    }

    if (request.method !== "POST") {
      return new Response("PRSTNK — приём заявок работает.", { headers: cors });
    }

    try {
      const form = await request.formData();
      const type = (form.get("type") || "Заявка").toString();

      const labels = {
        name: "Имя", contact: "Связь", phone: "Телефон", city: "Город",
        delivery: "Доставка", work: "Работа", price: "Цена", budget: "Бюджет",
        room: "Комната", size: "Размер стены", comment: "Комментарий", page: "Страница",
      };
      const lines = [`🟥 ${type}`];
      for (const [k, v] of form.entries()) {
        if (k === "photo" || k === "type") continue;
        const val = (v || "").toString().trim();
        if (val) lines.push(`${labels[k] || k}: ${val}`);
      }
      const text = lines.join("\n").slice(0, 1000);

      const api = `https://api.telegram.org/bot${TOKEN}`;
      const photo = form.get("photo");
      let tgResp;

      if (photo && typeof photo === "object" && photo.size > 0) {
        const tg = new FormData();
        tg.append("chat_id", CHAT);
        tg.append("caption", text);
        tg.append("photo", photo, photo.name || "photo.jpg");
        tgResp = await fetch(`${api}/sendPhoto`, { method: "POST", body: tg });
      } else {
        tgResp = await fetch(`${api}/sendMessage`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ chat_id: CHAT, text }),
        });
      }

      const ok = tgResp.ok;
      return new Response(JSON.stringify({ ok }), {
        status: ok ? 200 : 502,
        headers: { ...cors, "Content-Type": "application/json" },
      });
    } catch (e) {
      return new Response(JSON.stringify({ ok: false, error: String(e) }), {
        status: 500,
        headers: { ...cors, "Content-Type": "application/json" },
      });
    }
  },
};
