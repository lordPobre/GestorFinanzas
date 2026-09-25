(function () {
  var form = document.getElementById('formCodigo');
  var oculto = document.getElementById('codigo');
  var casillas = Array.prototype.slice.call(document.querySelectorAll('.auth-digito'));
  var respaldo = document.getElementById('codigoRespaldo');
  var modoRespaldo = false;

  function juntar() {
    return casillas.map(function (c) { return c.value; }).join('');
  }

  function enfocar(i) {
    if (casillas[i]) casillas[i].focus();
  }

  casillas.forEach(function (casilla, i) {
    casilla.addEventListener('input', function () {

      var texto = casilla.value.replace(/[^0-9]/g, '');
      if (texto.length > 1) {
        texto.split('').forEach(function (d, n) {
          if (casillas[i + n]) casillas[i + n].value = d;
        });
        enfocar(Math.min(i + texto.length, casillas.length - 1));
      } else {
        casilla.value = texto;
        if (texto) enfocar(i + 1);
      }

      var codigo = juntar();
      oculto.value = codigo;

      if (codigo.length === 6) form.submit();
    });

    casilla.addEventListener('keydown', function (e) {
      if (e.key === 'Backspace' && !casilla.value) {
        e.preventDefault();
        if (casillas[i - 1]) { casillas[i - 1].value = ''; enfocar(i - 1); }
        oculto.value = juntar();
      }
      if (e.key === 'ArrowLeft') { e.preventDefault(); enfocar(i - 1); }
      if (e.key === 'ArrowRight') { e.preventDefault(); enfocar(i + 1); }
    });

    casilla.addEventListener('paste', function (e) {
      e.preventDefault();
      var pegado = (e.clipboardData || window.clipboardData).getData('text') || '';
      var digitos = pegado.replace(/[^0-9]/g, '').slice(0, 6).split('');
      digitos.forEach(function (d, n) { if (casillas[n]) casillas[n].value = d; });
      oculto.value = juntar();
      enfocar(Math.min(digitos.length, casillas.length - 1));
      if (oculto.value.length === 6) form.submit();
    });
  });

  if (respaldo) {
    respaldo.addEventListener('input', function () {
      oculto.value = respaldo.value.trim().toUpperCase();
    });
  }

  form.addEventListener('submit', function () {
    oculto.value = modoRespaldo
      ? (respaldo ? respaldo.value.trim().toUpperCase() : '')
      : juntar();
  });

  var btn = document.getElementById('btnRespaldo');
  if (btn) {
    btn.addEventListener('click', function () {
      modoRespaldo = true;
      document.getElementById('campoNormal').hidden = true;
      document.getElementById('campoRespaldo').hidden = false;
      document.getElementById('esRespaldo').value = '1';
      btn.hidden = true;
      if (respaldo) respaldo.focus();
    });
  }
})();
