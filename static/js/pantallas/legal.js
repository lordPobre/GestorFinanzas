(function () {
  'use strict';

  document.documentElement.classList.add('legal-js');

  function numero(i) { return (i < 9 ? '0' : '') + (i + 1); }

  function enlace(seccion, i) {
    var a = document.createElement('a');
    a.href = '#' + seccion.id;
    var n = document.createElement('span');
    n.textContent = numero(i);
    var t = document.createElement('span');
    t.textContent = seccion.querySelector('h2').textContent;
    a.appendChild(n);
    a.appendChild(t);
    return a;
  }

  document.addEventListener('DOMContentLoaded', function () {
    var secciones = Array.prototype.slice.call(document.querySelectorAll('.legal-cuerpo > section[id]'));
    if (!secciones.length) return;
    var indice = document.querySelector('[data-legal-indice]');
    var movil = document.querySelector('[data-legal-indice-movil]');
    var enlaces = [];

    secciones.forEach(function (s, i) {
      if (indice) {
        var a = enlace(s, i);
        indice.appendChild(a);
        enlaces.push(a);
      }
      if (movil) {
        var b = enlace(s, i);
        b.addEventListener('click', function () { movil.querySelector('details').open = false; });
        movil.querySelector('[data-legal-lista]').appendChild(b);
      }
    });

    var cuenta = movil && movil.querySelector('[data-legal-cuenta]');
    if (cuenta) cuenta.textContent = secciones.length + ' secciones';

    if (!enlaces.length || !('IntersectionObserver' in window)) return;

    function marcar(id) {
      enlaces.forEach(function (a) {
        var actual = a.getAttribute('href') === '#' + id;
        a.classList.toggle('legal-actual', actual);
        if (actual) a.setAttribute('aria-current', 'location');
        else a.removeAttribute('aria-current');
      });
    }

    marcar(secciones[0].id);
    var io = new IntersectionObserver(function (entradas) {
      var visibles = entradas.filter(function (e) { return e.isIntersecting; });
      visibles.sort(function (a, b) { return a.boundingClientRect.top - b.boundingClientRect.top; });
      if (visibles.length) marcar(visibles[0].target.id);
    }, { rootMargin: '0px 0px -70% 0px', threshold: 0 });
    secciones.forEach(function (s) { io.observe(s); });
  });
})();
