(function () {
  'use strict';

  var CLAVE = 'fintora-lugar';
  var VIGENCIA = 30000;
  var SIN_VOLVER = /\/(logout|login|registro|verificar|recuperar|entrar)\b/;
  var PAGINA_DE_FORMULARIO = /\/(editar|nuevo|nueva|nuevo-ingreso)\/?$/;

  function aqui() { return location.pathname + location.search; }

  function rutaDe(form) {
    try { return new URL(form.getAttribute('action') || location.href, location.href).pathname; }
    catch (e) { return location.pathname; }
  }

  function scrollerDe(raiz) {
    var todos = [raiz].concat(Array.prototype.slice.call(raiz.querySelectorAll('*')));
    for (var i = 0; i < todos.length; i++) {
      var el = todos[i];
      if (el.scrollHeight > el.clientHeight + 2) {
        var oy = getComputedStyle(el).overflowY;
        if (oy === 'auto' || oy === 'scroll') return el;
      }
    }
    return null;
  }

  function pestanas() {
    return Array.prototype.slice.call(document.querySelectorAll('.sec-pestanas'));
  }

  function debeVolver(form) {
    if (form.querySelector('[name="next"]')) return false;
    if (form.hasAttribute('data-sin-lugar')) return false;
    if (PAGINA_DE_FORMULARIO.test(location.pathname)) return false;
    var ruta = rutaDe(form);
    if (SIN_VOLVER.test(ruta)) return false;
    if (/eliminar/.test(ruta) && ruta.indexOf(location.pathname) === 0 && location.pathname !== '/') return false;
    return true;
  }

  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (e.defaultPrevented || !form || form.tagName !== 'FORM') return;
    if ((form.getAttribute('method') || 'get').toLowerCase() !== 'post') return;
    if (form.target && form.target !== '_self') return;

    if (debeVolver(form)) {
      var next = document.createElement('input');
      next.type = 'hidden';
      next.name = 'next';
      next.value = aqui();
      form.appendChild(next);
    }

    var modal = document.querySelector('.modal-overlay.open:not(.confirm-overlay)');
    var dentro = modal ? scrollerDe(modal) : null;
    var filtro = modal ? modal.querySelector('[data-mov-filtro].on') : null;
    var lugar = {
      ruta: aqui(),
      y: window.scrollY || window.pageYOffset || 0,
      modal: modal && modal.id ? modal.id : '',
      dentro: dentro ? dentro.scrollTop : 0,
      filtro: filtro ? filtro.getAttribute('data-mov-filtro') : '',
      pestanas: pestanas().map(function (grupo) {
        var botones = Array.prototype.slice.call(grupo.querySelectorAll('button'));
        return botones.findIndex(function (b) { return b.classList.contains('on'); });
      }),
      t: Date.now(),
    };
    try { sessionStorage.setItem(CLAVE, JSON.stringify(lugar)); } catch (err) {}
  });

  var lugar = null;
  try {
    lugar = JSON.parse(sessionStorage.getItem(CLAVE) || 'null');
    sessionStorage.removeItem(CLAVE);
  } catch (err) { lugar = null; }
  if (!lugar || lugar.ruta !== aqui() || Date.now() - lugar.t > VIGENCIA) return;

  if ('scrollRestoration' in history) history.scrollRestoration = 'manual';

  (lugar.pestanas || []).forEach(function (indice, n) {
    var grupo = pestanas()[n];
    if (!grupo || indice < 0) return;
    var boton = grupo.querySelectorAll('button')[indice];
    if (boton && !boton.classList.contains('on')) boton.click();
  });

  function bajar() { window.scrollTo(0, lugar.y); }
  bajar();

  var modal = lugar.modal ? document.getElementById(lugar.modal) : null;
  if (modal && window.finappOpen) {
    window.finappOpen('#' + lugar.modal);
    if (lugar.filtro) {
      var boton = modal.querySelector('[data-mov-filtro="' + lugar.filtro + '"]');
      if (boton && !boton.classList.contains('on')) boton.click();
    }
    var dentro = scrollerDe(modal);
    if (dentro) dentro.scrollTop = lugar.dentro;
    if (document.activeElement && modal.contains(document.activeElement)) {
      setTimeout(function () {
        if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
        var otra = scrollerDe(modal);
        if (otra) otra.scrollTop = lugar.dentro;
      }, 80);
    }
  }

  window.addEventListener('load', function () {
    bajar();
    if (modal) {
      var dentro = scrollerDe(modal);
      if (dentro) dentro.scrollTop = lugar.dentro;
    }
  });
})();
