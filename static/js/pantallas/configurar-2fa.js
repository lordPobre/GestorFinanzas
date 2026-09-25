(function () {
  var campo = document.getElementById('campoCodigo');
  if (campo) {

    campo.addEventListener('input', function () {
      campo.value = campo.value.replace(/[^0-9]/g, '');
    });
    campo.focus();
  }

  var btn = document.getElementById('btnCopiarClave');
  var clave = document.getElementById('claveManual');
  if (btn && clave) {
    btn.addEventListener('click', function () {

      navigator.clipboard.writeText(clave.dataset.clave).then(function () {
        btn.innerHTML = '<i class="fas fa-check" style="font-size:10px;margin-right:5px"></i>Copiada';
        setTimeout(function () {
          btn.innerHTML = '<i class="fas fa-copy" style="font-size:10px;margin-right:5px"></i>Copiar clave';
        }, 2000);
      });
    });
  }
})();
