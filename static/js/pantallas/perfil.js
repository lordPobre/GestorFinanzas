(function () {
  var script = document.currentScript;
  if (!script) return;
  var campo = document.getElementById(script.dataset.foto);
  var img = document.getElementById('vistaAvatar');
  var nota = document.getElementById('notaFoto');
  if (!campo || !img) return;

  img.addEventListener('error', function () {
    if (!img.getAttribute('src')) return;
    img.removeAttribute('src');
    img.hidden = true;
  });

  var btnQuitar = document.getElementById('btnQuitarFoto');
  var campoQuitar = document.getElementById('quitarFoto');
  if (btnQuitar) {
    btnQuitar.addEventListener('click', function () {
      campoQuitar.value = '1';
      campo.value = '';
      img.removeAttribute('src');
      img.hidden = true;
      btnQuitar.hidden = true;
      if (nota) {
        nota.hidden = false;
        nota.lastChild.textContent = 'Guarda los cambios para quitar la foto';
      }
    });
  }

  campo.addEventListener('change', function () {
    var f = campo.files && campo.files[0];
    if (!f) return;
    if (campoQuitar) campoQuitar.value = '';
    img.src = URL.createObjectURL(f);
    img.hidden = false;
    if (nota) nota.hidden = false;
  });
})();
