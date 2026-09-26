(function () {
  'use strict';

  document.documentElement.classList.add('lp-js');

  var reducir = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var timers = [];
  var cuadro = null;

  function formatear(n) { return '$' + n.toLocaleString('es-CL'); }

  function parar() {
    timers.forEach(clearTimeout);
    timers = [];
    if (cuadro) cancelAnimationFrame(cuadro);
  }

  function animarTelefono(pantalla) {
    var fases = pantalla.querySelectorAll('[data-lp-fase]');
    var cifra = pantalla.querySelector('[data-lp-cifra]');
    var barra = pantalla.querySelector('[data-lp-barra]');
    var pagada = pantalla.querySelector('[data-lp-pagada]');
    var meta = Number(cifra.dataset.meta) || 0;

    parar();
    if (reducir) {
      fases.forEach(function (el) { el.classList.add('lp-ok'); });
      if (pagada) pagada.classList.add('lp-ok');
      return;
    }

    fases.forEach(function (el) { el.classList.remove('lp-ok'); });
    if (pagada) pagada.classList.remove('lp-ok');
    cifra.textContent = formatear(0);
    barra.style.transition = 'none';
    barra.style.width = '0%';
    void barra.offsetWidth;
    barra.style.transition = '';

    var tiempos = { 1: 250, 2: 550, 3: 1350, 4: 1650, 5: 1850, 6: 2050 };
    fases.forEach(function (el) {
      timers.push(setTimeout(function () { el.classList.add('lp-ok'); }, tiempos[el.dataset.lpFase] || 0));
    });
    timers.push(setTimeout(function () { barra.style.width = barra.dataset.ancho; }, 650));
    timers.push(setTimeout(function () {
      var inicio = performance.now();
      var duracion = 1300;
      function paso(ahora) {
        var p = Math.min(1, (ahora - inicio) / duracion);
        cifra.textContent = formatear(Math.round(meta * (1 - Math.pow(1 - p, 3))));
        if (p < 1) cuadro = requestAnimationFrame(paso);
      }
      cuadro = requestAnimationFrame(paso);
    }, 650));
    if (pagada) timers.push(setTimeout(function () { pagada.classList.add('lp-ok'); }, 3100));
  }

  function prepararPestanas() {
    var botones = document.querySelectorAll('[data-lp-tab]');
    var texto = document.querySelector('[data-lp-texto]');
    botones.forEach(function (b) {
      b.addEventListener('click', function () {
        botones.forEach(function (x) { x.setAttribute('aria-selected', x === b ? 'true' : 'false'); });
        document.querySelectorAll('[data-lp-panel]').forEach(function (p) {
          p.hidden = p.dataset.lpPanel !== b.dataset.lpTab;
        });
        if (texto) texto.textContent = b.dataset.texto;
      });
    });
  }

  function prepararRevelado() {
    var items = [];
    document.querySelectorAll('[data-lp-revelar]').forEach(function (el) { items.push(el); });
    document.querySelectorAll('[data-lp-hijos]').forEach(function (padre) {
      Array.prototype.forEach.call(padre.children, function (el, i) {
        el.style.transitionDelay = (i * 90) + 'ms';
        items.push(el);
      });
    });

    function mostrar(el) {
      el.classList.add('lp-visible');
      setTimeout(function () { el.style.transitionDelay = ''; }, 1600);
    }

    if (reducir || !('IntersectionObserver' in window)) {
      items.forEach(mostrar);
      return;
    }
    var io = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (e) {
        if (!e.isIntersecting) return;
        mostrar(e.target);
        io.unobserve(e.target);
      });
    }, { threshold: 0, rootMargin: '0px 10000px -8% 10000px' });
    items.forEach(function (el) { io.observe(el); });
  }

  document.addEventListener('DOMContentLoaded', function () {
    var pantalla = document.querySelector('[data-lp-telefono]');
    if (pantalla) {
      animarTelefono(pantalla);
      pantalla.addEventListener('click', function () { animarTelefono(pantalla); });
    }
    prepararPestanas();
    prepararRevelado();
  });
})();
