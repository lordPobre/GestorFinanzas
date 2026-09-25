(function () {
  var script = document.currentScript;
  if (!script || !window.RekonPasskeys || !RekonPasskeys.soportado()) return;
  var rutas = { opciones: script.dataset.urlOpciones, verificar: script.dataset.urlVerificar };
  var bloque = document.getElementById('bloquePasskey');
  var boton = document.getElementById('btnPasskey');
  var aviso = document.getElementById('avisoPasskey');
  var texto = document.getElementById('avisoPasskeyTexto');
  var entrar = document.getElementById('btnEntrar');
  if (!bloque || !boton) return;
  bloque.hidden = false;
  if (entrar) {
    entrar.classList.remove('btn-amber');
    entrar.classList.add('btn-glass');
  }

  boton.addEventListener('click', function () {
    aviso.hidden = true;
    boton.disabled = true;
    var siguiente = new URLSearchParams(window.location.search).get('next') || '';
    RekonPasskeys.entrar(rutas, siguiente).then(function (r) {
      window.location.href = r.destino;
    }).catch(function (err) {
      texto.textContent = RekonPasskeys.mensaje(err, true);
      aviso.hidden = false;
      boton.disabled = false;
      var usuario = document.querySelector('input[name=username]');
      if (usuario) usuario.focus();
    });
  });
})();
