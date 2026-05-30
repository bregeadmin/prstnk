/* ============================================================
   PRSTNK — заглушка «Простенок собирается».
   Закрывает весь сайт оверлеем поверх <head>, без мигания контента.

   ⚙️  ОТКРЫТЬ САЙТ: поставить GATE_ON = false ниже,
       пересобрать (python3 build.py) и задеплоить — заглушка исчезнет везде.

   🔑  Секретный просмотр настоящего сайта:
       prstnk.ru/?open=prstnk-preview  — впустить (запомнится в браузере)
       prstnk.ru/?open=off             — снова показать заглушку
   ============================================================ */
(function () {
  var GATE_ON = true;                 // ← false, чтобы открыть сайт
  var SECRET  = 'prstnk-preview';     // ← секретное слово для просмотра
  var KEY     = 'prstnk_preview';

  // --- секретная ссылка / выход ---
  try {
    var sp = new URLSearchParams(location.search);
    var open = sp.get('open');
    if (open === SECRET)      { localStorage.setItem(KEY, '1'); }
    else if (open === 'off')  { localStorage.removeItem(KEY); }
    if (open !== null) {
      sp.delete('open');
      var qs = sp.toString();
      history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash);
    }
  } catch (e) {}

  if (!GATE_ON) return;
  try { if (localStorage.getItem(KEY) === '1') return; } catch (e) {}

  document.title = 'Простенок собирается';

  var css = '\
html.prstnk-gated, html.prstnk-gated body { overflow: hidden !important; }\
html.prstnk-gated body { display: none !important; }\
.prstnk-gate {\
  position: fixed; inset: 0; z-index: 2147483647;\
  display: flex; flex-direction: column; align-items: center; justify-content: center;\
  text-align: center; padding: 32px;\
  background: var(--paper, #FCFCFB);\
  color: var(--ink, #141413);\
  font-family: var(--f-text, "Onest", system-ui, sans-serif);\
}\
.prstnk-gate__mark { width: 66px; height: 88px; margin-bottom: 34px; }\
.prstnk-gate__mark .w { fill: none; stroke: var(--ink, #141413); stroke-width: 3; }\
.prstnk-gate__mark .p {\
  fill: var(--c-alyi, #FA2A22);\
  animation: prstnk-gate-cycle 12s ease-in-out infinite;\
}\
@keyframes prstnk-gate-cycle {\
  0%{fill:var(--c-alyi,#FA2A22)} 16%{fill:var(--c-limon,#FFCC00)}\
  33%{fill:var(--c-kobalt,#2A4BFF)} 50%{fill:var(--c-hvoya,#2E5A2A)}\
  66%{fill:var(--c-fuxia,#FF3DA0)} 83%{fill:var(--c-ugol,#161614)}\
  100%{fill:var(--c-alyi,#FA2A22)}\
}\
@media (prefers-reduced-motion: reduce){ .prstnk-gate__mark .p{ animation:none } }\
.prstnk-gate__word { font-family: var(--f-display, "Unbounded", sans-serif); font-weight:700;\
  letter-spacing:.22em; font-size:22px; margin-bottom:6px; padding-left:.22em; }\
.prstnk-gate__desc { font-family: var(--f-mono, monospace); font-size:12px; letter-spacing:.08em;\
  color: var(--ink-3, #6E6B61); margin-bottom:48px; }\
.prstnk-gate__head { font-family: var(--f-display, "Unbounded", sans-serif); font-weight:600;\
  font-size: clamp(30px, 7vw, 54px); line-height:1.05; margin:0 0 20px; max-width:14ch; }\
.prstnk-gate__sub { font-size:17px; line-height:1.55; color: var(--ink-2, #38362F);\
  max-width:30ch; margin:0 0 40px; }\
.prstnk-gate__tg { display:inline-flex; align-items:center; gap:9px; font-family: var(--f-mono, monospace);\
  font-size:13px; letter-spacing:.04em; color: var(--ink, #141413); border:1.5px solid var(--ink, #141413);\
  border-radius:999px; padding:12px 22px; text-decoration:none; transition: background .15s, color .15s; }\
.prstnk-gate__tg:hover { background: var(--ink, #141413); color: var(--paper, #FCFCFB); }\
.prstnk-gate__foot { position:absolute; bottom:28px; left:0; right:0; font-family: var(--f-mono, monospace);\
  font-size:11px; letter-spacing:.06em; color: var(--ink-3, #6E6B61); }';

  var markup = '\
<div class="prstnk-gate" role="dialog" aria-label="Простенок собирается">\
  <svg class="prstnk-gate__mark" viewBox="0 0 60 80" aria-hidden="true">\
    <rect class="w" x="2" y="2" width="9" height="76"/>\
    <rect class="p" x="13" y="0" width="34" height="80"/>\
    <rect class="w" x="49" y="2" width="9" height="76"/>\
  </svg>\
  <div class="prstnk-gate__word">PRSTNK</div>\
  <div class="prstnk-gate__desc">[ простенок ]</div>\
  <h1 class="prstnk-gate__head">Простенок собирается</h1>\
  <p class="prstnk-gate__sub">Витрина авторской печатной графики петербургских художников. Скоро откроем — сейчас наводим порядок.</p>\
  <a class="prstnk-gate__tg" href="https://t.me/prstnk_store" target="_blank" rel="noopener">Написать в Telegram →</a>\
  <div class="prstnk-gate__foot">prstnk.ru · Санкт-Петербург</div>\
</div>';

  document.documentElement.className += ' prstnk-gated';

  var style = document.createElement('style');
  style.textContent = css;
  document.documentElement.appendChild(style);

  function mount() {
    var wrap = document.createElement('div');
    wrap.innerHTML = markup;
    document.documentElement.appendChild(wrap.firstChild);
  }
  if (document.body) mount();
  else document.addEventListener('DOMContentLoaded', mount);
})();
