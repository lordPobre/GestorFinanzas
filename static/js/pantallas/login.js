(function () {
  var script = document.currentScript;
  if (!script || !window.FintoraPasskeys || !FintoraPasskeys.soportado()) return;
  if (!window.FintoraDispositivo || !FintoraDispositivo.movil) return;
  var rutas = { opciones: script.dataset.urlOpciones, verificar: script.dataset.urlVerificar };
  var bloque = document.getElementById('bloquePasskey');
  var boton = document.getElementById('btnPasskey');
  var aviso = document.getElementById('avisoPasskey');
  var texto = document.getElementById('avisoPasskeyTexto');
  if (!bloque || !boton) return;
  bloque.hidden = false;

  boton.addEventListener('click', function () {
    aviso.hidden = true;
    boton.disabled = true;
    var siguiente = new URLSearchParams(window.location.search).get('next') || '';
    FintoraPasskeys.entrar(rutas, siguiente).then(function (r) {
      window.location.href = r.destino;
    }).catch(function (err) {
      texto.textContent = FintoraPasskeys.mensaje(err, true);
      aviso.hidden = false;
      boton.disabled = false;
      var usuario = document.querySelector('input[name=username]');
      if (usuario) usuario.focus();
    });
  });
})();
