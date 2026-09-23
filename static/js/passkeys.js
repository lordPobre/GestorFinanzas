(function () {
  function aB64(buf) {
    var b = new Uint8Array(buf), s = '';
    for (var i = 0; i < b.length; i++) s += String.fromCharCode(b[i]);
    return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  function deB64(txt) {
    txt = txt.replace(/-/g, '+').replace(/_/g, '/');
    while (txt.length % 4) txt += '=';
    var s = atob(txt), b = new Uint8Array(s.length);
    for (var i = 0; i < s.length; i++) b[i] = s.charCodeAt(i);
    return b.buffer;
  }

  function csrf() {
    var c = document.querySelector('[name=csrfmiddlewaretoken]');
    return c ? c.value : '';
  }

  function enviar(url, datos) {
    var f = new FormData();
    Object.keys(datos || {}).forEach(function (k) { f.append(k, datos[k]); });
    return fetch(url, {
      method: 'POST',
      body: f,
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': csrf(), 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' }
    }).then(function (r) {
      return r.json().catch(function () { return { ok: false, msg: 'No se pudo conectar. Vuelve a intentarlo.' }; });
    });
  }

  function falla(r) {
    var e = new Error(r.msg || 'Algo salió mal.');
    e.servidor = true;
    throw e;
  }

  function mensaje(e, alEntrar) {
    if (e && e.servidor) return e.message;
    if (e && e.name === 'NotAllowedError') {
      return alEntrar
        ? 'No se reconoció tu cara o huella, o se canceló. Entra con tu contraseña.'
        : 'Se canceló o no se reconoció. Vuelve a intentarlo.';
    }
    if (e && e.name === 'InvalidStateError') return 'Este dispositivo ya estaba vinculado.';
    return alEntrar
      ? 'No se pudo usar Face ID o huella. Entra con tu contraseña.'
      : 'No se pudo vincular este dispositivo.';
  }

  function soportado() {
    return !!(window.PublicKeyCredential && navigator.credentials && navigator.credentials.create);
  }

  function registrar(urls, extra) {
    return enviar(urls.opciones, { password: extra.password || '' }).then(function (r) {
      if (!r.ok) falla(r);
      var o = r.opciones;
      o.challenge = deB64(o.challenge);
      o.user.id = deB64(o.user.id);
      (o.excludeCredentials || []).forEach(function (c) { c.id = deB64(c.id); });
      return navigator.credentials.create({ publicKey: o });
    }).then(function (cred) {
      var resp = cred.response;
      var json = {
        id: cred.id,
        rawId: aB64(cred.rawId),
        type: cred.type,
        response: {
          clientDataJSON: aB64(resp.clientDataJSON),
          attestationObject: aB64(resp.attestationObject),
          transports: resp.getTransports ? resp.getTransports() : []
        },
        clientExtensionResults: cred.getClientExtensionResults ? cred.getClientExtensionResults() : {},
        authenticatorAttachment: cred.authenticatorAttachment || null
      };
      return enviar(urls.verificar, { credencial: JSON.stringify(json), nombre: extra.nombre || '' });
    }).then(function (r) {
      if (!r.ok) falla(r);
      return r;
    });
  }

  function entrar(urls, siguiente) {
    return enviar(urls.opciones).then(function (r) {
      if (!r.ok) falla(r);
      var o = r.opciones;
      o.challenge = deB64(o.challenge);
      (o.allowCredentials || []).forEach(function (c) { c.id = deB64(c.id); });
      return navigator.credentials.get({ publicKey: o });
    }).then(function (cred) {
      var resp = cred.response;
      var json = {
        id: cred.id,
        rawId: aB64(cred.rawId),
        type: cred.type,
        response: {
          clientDataJSON: aB64(resp.clientDataJSON),
          authenticatorData: aB64(resp.authenticatorData),
          signature: aB64(resp.signature),
          userHandle: resp.userHandle ? aB64(resp.userHandle) : null
        },
        clientExtensionResults: cred.getClientExtensionResults ? cred.getClientExtensionResults() : {},
        authenticatorAttachment: cred.authenticatorAttachment || null
      };
      return enviar(urls.verificar, { credencial: JSON.stringify(json), next: siguiente || '' });
    }).then(function (r) {
      if (!r.ok) falla(r);
      return r;
    });
  }

  window.RekonPasskeys = { soportado: soportado, registrar: registrar, entrar: entrar, mensaje: mensaje };
})();
