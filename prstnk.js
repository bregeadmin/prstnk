/* PRSTNK — минимальный JS */

(() => {
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

  /* --- Каталог: фильтр-чипы по технике (works.html) --- */
  const chips = document.querySelectorAll('.catalog-filter__chip');
  const sections = document.querySelectorAll('[data-technique]');
  if (chips.length && sections.length) {
    chips.forEach(chip => {
      chip.addEventListener('click', () => {
        const filter = chip.dataset.filter;
        chips.forEach(c => c.classList.toggle('is-active', c === chip));
        sections.forEach(s => {
          s.style.display = (filter === 'all' || s.dataset.technique === filter) ? '' : 'none';
        });
      });
    });
  }
})();
