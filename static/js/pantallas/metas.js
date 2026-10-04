document.addEventListener('click', function (e) {
  var chip = e.target.closest('[data-montos] > button');
  if (chip) {
    e.preventDefault();
    var grupo = chip.parentElement;
    var campo = document.querySelector(grupo.dataset.montos);
    grupo.querySelectorAll('button').forEach(function (b) { b.classList.remove('on'); });
    chip.classList.add('on');
    if (campo) { campo.value = chip.dataset.monto; campo.focus(); }
    return;
  }

  var col = e.target.closest('.aporte-col');
  if (col) {
    e.preventDefault();
    var abierta = col.classList.contains('on');
    col.closest('.aportes-chart')
       .querySelectorAll('.aporte-col.on')
       .forEach(function (c) { c.classList.remove('on'); });
    if (!abierta) col.classList.add('on');
    return;
  }

  document.querySelectorAll('.aporte-col.on').forEach(function (c) {
    c.classList.remove('on');
  });
});

(function () {
  if (!('IntersectionObserver' in window)) return;
  var pendientes = document.querySelectorAll('.meta-card');
  if (!pendientes.length) return;

  pendientes.forEach(function (card) {

    card.querySelectorAll('.progress-fill.viva, .aporte-barra')
        .forEach(function (el) { el.style.animationPlayState = 'paused'; });
  });

  var obs = new IntersectionObserver(function (entradas) {
    entradas.forEach(function (en) {
      if (!en.isIntersecting) return;
      en.target.querySelectorAll('.progress-fill.viva, .aporte-barra')
               .forEach(function (el) { el.style.animationPlayState = ''; });
      obs.unobserve(en.target);
    });
  }, { threshold: .25 });

  pendientes.forEach(function (card) { obs.observe(card); });
})();

(function () {
  document.querySelectorAll('[data-meta-rapido]').forEach(function (f) {
    var card = f.closest('.me-card');
    var orbita = card ? card.querySelector('.me-orbita') : null;
    var despues = card ? card.querySelector('[data-meta-despues]') : null;
    var campo = f.querySelector('input[name="monto"]');
    var boton = f.querySelector('[data-meta-boton]');
    var meta = Number(f.dataset.meta) || 0;
    var actual = Number(f.dataset.actual) || 0;
    var faltante = Number(f.dataset.faltante) || 0;
    var textoInicial = despues ? despues.textContent : '';
    var chips = f.querySelectorAll('[data-monto]');

    function limpiar() {
      chips.forEach(function (x) { x.classList.remove('on'); x.setAttribute('aria-pressed', 'false'); });
    }

    chips.forEach(function (b) {
      b.addEventListener('click', function () {
        var estaba = b.classList.contains('on');
        limpiar();
        if (estaba) {
          campo.value = '';
          boton.disabled = true;
          boton.textContent = 'Elige un monto';
          if (orbita) orbita.style.setProperty('--extra', 0);
          if (despues) { despues.textContent = textoInicial; despues.classList.remove('cambia'); }
          return;
        }
        b.classList.add('on');
        b.setAttribute('aria-pressed', 'true');
        var m = Math.min(Number(b.dataset.monto) || 0, faltante || Infinity);
        campo.value = Math.round(m);
        boton.disabled = false;
        boton.textContent = 'Aportar $' + Math.round(m).toLocaleString('es-CL');
        if (orbita && meta) orbita.style.setProperty('--extra', (m / meta * 100).toFixed(2));
        if (despues && meta) {
          var p = Math.min(100, Math.round((actual + m) / meta * 100));
          despues.textContent = p >= 100 ? 'Llegarías a la meta' : 'Quedarías al ' + p + '%';
          despues.classList.add('cambia');
        }
      });
    });
  });
})();
