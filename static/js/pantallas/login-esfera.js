(function () {
  var auth = document.querySelector('.auth.lm');
  if (!auth) return;
  var hero = auth.querySelector('[data-lm-hero]');
  var esfera = auth.querySelector('[data-lm-esfera]');
  var panel = auth.querySelector('.auth-panel');
  var tarjeta = auth.querySelector('.auth-tarjeta');
  var abrir = auth.querySelector('[data-lm-abrir]');
  if (!hero || !esfera || !panel || !tarjeta || !abrir) return;
  var movil = window.matchMedia('(max-width: 900px)');
  tarjeta.setAttribute('tabindex', '-1');

  function abierto() { return auth.classList.contains('abierto'); }

  function medir() {
    var centro = esfera.offsetParent;
    if (!centro) return;
    var actual = centro.getBoundingClientRect().top + esfera.offsetTop + esfera.offsetHeight / 2;
    var arriba = parseFloat(getComputedStyle(hero).paddingTop) || 0;
    var destino = (arriba + panel.offsetTop) / 2;
    auth.style.setProperty('--lm-subir', Math.round(destino - actual) + 'px');
  }

  function sincronizar() {
    var enMovil = movil.matches;
    var ab = abierto();
    panel.inert = enMovil && !ab;
    hero.inert = enMovil && ab;
    if (enMovil && !ab) panel.setAttribute('aria-hidden', 'true');
    else panel.removeAttribute('aria-hidden');
    abrir.setAttribute('aria-expanded', ab ? 'true' : 'false');
  }

  function mostrar() {
    medir();
    auth.classList.add('abierto');
    sincronizar();
    tarjeta.focus({ preventScroll: true });
  }

  function ocultar() {
    auth.classList.remove('abierto');
    sincronizar();
    abrir.focus({ preventScroll: true });
  }

  abrir.addEventListener('click', mostrar);
  auth.querySelectorAll('[data-lm-cerrar]').forEach(function (el) {
    el.addEventListener('click', ocultar);
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && movil.matches && abierto()) ocultar();
  });
  window.addEventListener('resize', medir);
  if (movil.addEventListener) movil.addEventListener('change', sincronizar);

  medir();
  sincronizar();
})();
