(function () {
  var script = document.currentScript;
  if (!script) return;
  var ids = { ga4: script.dataset.ga4, meta: script.dataset.meta, tiktok: script.dataset.tiktok, x: script.dataset.x, xRegistro: script.dataset.xRegistro };
  var evento = script.dataset.evento;
  var CLAVE = 'fintora.cookies';
  var aviso = document.querySelector('[data-cookies]');
  var cargado = false;

  function leer() {
    try { return JSON.parse(localStorage.getItem(CLAVE) || 'null'); } catch (e) { return null; }
  }
  function guardar(acepta) {
    try { localStorage.setItem(CLAVE, JSON.stringify({ acepta: acepta, fecha: new Date().toISOString() })); } catch (e) {}
  }
  function insertar(src) {
    var s = document.createElement('script');
    s.async = true;
    s.src = src;
    document.head.appendChild(s);
  }

  function cargarGoogle(id) {
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    window.gtag('js', new Date());
    window.gtag('config', id);
    insertar('https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(id));
  }

  function cargarMeta(id) {
    if (window.fbq) return;
    var f = window.fbq = function () {
      if (f.callMethod) f.callMethod.apply(f, arguments); else f.queue.push(arguments);
    };
    if (!window._fbq) window._fbq = f;
    f.push = f;
    f.loaded = true;
    f.version = '2.0';
    f.queue = [];
    insertar('https://connect.facebook.net/en_US/fbevents.js');
    window.fbq('init', id);
    window.fbq('track', 'PageView');
  }

  function cargarTiktok(id) {
    var ttq = window.ttq = window.ttq || [];
    window.TiktokAnalyticsObject = 'ttq';
    ttq.methods = ['page', 'track', 'identify', 'instances', 'debug', 'on', 'off', 'once', 'ready', 'alias', 'group', 'enableCookie', 'disableCookie', 'holdConsent', 'revokeConsent', 'grantConsent'];
    ttq.setAndDefer = function (t, e) { t[e] = function () { t.push([e].concat(Array.prototype.slice.call(arguments, 0))); }; };
    for (var i = 0; i < ttq.methods.length; i++) ttq.setAndDefer(ttq, ttq.methods[i]);
    ttq.instance = function (t) {
      var e = ttq._i[t] || [];
      for (var n = 0; n < ttq.methods.length; n++) ttq.setAndDefer(e, ttq.methods[n]);
      return e;
    };
    ttq.load = function (e, n) {
      var r = 'https://analytics.tiktok.com/i18n/pixel/events.js';
      ttq._i = ttq._i || {}; ttq._i[e] = []; ttq._i[e]._u = r;
      ttq._t = ttq._t || {}; ttq._t[e] = +new Date();
      ttq._o = ttq._o || {}; ttq._o[e] = n || {};
      insertar(r + '?sdkid=' + encodeURIComponent(e) + '&lib=ttq');
    };
    ttq.load(id);
    ttq.page();
  }

  function cargarX(id) {
    if (window.twq) return;
    var s = window.twq = function () {
      if (s.exe) s.exe.apply(s, arguments); else s.queue.push(arguments);
    };
    s.version = '1.1';
    s.queue = [];
    insertar('https://static.ads-twitter.com/uwt.js');
    window.twq('config', id);
  }

  function cargar() {
    if (cargado) return;
    cargado = true;
    if (ids.ga4) cargarGoogle(ids.ga4);
    if (ids.meta) cargarMeta(ids.meta);
    if (ids.tiktok) cargarTiktok(ids.tiktok);
    if (ids.x) cargarX(ids.x);
  }

  function registrarAlta() {
    if (ids.ga4 && window.gtag) window.gtag('event', 'sign_up', { method: 'correo' });
    if (ids.meta && window.fbq) window.fbq('track', 'CompleteRegistration');
    if (ids.tiktok && window.ttq) window.ttq.track('CompleteRegistration');
    if (ids.x && ids.xRegistro && window.twq) window.twq('event', ids.xRegistro, {});
  }

  function borrarCookies() {
    var nombres = document.cookie.split(';').map(function (c) { return c.split('=')[0].trim(); });
    var dominio = location.hostname.replace(/^www\./, '');
    nombres.forEach(function (n) {
      if (!/^(_ga|_gid|_gcl|_fbp|_fbc|_ttp|_tt_|muc_ads|personalization_id|guest_id)/.test(n)) return;
      ['', '; domain=' + dominio, '; domain=.' + dominio].forEach(function (d) {
        document.cookie = n + '=; Max-Age=0; path=/' + d;
      });
    });
  }

  function mostrar(si) { if (aviso) aviso.hidden = !si; }

  document.addEventListener('click', function (e) {
    if (e.target.closest('[data-cookies-aceptar]')) {
      guardar(true);
      mostrar(false);
      cargar();
    } else if (e.target.closest('[data-cookies-rechazar]')) {
      var antes = leer();
      guardar(false);
      mostrar(false);
      if (cargado || (antes && antes.acepta)) {
        borrarCookies();
        location.reload();
      }
    } else if (e.target.closest('[data-cookies-abrir]')) {
      e.preventDefault();
      mostrar(true);
    }
  });

  var decision = leer();
  if (evento) {
    if (decision && decision.acepta) {
      cargar();
      if (evento === 'registro') registrarAlta();
    }
    return;
  }
  if (decision && decision.acepta) cargar();
  else if (!decision) mostrar(true);
})();
