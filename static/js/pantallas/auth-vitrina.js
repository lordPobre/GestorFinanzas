(function () {
  var raiz = document.querySelector('[data-vitrina]');
  if (!raiz) return;
  var pasos = Array.prototype.slice.call(raiz.querySelectorAll('[data-vitrina-paso]'));
  var pantallas = Array.prototype.slice.call(raiz.querySelectorAll('[data-vitrina-pantalla]'));
  var luces = Array.prototype.slice.call(raiz.querySelectorAll('[data-vitrina-luz]'));
  if (!pasos.length || pasos.length !== pantallas.length) return;

  var DURACION = 4200;
  var quieto = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var visible = window.matchMedia ? window.matchMedia('(min-width: 1181px) and (min-height: 681px)') : { matches: true };
  var actual = 0;
  var reloj = null;

  raiz.style.setProperty('--dur', DURACION + 'ms');
  if (quieto) raiz.classList.add('av-quieto');

  function plata(n) { return '$' + Math.round(n).toLocaleString('es-CL'); }

  function contar(el) {
    var fin = Number(el.getAttribute('data-contar')) || 0;
    if (quieto) { el.textContent = plata(fin); return; }
    var inicio = null;
    el.textContent = plata(0);
    function paso(ahora) {
      if (inicio === null) inicio = ahora;
      var x = Math.max(0, Math.min(1, (ahora - inicio - 150) / 900));
      el.textContent = plata(fin * (1 - Math.pow(1 - x, 3)));
      if (x < 1) window.requestAnimationFrame(paso);
    }
    window.requestAnimationFrame(paso);
  }

  function llenar(el) {
    var ancho = el.getAttribute('data-llenar') + '%';
    if (quieto) { el.style.width = ancho; return; }
    el.style.transition = 'none';
    el.style.width = '0';
    void el.offsetWidth;
    el.style.transition = 'width .9s cubic-bezier(.22, 1, .36, 1) .3s';
    el.style.width = ancho;
  }

  function mostrar(i) {
    var previo = actual;
    actual = i;
    pantallas.forEach(function (p, j) {
      p.classList.toggle('on', j === i);
      p.classList.toggle('sale', j === previo && j !== i);
    });
    luces.forEach(function (l, j) { l.classList.toggle('on', j === i); });
    pasos.forEach(function (b, j) {
      b.classList.remove('on');
      b.setAttribute('aria-pressed', j === i ? 'true' : 'false');
    });
    void raiz.offsetWidth;
    pasos[i].classList.add('on');
    pantallas[i].querySelectorAll('[data-contar]').forEach(contar);
    pantallas[i].querySelectorAll('[data-llenar]').forEach(llenar);
  }

  function programar() {
    window.clearTimeout(reloj);
    if (quieto || !visible.matches || document.hidden) return;
    reloj = window.setTimeout(function () {
      mostrar((actual + 1) % pantallas.length);
      programar();
    }, DURACION);
  }

  pasos.forEach(function (b, j) {
    b.addEventListener('click', function () {
      if (!visible.matches) return;
      mostrar(j);
      programar();
    });
  });

  document.addEventListener('visibilitychange', programar);
  if (visible.addEventListener) {
    visible.addEventListener('change', function () {
      if (visible.matches) mostrar(actual);
      programar();
    });
  }

  if (visible.matches) mostrar(0);
  programar();
})();
