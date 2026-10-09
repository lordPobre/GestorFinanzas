(function () {
  var soporta = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  var ios = /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  var instalada = (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) || navigator.standalone === true;
  var NO = 'fintora-avisos-no';
  function token() { var c = document.querySelector('input[name="csrfmiddlewaretoken"]'); return c ? c.value : ''; }
  function bytes(b64) {
    var raw = atob((b64 + '==='.slice((b64.length + 3) % 4)).replace(/-/g, '+').replace(/_/g, '/'));
    var out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }
  function enviar(url, datos) {
    return fetch(url, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token(), 'X-Requested-With': 'XMLHttpRequest' },
      body: JSON.stringify(datos || {}),
    }).then(function (r) { if (!r.ok) throw new Error(String(r.status)); return r.json(); });
  }
  function mismaClave(sub, clave) {
    try {
      var a = new Uint8Array(sub.options.applicationServerKey), b = bytes(clave);
      if (a.length !== b.length) return false;
      for (var i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
      return true;
    } catch (e) { return true; }
  }
  function actual() { return navigator.serviceWorker.ready.then(function (reg) { return reg.pushManager.getSubscription(); }); }
  function activar(clave, url) {
    return Notification.requestPermission().then(function (p) {
      if (p !== 'granted') throw new Error('permiso');
      return navigator.serviceWorker.ready;
    }).then(function (reg) {
      return reg.pushManager.getSubscription().then(function (s) {
        if (s && !mismaClave(s, clave)) return s.unsubscribe().then(function () { return null; });
        return s;
      }).then(function (s) {
        return s || reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: bytes(clave) });
      });
    }).then(function (sub) {
      var datos = sub.toJSON();
      try { datos.zona = Intl.DateTimeFormat().resolvedOptions().timeZone || ''; } catch (e) { datos.zona = ''; }
      return enviar(url, datos);
    });
  }
  function desactivar(url) {
    return actual().then(function (s) {
      if (!s) return null;
      var ep = s.endpoint;
      return s.unsubscribe().then(function () { return enviar(url, { endpoint: ep }); });
    });
  }

  var fila = document.querySelector('[data-push]');
  if (fila) {
    var estado = fila.querySelector('[data-push-estado]');
    var sw = fila.querySelector('[data-push-switch]');
    var poner = function (texto, on) {
      estado.textContent = texto;
      if (on === undefined) { sw.hidden = true; return; }
      sw.hidden = false;
      sw.classList.toggle('on', on);
      sw.setAttribute('aria-pressed', on ? 'true' : 'false');
    };
    if (!soporta) {
      poner(ios && !instalada ? 'En el iPhone, agrega Fintora a la pantalla de inicio para recibirlos.' : 'Este navegador no recibe avisos.');
    } else if (Notification.permission === 'denied') {
      poner('Bloqueados. Actívalos en los ajustes del navegador.');
    } else {
      actual().then(function (s) { poner(s ? 'Activados en este aparato' : 'Apagados en este aparato', !!s); })
        .catch(function () { poner('Este navegador no recibe avisos.'); });
      sw.addEventListener('click', function () {
        sw.disabled = true;
        var encender = !sw.classList.contains('on');
        var paso = encender ? activar(fila.dataset.clave, fila.dataset.suscribir) : desactivar(fila.dataset.quitar);
        paso.then(function () { location.reload(); }).catch(function (e) {
          sw.disabled = false;
          poner(e && e.message === 'permiso' ? 'No diste permiso. Puedes cambiarlo en los ajustes del navegador.' : 'No se pudo. Vuelve a intentarlo.', !encender);
        });
      });
    }
  }

  var probar = document.querySelector('[data-push-probar]');
  if (probar) {
    probar.addEventListener('click', function () {
      probar.disabled = true;
      enviar(probar.dataset.pushProbar).then(function (r) {
        probar.textContent = r.enviados ? 'Enviado' : 'No llegó a ningún aparato';
      }).catch(function () { probar.textContent = 'Espera unos segundos'; })
        .then(function () { setTimeout(function () { probar.disabled = false; probar.textContent = 'Probar aviso'; }, 4000); });
    });
  }

  var inv = document.querySelector('[data-push-invitacion]');
  if (inv) {
    var no = false;
    try { no = localStorage.getItem(NO) === '1'; } catch (e) {}
    var si = inv.querySelector('[data-push-si]');
    var cerrar = inv.querySelector('[data-push-no]');
    var tit = inv.querySelector('[data-push-titulo]');
    var txt = inv.querySelector('[data-push-texto]');
    var ocultar = function () { inv.hidden = true; try { localStorage.setItem(NO, '1'); } catch (e) {} };
    cerrar.addEventListener('click', ocultar);
    if (!no && soporta && Notification.permission === 'default') {
      inv.hidden = false;
      si.addEventListener('click', function () {
        si.disabled = true;
        activar(inv.dataset.clave, inv.dataset.suscribir).then(function () {
          tit.textContent = 'Listo';
          txt.textContent = 'Te avisamos un día antes de cada cobro. Puedes cambiarlo en Perfil.';
          si.hidden = true; cerrar.hidden = true;
          setTimeout(function () { inv.hidden = true; }, 5000);
        }).catch(ocultar);
      });
    } else if (!no && !soporta && ios && !instalada) {
      inv.hidden = false;
      tit.textContent = 'Avisos en el iPhone';
      txt.textContent = 'Para recibir un aviso antes de cada cobro, agrega Fintora a la pantalla de inicio: botón Compartir y «Agregar a inicio».';
      si.hidden = true;
      cerrar.textContent = 'Entendido';
    }
  }
})();
