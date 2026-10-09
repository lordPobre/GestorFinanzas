(function () {
  'use strict';

  var HEX = /^#[0-9a-f]{3,8}$/i;

  function numero(valor) {
    var n = parseFloat(String(valor || '').replace(',', '.'));
    return isFinite(n) ? n : null;
  }

  function cada(raiz, selector, funcion) {
    Array.prototype.forEach.call(raiz.querySelectorAll(selector), funcion);
  }

  function aplicar(raiz) {
    raiz = raiz || document;
    cada(raiz, '[data-ancho-pct]', function (el) {
      var n = numero(el.dataset.anchoPct);
      if (n !== null) el.style.width = n + '%';
    });
    cada(raiz, '[data-columnas]', function (el) {
      var n = numero(el.dataset.columnas);
      if (n !== null && n >= 1) el.style.gridTemplateColumns = 'repeat(' + Math.round(n) + ', minmax(0, 1fr))';
    });
    cada(raiz, '[data-pct-var]', function (el) {
      var n = numero(el.dataset.pctVar);
      if (n !== null) el.style.setProperty('--pct', String(n));
    });
    cada(raiz, '[data-color-var]', function (el) {
      if (HEX.test(el.dataset.colorVar)) el.style.setProperty('--color', el.dataset.colorVar);
    });
    cada(raiz, '[data-fondo]', function (el) {
      if (HEX.test(el.dataset.fondo)) el.style.background = el.dataset.fondo;
      if (HEX.test(el.dataset.tinta || '')) el.style.color = el.dataset.tinta;
    });
    cada(raiz, '[data-color]', function (el) {
      if (HEX.test(el.dataset.color)) el.style.color = el.dataset.color;
    });
    cada(raiz, '[data-color-cat]', function (el) {
      var color = el.dataset.colorCat;
      if (!HEX.test(color)) return;
      el.style.background = color + '29';
      el.style.color = color;
    });
  }

  var html = document.documentElement;
  html.classList.add('sin-transicion');
  aplicar(document);
  void html.offsetWidth;
  html.classList.remove('sin-transicion');

  window.finappEstilos = aplicar;
})();
