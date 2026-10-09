(function () {
  'use strict';

  var CLAVE = 'fintora-lugar';
  var CORTO = 30000;
  var LARGO = 600000;
  var SIN_VOLVER = /\/(logout|login|registro|verificar|recuperar|entrar)\b/;
  var PAGINA_DE_FORMULARIO = /\/(editar|nuevo|nueva|nuevo-ingreso)\/?$/;

  function aqui() { return location.pathname + location.search; }
  function esFormulario() { return PAGINA_DE_FORMULARIO.test(location.pathname); }

  function leer() {
    try { return JSON.parse(sessionStorage.getItem(CLAVE) || 'null'); } catch (e) { return null; }
  }
  function guardar(l) { try { sessionStorage.setItem(CLAVE, JSON.stringify(l)); } catch (e) {} }
  function olvidar() { try { sessionStorage.removeItem(CLAVE); } catch (e) {} }

  function normal(valor) {
    try {
      var u = new URL(valor, location.href);
      return u.origin === location.origin ? u.pathname + u.search : '';
    } catch (e) { return ''; }
  }
  function soloRuta(valor) { return (valor || '').split('?')[0]; }

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

  function foto(ruta, largo) {
    var modal = document.querySelector('.modal-overlay.open:not(.confirm-overlay)');
    var dentro = modal ? scrollerDe(modal) : null;
    var filtro = modal ? modal.querySelector('[data-mov-filtro].on') : null;
    return {
      ruta: ruta,
      largo: !!largo,
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
  }

  var previo = leer();
  if (previo && Date.now() - previo.t > (previo.largo ? LARGO : CORTO)) { olvidar(); previo = null; }

  function agregarNext(form, valor) {
    var campo = document.createElement('input');
    campo.type = 'hidden';
    campo.name = 'next';
    campo.value = valor;
    form.appendChild(campo);
  }

  function destinoDe(form) {
    var ruta = rutaDe(form);
    if (SIN_VOLVER.test(ruta) || form.hasAttribute('data-sin-lugar')) return '';
    var campo = form.querySelector('[name="next"]');

    if (esFormulario()) {
      if (!previo || !previo.largo) return campo ? normal(campo.value) : '';
      var objetivo = campo ? (campo.value || '').trim() : '';
      var alOrigen = !campo || objetivo.charAt(0) === '?' ||
        soloRuta(normal(objetivo)) === soloRuta(previo.ruta);
      if (!alOrigen) return normal(objetivo);
      if (campo) campo.value = previo.ruta; else agregarNext(form, previo.ruta);
      return previo.ruta;
    }

    if (campo) {
      var v = (campo.value || '').trim();
      if (v.charAt(0) === '?') {
        if (location.pathname !== '/') return '';
        campo.value = aqui();
        return aqui();
      }
      if (soloRuta(normal(v)) === location.pathname) {
        campo.value = aqui();
        return aqui();
      }
      return normal(v);
    }

    if (/eliminar/.test(ruta) && ruta.indexOf(location.pathname) === 0 && location.pathname !== '/') return '';
    agregarNext(form, aqui());
    return aqui();
  }

  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (e.defaultPrevented || !form || form.tagName !== 'FORM') return;
    if ((form.getAttribute('method') || 'get').toLowerCase() !== 'post') return;
    if (form.target && form.target !== '_self') return;

    var destino = destinoDe(form);
    if (!destino) return;
    if (esFormulario() && previo && previo.largo && destino === previo.ruta) {
      var vuelta = JSON.parse(JSON.stringify(previo));
      vuelta.largo = false;
      vuelta.t = Date.now();
      guardar(vuelta);
    } else if (destino === aqui()) {
      guardar(foto(destino, false));
    } else {
      olvidar();
    }
  });

  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href]');
    if (!a || a.target === '_blank' || a.hasAttribute('download') || esFormulario()) return;
    var destino = normal(a.getAttribute('href'));
    if (!destino || !PAGINA_DE_FORMULARIO.test(soloRuta(destino))) return;
    guardar(foto(aqui(), true));
  });

  window.finappRecargarAqui = function () {
    guardar(foto(aqui(), false));
    location.reload();
  };

  if (!previo || esFormulario()) return;
  if (previo.ruta !== aqui()) { olvidar(); return; }
  olvidar();
  var lugar = previo;

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
  function bajarDentro() {
    if (!modal) return;
    var dentro = scrollerDe(modal);
    if (dentro) dentro.scrollTop = lugar.dentro;
  }
  if (modal && window.finappOpen) {
    window.finappOpen('#' + lugar.modal);
    if (lugar.filtro) {
      var boton = modal.querySelector('[data-mov-filtro="' + lugar.filtro + '"]');
      if (boton && !boton.classList.contains('on')) boton.click();
    }
    bajarDentro();
    setTimeout(function () {
      if (document.activeElement && modal.contains(document.activeElement) && document.activeElement.blur) {
        document.activeElement.blur();
      }
      bajarDentro();
    }, 80);
  }

  window.addEventListener('load', function () {
    bajar();
    bajarDentro();
  });
})();
