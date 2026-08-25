/* ============================================================
   FinApp · Interacciones de la capa glass
   Sin dependencias. Cargar al final del <body>.
   ============================================================ */
(function () {
  'use strict';

  /* --- 1. Luz que sigue el cursor sobre [data-spot] --- */
  var canHover = window.matchMedia('(hover: hover)').matches;
  if (canHover) {
    document.addEventListener('mousemove', function (e) {
      var el = e.target.closest && e.target.closest('[data-spot]');
      if (!el) return;
      var r = el.getBoundingClientRect();
      el.style.setProperty('--mx', (e.clientX - r.left) + 'px');
      el.style.setProperty('--my', (e.clientY - r.top) + 'px');
      el.style.backgroundImage =
        'radial-gradient(480px circle at var(--mx) var(--my), rgba(167,139,250,.13), transparent 45%)';
    });
    document.addEventListener('mouseleave', function (e) {
      var el = e.target.closest && e.target.closest('[data-spot]');
      if (el) el.style.backgroundImage = 'none';
    }, true);
  }

  /* --- 2. Modales y paneles: data-open="#id" / data-close --- */
  function open(id) {
    var m = document.querySelector(id);
    if (m) { m.classList.add('open'); document.body.style.overflow = 'hidden'; }
  }
  function closeAll() {
    document.querySelectorAll('.modal-overlay.open').forEach(function (m) { m.classList.remove('open'); });
    document.body.style.overflow = '';
  }
  window.finappOpen = open;
  window.finappClose = closeAll;

  document.addEventListener('click', function (e) {
    var opener = e.target.closest('[data-open]');
    if (opener) { e.preventDefault(); open(opener.getAttribute('data-open')); return; }
    if (e.target.closest('[data-close]')) { e.preventDefault(); closeAll(); return; }
    if (e.target.classList.contains('modal-overlay')) closeAll();
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeAll(); });

  /* --- 3. Teclado numérico del panel de registro ---
     <div data-keypad data-target="#id_monto" data-display="#montoView"></div>  */
  document.querySelectorAll('[data-keypad]').forEach(function (pad) {
    var input = document.querySelector(pad.dataset.target);
    var view = document.querySelector(pad.dataset.display);
    var val = (input && input.value) || '';
    var fmt = function (n) { return n ? '$' + Number(n).toLocaleString('es-CL') : '$0'; };
    var paint = function () {
      if (input) input.value = val;
      if (view) view.textContent = fmt(val);
      pad.dispatchEvent(new CustomEvent('keypad:change', { bubbles: true, detail: { value: Number(val || 0) } }));
    };
    pad.addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      e.preventDefault();
      var k = b.dataset.key;
      if (k === 'del') val = val.slice(0, -1);
      else if (val.length <= 8) val = (val + k).replace(/^0+/, '');
      paint();
    });
    paint();
  });

  /* --- 4. Vista previa del impacto: recalcula "te queda libre" ---
     <span data-preview data-base="238700" data-dias="11" data-sign="-1"></span> */
  document.addEventListener('keypad:change', function (e) {
    document.querySelectorAll('[data-preview]').forEach(function (el) {
      var base = Number(el.dataset.base || 0);
      var sign = Number(el.dataset.sign || -1);
      var dias = Number(el.dataset.dias || 1);
      var v = base + sign * e.detail.value;
      el.textContent = '$' + Math.round(v).toLocaleString('es-CL');
      el.style.color = v < 0 ? '#fb7185' : '#f1f0ff';
      var perDia = el.parentElement.querySelector('[data-preview-dia]');
      if (perDia) perDia.textContent = '$' + Math.round(v / dias).toLocaleString('es-CL');
    });
  });

  /* --- 5. Segmentados y chips: marcan .on y rellenan un input oculto ---
     <div class="chips" data-field="#id_categoria"><button class="chip" data-value="Comida">…</button></div> */
  document.querySelectorAll('[data-field]').forEach(function (group) {
    var input = document.querySelector(group.dataset.field);
    group.addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      e.preventDefault();
      group.querySelectorAll('button').forEach(function (x) { x.classList.remove('on'); });
      b.classList.add('on');
      if (input) { input.value = b.dataset.value; input.dispatchEvent(new Event('change', { bubbles: true })); }
    });
  });

  /* --- 6. Barras y pips animan al entrar en pantalla --- */
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) {
      if (!en.isIntersecting) return;
      var el = en.target;
      if (el.classList.contains('progress-fill')) {
        var w = el.dataset.width || el.style.width;
        el.style.width = '0%';
        requestAnimationFrame(function () { el.style.width = w; });
      }
      io.unobserve(el);
    });
  }, { threshold: .2 });
  document.querySelectorAll('.progress-fill').forEach(function (el) {
    el.dataset.width = el.style.width; io.observe(el);
  });

  /* --- 7. Toasts se van solos --- */
  setTimeout(function () {
    document.querySelectorAll('.toast').forEach(function (t) {
      t.style.transition = 'opacity .4s, transform .4s';
      t.style.opacity = '0'; t.style.transform = 'translateX(20px)';
      setTimeout(function () { t.remove(); }, 400);
    });
  }, 3800);

  /* --- 8. Confirmación antes de borrar: data-confirm="texto" --- */
  document.addEventListener('submit', function (e) {
    var f = e.target.closest('form[data-confirm]');
    if (f && !window.confirm(f.dataset.confirm)) e.preventDefault();
  });

  /* --- 9. Buscador del topbar filtra filas .row de la página --- */
  var search = document.querySelector('[data-search]');
  if (search) {
    search.addEventListener('input', function () {
      var q = search.value.toLowerCase().trim();
      document.querySelectorAll('[data-searchable]').forEach(function (row) {
        row.style.display = !q || row.textContent.toLowerCase().indexOf(q) > -1 ? '' : 'none';
      });
    });
  }
})();
