(function () {
  var input = document.getElementById('inputCartola');
  var zona = document.getElementById('zona');
  var titulo = document.getElementById('zonaTitulo');
  var nota = document.getElementById('zonaNota');
  var btn = document.getElementById('btnLeer');
  if (!input) return;

  function kb(n) { return (n / 1024 / 1024).toFixed(1) + ' MB'; }

  function mostrar(archivo) {
    if (!archivo) return;
    zona.classList.add('con-archivo');
    titulo.textContent = archivo.name;
    nota.textContent = kb(archivo.size) + ' · toca para cambiarlo';
    btn.disabled = false;
  }

  input.addEventListener('change', function () { mostrar(input.files[0]); });

  ['dragenter', 'dragover'].forEach(function (ev) {
    zona.addEventListener(ev, function (e) {
      e.preventDefault();
      zona.classList.add('encima');
    });
  });
  ['dragleave', 'drop'].forEach(function (ev) {
    zona.addEventListener(ev, function (e) {
      e.preventDefault();
      zona.classList.remove('encima');
    });
  });
  zona.addEventListener('drop', function (e) {
    var f = e.dataTransfer && e.dataTransfer.files[0];
    if (!f) return;
    input.files = e.dataTransfer.files;
    mostrar(f);
  });

  document.getElementById('formCartola').addEventListener('submit', function () {
    btn.disabled = true;
    btn.textContent = 'Leyendo…';
  });

  var copiar = document.getElementById('btnCopiarDiag');
  if (copiar) {
    copiar.addEventListener('click', function () {
      var caja = document.getElementById('diagTexto');
      var aviso = document.getElementById('diagAviso');
      caja.select();
      var listo = false;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(caja.value);
        listo = true;
      } else {
        try { listo = document.execCommand('copy'); } catch (e) { listo = false; }
      }
      aviso.textContent = listo ? 'Copiado.' : 'Selecciónalo y cópialo a mano.';
    });
  }
})();
