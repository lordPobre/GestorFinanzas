(function () {
  var codigos = Array.prototype.map.call(
    document.querySelectorAll('.codigo-respaldo'),
    function (el) { return el.textContent.trim(); }
  );
  var texto = 'Códigos de respaldo de FinApp\n' +
              'Cada uno sirve una sola vez.\n\n' + codigos.join('\n');

  document.getElementById('btnCopiar').addEventListener('click', function () {
    var b = this;
    navigator.clipboard.writeText(texto).then(function () {
      b.innerHTML = '<i class="fas fa-check" style="font-size:11px"></i>Copiados';
      setTimeout(function () {
        b.innerHTML = '<i class="fas fa-copy" style="font-size:11px"></i>Copiar todos';
      }, 2000);
    });
  });

  document.getElementById('btnDescargar').addEventListener('click', function () {

    var blob = new Blob([texto], { type: 'text/plain' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'finapp-codigos-respaldo.txt';
    a.click();
    URL.revokeObjectURL(url);
  });

  var check = document.getElementById('confirmo');
  var btn = document.getElementById('btnListo');
  check.addEventListener('change', function () {
    btn.style.pointerEvents = check.checked ? 'auto' : 'none';
    btn.style.opacity = check.checked ? '1' : '.45';
  });
})();
