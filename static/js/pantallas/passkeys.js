(function () {
  var script = document.currentScript;
  var form = document.getElementById('formPasskey');
  var boton = document.getElementById('btnPasskey');
  var aviso = document.getElementById('avisoPasskey');
  var pass = document.getElementById('passPasskey');
  var nombre = document.getElementById('nombrePasskey');
  if (!form || !boton || !script) return;
  var rutas = { opciones: script.dataset.urlOpciones, verificar: script.dataset.urlVerificar };

  if (!window.RekonPasskeys || !RekonPasskeys.soportado()) {
    document.getElementById('sinSoporte').hidden = false;
    boton.disabled = true;
    return;
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    aviso.hidden = true;
    boton.disabled = true;
    RekonPasskeys.registrar(
      rutas,
      { password: pass ? pass.value : '', nombre: nombre.value }
    ).then(function () {
      window.location.reload();
    }).catch(function (err) {
      aviso.textContent = RekonPasskeys.mensaje(err, false);
      aviso.hidden = false;
      boton.disabled = false;
    });
  });
})();
