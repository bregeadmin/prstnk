/* PRSTNK — минимальный JS */

(() => {
  /* --- Чистый адрес: если зашли по старой ссылке с .html, убираем
         расширение из адресной строки (страница та же, GitHub Pages
         отдаёт и /journal, и /journal.html). /index.html → /. --- */
  if (location.pathname.endsWith('.html')) {
    let clean = location.pathname.slice(0, -5);   // отрезаем ".html"
    if (clean === '/index') clean = '/';
    history.replaceState(null, '', clean + location.search + location.hash);
  }

  // ────────────────────────────────────────────────
  // Telegram-юзернейм. Меняется в одном месте.
  // ────────────────────────────────────────────────
  const TG_USER = 'prstnk_store';

  /* --- Все ссылки с data-tg-text автоматически собираются
         в https://t.me/<user>?text=<encoded>. Юзернейм меняется
         в одном месте выше; шаблон работает для любой страницы. --- */
  document.querySelectorAll('[data-tg-text]').forEach(el => {
    const text = el.dataset.tgText || '';
    const href = `https://t.me/${TG_USER}?text=${encodeURIComponent(text)}`;
    el.setAttribute('href', href);
    el.setAttribute('target', '_blank');
    el.setAttribute('rel', 'noopener');
  });

  /* --- Универсальная кнопка контакта без текста — просто открыть чат --- */
  document.querySelectorAll('[data-tg-open]').forEach(el => {
    el.setAttribute('href', `https://t.me/${TG_USER}`);
    el.setAttribute('target', '_blank');
    el.setAttribute('rel', 'noopener');
  });

  /* --- Mobile menu toggle --- */
  const toggle = document.querySelector('.menu-toggle');
  const nav = document.querySelector('.nav');
  if (toggle && nav) {
    toggle.addEventListener('click', () => {
      const willOpen = !nav.classList.contains('is-open');
      nav.classList.toggle('is-open', willOpen);
      toggle.setAttribute('aria-expanded', String(willOpen));
      document.body.style.overflow = willOpen ? 'hidden' : '';
    });
    nav.addEventListener('click', (e) => {
      if (e.target.tagName === 'A') {
        nav.classList.remove('is-open');
        toggle.setAttribute('aria-expanded', 'false');
        document.body.style.overflow = '';
      }
    });
  }

  /* --- Section color: при наведении на пункт навигации
         меняем цвет «простенка» в знаке. Тихо и дорого, не аттракцион. --- */
  const COLORS = {
    'Каталог':   'var(--c-alyi)',
    'Подбор':    'var(--c-kobalt)',
    'Подарки':   'var(--c-fuxia)',
    'Художники': 'var(--c-hvoya)',
    'Журнал':    'var(--c-limon)',
  };
  const root = document.documentElement;
  const defaultColor = getComputedStyle(root).getPropertyValue('--prstnk-color').trim() || '#FA2A22';
  document.querySelectorAll('.nav a').forEach(a => {
    const label = (a.textContent || '').trim();
    const col = COLORS[label];
    if (!col) return;
    a.addEventListener('mouseenter', () => root.style.setProperty('--prstnk-color', col));
    a.addEventListener('mouseleave', () => root.style.setProperty('--prstnk-color', defaultColor));
    a.addEventListener('focus',     () => root.style.setProperty('--prstnk-color', col));
    a.addEventListener('blur',      () => root.style.setProperty('--prstnk-color', defaultColor));
  });

  /* --- Entry animation: staggered показ работ + герой --- */
  const els = document.querySelectorAll('.stagger');
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const delay = parseFloat(entry.target.dataset.stagDelay || 0);
          entry.target.style.animationDelay = `${delay}s`;
          entry.target.classList.add('in');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -60px 0px' });
    els.forEach(el => io.observe(el));
  } else {
    els.forEach(el => el.classList.add('in'));
  }

  /* --- Hover на карточке работы: цвет простенка временно подкрашивается
         под акцент конкретной работы (data-work-color) --- */
  document.querySelectorAll('[data-work-color]').forEach(card => {
    const col = card.dataset.workColor;
    if (!col) return;
    card.addEventListener('mouseenter', () => root.style.setProperty('--prstnk-color', col));
    card.addEventListener('mouseleave', () => root.style.setProperty('--prstnk-color', defaultColor));
  });

  /* --- Каталог: фильтры + сортировка + поиск (works.html) --- */
  const grid = document.getElementById('catGrid');
  if (grid) {
    const cards = Array.from(grid.querySelectorAll('.work'));
    const techChips = Array.from(document.querySelectorAll('.catalog-filter__chip[data-group="tech"]'));
    const toggleChips = Array.from(document.querySelectorAll('.catalog-filter__chip[data-toggle]'));
    const searchInput = document.getElementById('catSearch');
    const sortSelect = document.getElementById('catSort');
    const countEl = document.getElementById('catCount');
    const resetBtn = document.getElementById('catReset');
    const emptyEl = document.getElementById('catEmpty');
    const total = cards.length;
    let tech = 'all';
    const toggles = { available: false, under10k: false, unique: false, last: false };

    const num = (c, key) => Number(c.dataset[key] || 0);

    function matches(c) {
      if (tech !== 'all' && c.dataset.technique !== tech) return false;
      if (toggles.available && c.dataset.status !== 'available') return false;
      if (toggles.under10k && num(c, 'price') > 10000) return false;
      if (toggles.unique && c.dataset.type !== 'unique') return false;
      if (toggles.last && !(c.dataset.type === 'editioned' && num(c, 'available') <= 1 && c.dataset.status === 'available')) return false;
      const q = (searchInput ? searchInput.value : '').trim().toLowerCase();
      if (q && !(c.dataset.search || '').includes(q)) return false;
      return true;
    }

    function anyActive() {
      return tech !== 'all' || toggles.available || toggles.under10k || toggles.unique ||
             toggles.last || (searchInput && searchInput.value.trim() !== '') ||
             (sortSelect && sortSelect.value !== 'curated');
    }

    function apply() {
      let shown = 0;
      cards.forEach(c => {
        const ok = matches(c);
        c.style.display = ok ? '' : 'none';
        if (ok) shown++;
      });
      const mode = sortSelect ? sortSelect.value : 'curated';
      cards.filter(c => c.style.display !== 'none').sort((a, b) => {
        if (mode === 'price-asc') return num(a, 'price') - num(b, 'price');
        if (mode === 'price-desc') return num(b, 'price') - num(a, 'price');
        if (mode === 'new') return num(b, 'year') - num(a, 'year') || num(a, 'order') - num(b, 'order');
        return num(a, 'order') - num(b, 'order');
      }).forEach(c => grid.appendChild(c));
      if (countEl) countEl.textContent = `Показано ${shown} из ${total}`;
      if (emptyEl) emptyEl.hidden = shown !== 0;
      if (resetBtn) resetBtn.hidden = !anyActive();
    }

    techChips.forEach(chip => chip.addEventListener('click', () => {
      tech = chip.dataset.filter;
      techChips.forEach(c => c.classList.toggle('is-active', c === chip));
      apply();
    }));
    toggleChips.forEach(chip => chip.addEventListener('click', () => {
      const key = chip.dataset.toggle;
      toggles[key] = !toggles[key];
      chip.classList.toggle('is-active', toggles[key]);
      apply();
    }));
    if (searchInput) searchInput.addEventListener('input', apply);
    if (sortSelect) sortSelect.addEventListener('change', apply);
    if (resetBtn) resetBtn.addEventListener('click', () => {
      tech = 'all';
      Object.keys(toggles).forEach(k => (toggles[k] = false));
      techChips.forEach(c => c.classList.toggle('is-active', c.dataset.filter === 'all'));
      toggleChips.forEach(c => c.classList.remove('is-active'));
      if (searchInput) searchInput.value = '';
      if (sortSelect) sortSelect.value = 'curated';
      apply();
    });

    apply();
  }

  /* --- Заявки: модальная форма (покупка / подбор по фото) → Cloudflare-воркер → Telegram --- */
  const ORDERS_URL = 'https://prstnk-orders.grinbergartgroup.workers.dev';
  const escAttr = (s) => (s || '').toString().replace(/&/g, '&amp;').replace(/"/g, '&quot;');

  const PURCHASE_FIELDS = `
    <label class="field"><span>Имя *</span><input name="name" required autocomplete="name"></label>
    <label class="field"><span>Телефон или Telegram *</span><input name="phone" required placeholder="+7… или @ник"></label>
    <label class="field"><span>Город</span><input name="city"></label>
    <label class="field"><span>Доставка</span><select name="delivery"><option>Самовывоз (Санкт-Петербург)</option><option>СДЭК</option><option>Почта России</option><option>Уточнить при заказе</option></select></label>
    <label class="field"><span>Комментарий</span><textarea name="comment" rows="2"></textarea></label>`;
  const FIT_FIELDS = `
    <label class="field"><span>Фото стены</span><input type="file" name="photo" accept="image/*"></label>
    <label class="field"><span>Размер стены</span><input name="size" placeholder="напр. 150 × 200 см"></label>
    <label class="field"><span>Бюджет</span><input name="budget" placeholder="напр. до 30 000 ₽"></label>
    <label class="field"><span>Про комнату и пожелания</span><textarea name="room" rows="2"></textarea></label>
    <label class="field"><span>Имя *</span><input name="name" required></label>
    <label class="field"><span>Телефон или Telegram *</span><input name="phone" required placeholder="+7… или @ник"></label>`;
  const CERT_FIELDS = `
    <div class="field">
      <span>Сумма сертификата (₽) *</span>
      <div class="cert-amounts">
        <button type="button" data-amount="5000">5 000</button>
        <button type="button" data-amount="10000">10 000</button>
        <button type="button" data-amount="20000">20 000</button>
        <button type="button" data-amount="50000">50 000</button>
      </div>
      <input name="amount" type="number" min="1000" step="500" placeholder="или впишите свою сумму" required inputmode="numeric">
    </div>
    <label class="field"><span>Кому (имя получателя)</span><input name="recipient" autocomplete="off"></label>
    <label class="field"><span>Текст для открытки</span><textarea name="message" rows="2" placeholder="напр. С днём рождения!"></textarea></label>
    <label class="field"><span>Ваше имя *</span><input name="name" required autocomplete="name"></label>
    <label class="field"><span>Телефон или Telegram *</span><input name="phone" required placeholder="+7… или @ник"></label>`;

  let modal;
  function ensureModal() {
    if (modal) return modal;
    modal = document.createElement('div');
    modal.className = 'modal';
    modal.hidden = true;
    modal.innerHTML = `
      <div class="modal__overlay" data-close></div>
      <div class="modal__dialog" role="dialog" aria-modal="true" aria-labelledby="orderTitle">
        <button class="modal__close" data-close aria-label="Закрыть" type="button">✕</button>
        <div class="eyebrow" id="orderEyebrow">Заявка</div>
        <h3 class="modal__title" id="orderTitle">Оформить заявку</h3>
        <p class="modal__sub" id="orderSub" hidden></p>
        <form class="modal__form" id="orderForm">
          <div id="orderFields"></div>
          <button type="submit" class="btn btn--big btn--accent" id="orderSubmit">Отправить заявку</button>
          <p class="modal__alt">или <a id="orderTg" target="_blank" rel="noopener">написать в Telegram</a></p>
          <div class="modal__status" id="orderStatus" hidden></div>
        </form>
        <div class="modal__done" id="orderDone" hidden>
          <h3>Спасибо! Заявка отправлена.</h3>
          <p>Ответим в течение дня — в Telegram или по телефону.</p>
          <button type="button" class="btn btn--accent" data-close>Закрыть</button>
        </div>
      </div>`;
    document.body.appendChild(modal);
    modal.addEventListener('click', (e) => {
      if (e.target.hasAttribute('data-close')) { closeModal(); return; }
      const ab = e.target.closest('button[data-amount]');
      if (ab) {
        e.preventDefault();
        const input = modal.querySelector('input[name=amount]');
        if (input) input.value = ab.dataset.amount;
        modal.querySelectorAll('.cert-amounts button').forEach(b => b.classList.toggle('is-active', b === ab));
      }
    });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !modal.hidden) closeModal(); });
    modal.querySelector('#orderForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const form = e.currentTarget;
      if (!form.checkValidity()) { form.reportValidity(); return; }
      const btn = modal.querySelector('#orderSubmit');
      const status = modal.querySelector('#orderStatus');
      btn.disabled = true;
      status.hidden = false; status.className = 'modal__status'; status.textContent = 'Отправляем…';
      try {
        const r = await fetch(ORDERS_URL, { method: 'POST', body: new FormData(form) });
        const d = await r.json().catch(() => ({ ok: false }));
        if (!d.ok) throw new Error('fail');
        form.hidden = true;
        modal.querySelector('#orderDone').hidden = false;
      } catch (err) {
        status.className = 'modal__status modal__status--err';
        status.textContent = 'Не отправилось. Попробуйте ещё раз или напишите в Telegram.';
        btn.disabled = false;
      }
    });
    return modal;
  }

  function closeModal() { if (modal) { modal.hidden = true; document.body.style.overflow = ''; } }

  function openOrder(opts) {
    ensureModal();
    const fit = opts.mode === 'fit';
    const cert = opts.mode === 'cert';
    modal.querySelector('#orderEyebrow').textContent = cert ? 'Подарочный сертификат' : (fit ? 'Подбор куратора' : 'Заявка');
    modal.querySelector('#orderTitle').textContent = cert ? 'Оформить сертификат' : (fit ? 'Подбор по фото стены' : 'Оформить заявку');
    const sub = modal.querySelector('#orderSub');
    if (cert) {
      sub.hidden = false;
      sub.textContent = 'Сертификат на любую сумму. Получатель сам выбирает работу из каталога. Срок действия — год.';
    } else if (fit) {
      sub.hidden = false;
      sub.textContent = 'Пришлите фото стены — куратор подберёт 3–5 листов по размеру, цвету и настроению. Бесплатно.';
    } else if (opts.work) {
      sub.hidden = false;
      sub.innerHTML = `<b>${escAttr(opts.work)}</b>` + (opts.price ? ` · ${escAttr(opts.price)}` : '');
    } else { sub.hidden = true; }
    const hidden = `<input type="hidden" name="type" value="${escAttr(opts.type)}"><input type="hidden" name="page" value="${escAttr(location.href)}">`
      + (opts.work ? `<input type="hidden" name="work" value="${escAttr(opts.work)}">` : '')
      + (opts.price ? `<input type="hidden" name="price" value="${escAttr(opts.price)}">` : '')
      + (opts.slug ? `<input type="hidden" name="slug" value="${escAttr(opts.slug)}">` : '');
    modal.querySelector('#orderFields').innerHTML = hidden + (cert ? CERT_FIELDS : (fit ? FIT_FIELDS : PURCHASE_FIELDS));
    const form = modal.querySelector('#orderForm');
    form.hidden = false;
    modal.querySelector('#orderDone').hidden = true;
    modal.querySelector('#orderStatus').hidden = true;
    modal.querySelector('#orderSubmit').disabled = false;
    modal.querySelector('#orderTg').href = `https://t.me/${TG_USER}?text=${encodeURIComponent(opts.tgText || 'Здравствуйте! Хочу оставить заявку на сайте PRSTNK.')}`;
    modal.hidden = false;
    document.body.style.overflow = 'hidden';
    const first = modal.querySelector('#orderFields input:not([type=hidden]), #orderFields select');
    if (first) first.focus();
  }

  document.addEventListener('click', (e) => {
    const ob = e.target.closest('[data-buy]');
    if (ob) { e.preventDefault(); openOrder({ mode: 'purchase', type: ob.dataset.buyType || 'Заявка на покупку', work: ob.dataset.work, price: ob.dataset.price, slug: ob.dataset.lotSlug, tgText: ob.dataset.tgText }); return; }
    const fb = e.target.closest('[data-fit]');
    if (fb) { e.preventDefault(); openOrder({ mode: 'fit', type: 'Подбор по фото стены', tgText: fb.dataset.tgText }); return; }
    const cb = e.target.closest('[data-cert]');
    if (cb) { e.preventDefault(); openOrder({ mode: 'cert', type: 'Подарочный сертификат', tgText: cb.dataset.tgText }); }
  });

  /* --- Избранное (♡): хранится в памяти браузера (localStorage) --- */
  const FAV_KEY = 'prstnk_fav';
  const getFavs = () => { try { return JSON.parse(localStorage.getItem(FAV_KEY)) || []; } catch (e) { return []; } };
  const setFavs = (a) => { try { localStorage.setItem(FAV_KEY, JSON.stringify(a)); } catch (e) {} };

  function paintFav(slug, on) {
    document.querySelectorAll(`[data-fav-toggle][data-fav-slug="${slug}"]`).forEach((b) => {
      b.classList.toggle('is-faved', on);
      b.setAttribute('aria-pressed', String(on));
      b.textContent = on ? '♥' : '♡';
    });
  }

  function initFavButtons() {
    const favs = getFavs();
    document.querySelectorAll('[data-fav-toggle][data-fav-slug]').forEach((b) => {
      paintFav(b.dataset.favSlug, favs.includes(b.dataset.favSlug));
    });
  }

  function updateFab() {
    const n = getFavs().length;
    const onFavPage = !!document.getElementById('favGrid');
    let fab = document.getElementById('favFab');
    if (n === 0 || onFavPage) { if (fab) fab.hidden = true; return; }
    if (!fab) {
      fab = document.createElement('a');
      fab.id = 'favFab'; fab.className = 'fav-fab'; fab.href = 'favorites.html';
      document.body.appendChild(fab);
    }
    fab.hidden = false;
    fab.innerHTML = `♥ Избранное <span>${n}</span>`;
  }

  function renderFavorites() {
    const grid = document.getElementById('favGrid');
    if (!grid) return;
    const empty = document.getElementById('favEmpty');
    const data = window.PRSTNK_WORKS || {};
    const favs = getFavs().filter((s) => data[s]);
    grid.innerHTML = favs.length ? favs.map((s) => data[s]).join('\n') : '';
    if (empty) empty.hidden = favs.length > 0;
    const countEl = document.getElementById('favCount');
    if (countEl) countEl.textContent = favs.length;
    initFavButtons();
  }

  document.addEventListener('click', (e) => {
    const f = e.target.closest('[data-fav-toggle]');
    if (!f) return;
    e.preventDefault();
    const slug = f.dataset.favSlug;
    if (!slug) return;
    const arr = getFavs();
    const i = arr.indexOf(slug);
    if (i >= 0) arr.splice(i, 1); else arr.push(slug);
    setFavs(arr);
    paintFav(slug, arr.includes(slug));
    updateFab();
    if (document.getElementById('favGrid')) renderFavorites();
  });

  initFavButtons();
  updateFab();
  renderFavorites();
})();
