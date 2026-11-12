(function () {
  var abierto = null;
  var origen = null;

  function enfocables(raiz) {
    return Array.prototype.filter.call(raiz.querySelectorAll('button, [href], input:not([type=hidden])'),
      function (el) { return !el.disabled && el.offsetParent !== null; });
  }

  function abrir(panel) {
    origen = panel.parentNode;
    document.body.appendChild(panel);
    panel.hidden = false;
    abierto = panel;
    var cancelar = panel.querySelector('.bm2c-cancelar');
    if (cancelar) cancelar.focus();
  }

  function cerrar() {
    if (!abierto) return;
    var panel = abierto;
    abierto = null;
    panel.hidden = true;
    if (origen && origen.isConnected) origen.appendChild(panel);
    else panel.remove();
    var boton = origen && origen.querySelector('[data-borrar-mes-abrir]');
    if (boton) boton.focus();
  }

  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('[data-borrar-mes-abrir]');
    if (a) {
      e.preventDefault();
      var caja = a.closest('[data-movimientos-caja]');
      var panel = caja && caja.querySelector('[data-borrar-mes]');
      if (panel) abrir(panel);
      return;
    }
    if (abierto && e.target.closest && e.target.closest('[data-borrar-mes-cerrar]')) {
      e.preventDefault();
      cerrar();
    }
  });

  document.addEventListener('keydown', function (e) {
    if (!abierto) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      cerrar();
      return;
    }
    if (e.key !== 'Tab') return;
    var lista = enfocables(abierto);
    if (!lista.length) return;
    e.stopPropagation();
    var primero = lista[0];
    var ultimo = lista[lista.length - 1];
    if (e.shiftKey && document.activeElement === primero) { e.preventDefault(); ultimo.focus(); }
    else if (!e.shiftKey && document.activeElement === ultimo) { e.preventDefault(); primero.focus(); }
    else if (!abierto.contains(document.activeElement)) { e.preventDefault(); primero.focus(); }
  }, true);

  var aviso = document.querySelector('[data-borrado-aviso]');
  if (!aviso) return;
  var quieto = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var quitar = function () {
    aviso.classList.add('fuera');
    setTimeout(function () { aviso.remove(); }, quieto ? 0 : 300);
  };
  var reloj = setTimeout(quitar, 10000);
  var barra = aviso.querySelector('[data-borrado-barra]');
  if (barra && barra.animate && !quieto) {
    barra.animate([{ transform: 'scaleX(1)' }, { transform: 'scaleX(0)' }],
      { duration: 10000, easing: 'linear', fill: 'forwards' });
  }
  aviso.addEventListener('submit', function () { clearTimeout(reloj); });
})();
