(function () {
  var check = document.querySelector('[data-acepta-google]');
  var boton = document.getElementById('btnGoogle');
  var aviso = document.getElementById('avisoGoogle');
  if (!check || !boton) return;

  function pintar() {
    var ok = check.checked;
    boton.setAttribute('aria-disabled', ok ? 'false' : 'true');
    boton.style.opacity = ok ? '1' : '.45';
    boton.style.cursor = ok ? 'pointer' : 'not-allowed';
    if (ok && aviso) aviso.hidden = true;
  }

  check.addEventListener('change', pintar);
  boton.addEventListener('click', function (e) {
    if (check.checked) return;
    e.preventDefault();
    if (aviso) aviso.hidden = false;
    check.focus();
  });
  pintar();
})();
