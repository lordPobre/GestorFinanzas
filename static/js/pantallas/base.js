  (function () {
    function open(id) {
      var m = document.querySelector(id);
      if (m) { m.classList.add('open'); document.body.style.overflow = 'hidden'; }
    }
    function closeAll() {
      document.querySelectorAll('.modal-overlay.open').forEach(function (m) { m.classList.remove('open'); });
      document.body.style.overflow = '';
    }
    document.addEventListener('click', function (e) {
      if (window.__finappJsCargado) return;
      var o = e.target.closest('[data-open]');
      if (o) { e.preventDefault(); open(o.getAttribute('data-open')); return; }
      if (e.target.closest('[data-close]')) { e.preventDefault(); closeAll(); return; }
      if (e.target.classList.contains('modal-overlay')) closeAll();
    });
    document.addEventListener('keydown', function (e) {
      if (!window.__finappJsCargado && e.key === 'Escape') closeAll();
    });
    window.finappOpen = open;
    window.finappClose = closeAll;
  })();

  try {
    if (localStorage.getItem('finapp.pasos.oculto') === '1') {
      document.documentElement.classList.add('pasos-ocultos');
    }
  } catch (e) {}
