(function () {
  'use strict';

  var hoja = document.getElementById('modalMovimientos');
  if (!hoja || !window.fetch || !window.FormData) return;
  var sucio = false;

  function cerrarCarril(fila) {
    if (!fila) return;
    fila.classList.remove('abierta', 'abierta-izq', 'abierta-der');
    var card = fila.querySelector('.swipe-card');
    if (card) card.style.transform = '';
  }

  function recontar() {
    if (window.finappMovimientos) window.finappMovimientos.recontar();
  }

  function quitar(fila) {
    if (!fila) return;
    var listo = function () { fila.remove(); recontar(); };
    if (fila.animate) {
      fila.animate([{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateX(-24px)' }],
        { duration: 180, easing: 'ease-in' }).onfinish = listo;
    } else {
      listo();
    }
  }

  function marcarPago(fila, form, pagado) {
    if (!fila) return;
    fila.classList.toggle('sin-pagar', !pagado);
    var icono = fila.querySelector('.mv-icono');
    if (icono) icono.classList.toggle('sin-pagar', !pagado);
    var meta = fila.querySelector('.mv-meta');
    if (meta) {
      meta.classList.toggle('sin-pagar', !pagado);
      var texto = meta.textContent.replace(/^\s*Sin pagar · /, '');
      meta.textContent = pagado ? texto : 'Sin pagar · ' + texto;
    }
    form.remove();
    cerrarCarril(fila);
  }

  function enviarNormal(form) {
    form.removeAttribute('data-sin-recargar');
    form.dataset.confirmado = '1';
    HTMLFormElement.prototype.submit.call(form);
  }

  hoja.addEventListener('submit', function (e) {
    var form = e.target;
    if (e.defaultPrevented || !form.matches || !form.matches('form[data-sin-recargar]')) return;
    if (form.hasAttribute('data-confirm') && !form.dataset.confirmado) return;
    e.preventDefault();

    var accion = form.getAttribute('data-sin-recargar');
    var fila = form.closest('.swipe');
    fetch(form.action, {
      method: 'POST',
      body: new FormData(form),
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' },
    }).then(function (r) {
      if (!r.ok) throw new Error('respuesta ' + r.status);
      return r.json();
    }).then(function (datos) {
      if (!datos || !datos.ok) throw new Error('sin ok');
      sucio = true;
      if (accion === 'eliminar') quitar(fila);
      else marcarPago(fila, form, accion === 'pagar');
    }).catch(function () {
      enviarNormal(form);
    });
  });

  new MutationObserver(function () {
    if (!sucio || hoja.classList.contains('open')) return;
    sucio = false;
    if (window.finappRecargarAqui) window.finappRecargarAqui();
    else location.reload();
  }).observe(hoja, { attributes: true, attributeFilter: ['class'] });
})();
