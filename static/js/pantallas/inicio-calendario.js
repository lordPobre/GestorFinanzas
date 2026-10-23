(function () {
  var modal = document.getElementById('modalCalendario');
  if (!modal || !modal.dataset.fragmento) return;
  var pedido = null;

  function avisar(texto) {
    var estado = modal.querySelector('[data-calendario-estado]');
    if (estado) estado.textContent = texto;
  }

  function cargar() {
    if (pedido || modal.dataset.cargado) return;
    avisar('Cargando…');
    pedido = fetch(modal.dataset.fragmento, { credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' } })
      .then(function (r) {
        if (!r.ok || r.redirected) throw new Error(String(r.status));
        return r.text();
      })
      .then(function (html) {
        var tpl = document.createElement('template');
        tpl.innerHTML = html;
        var caja = tpl.content.querySelector('[data-calendario-caja]');
        var actual = modal.querySelector('.modal-box');
        if (!caja || !actual) throw new Error('fragmento');
        var dias = Array.prototype.slice.call(tpl.content.querySelectorAll('.modal-overlay'));
        actual.replaceWith(caja);
        var despues = modal;
        dias.forEach(function (m) { despues.after(m); despues = m; });
        modal.dataset.cargado = '1';
        if (modal.classList.contains('open')) {
          var cerrar = caja.querySelector('[data-close]');
          if (cerrar) cerrar.focus();
        }
      })
      .catch(function () {
        avisar('No se pudo cargar. Cierra y vuelve a abrirlo.');
      })
      .then(function () { pedido = null; });
  }

  function abridor(e) {
    return e.target.closest && e.target.closest('[data-open="#modalCalendario"]');
  }

  document.addEventListener('pointerover', function (e) { if (abridor(e)) cargar(); }, { passive: true });
  document.addEventListener('focusin', function (e) { if (abridor(e)) cargar(); });
  document.addEventListener('click', function (e) { if (abridor(e)) cargar(); }, true);
})();
