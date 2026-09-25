(function () {
  var form = document.getElementById('formConfirmar');
  if (!form) return;
  var checks = form.querySelectorAll('.cartola-check');
  var cuenta = document.getElementById('cuenta');

  function actualizar() {
    var n = 0;
    checks.forEach(function (c) {
      if (c.checked) n++;

      var fila = c.closest('.cartola-fila');
      if (fila) fila.classList.toggle('apagada', !c.checked);
    });
    cuenta.textContent = n === 0
      ? 'No hay nada marcado.'
      : 'Se guardará' + (n === 1 ? ' 1 movimiento.' : 'n ' + n + ' movimientos.');
    document.getElementById('btnGuardar').disabled = n === 0;
  }

  checks.forEach(function (c) { c.addEventListener('change', actualizar); });

  form.querySelectorAll('.cartola-cat').forEach(function (sel) {
    var txt = sel.parentNode.querySelector('[data-cat-txt]');
    if (!txt) return;
    sel.addEventListener('change', function () {
      txt.textContent = sel.options[sel.selectedIndex].text;
    });
  });

  form.querySelectorAll('[data-deben]').forEach(function (cb) {
    var caja = cb.closest('.cartola-deben');
    var quien = caja.querySelector('.cartola-deben-quien');
    var sel = caja.querySelector('[data-deben-persona]');
    var nombre = caja.querySelector('[data-deben-nombre]');

    function pintar() {
      quien.hidden = !cb.checked;
      sel.disabled = !cb.checked;
      nombre.hidden = !cb.checked || sel.value !== 'nueva';
      nombre.disabled = nombre.hidden;
      if (!nombre.hidden) nombre.focus();
    }
    cb.addEventListener('change', function () {
      if (cb.checked) {
        var fila = cb.closest('.cartola-fila').querySelector('.cartola-check');
        if (fila && !fila.checked) { fila.checked = true; actualizar(); }
      }
      pintar();
    });
    sel.addEventListener('change', pintar);
  });

  form.querySelectorAll('[data-marcar]').forEach(function (b) {
    b.addEventListener('click', function () {
      var modo = b.dataset.marcar;
      checks.forEach(function (c) {
        var repetida = c.closest('.cartola-fila').classList.contains('repetida');
        c.checked = modo === 'todos' ? true
                  : modo === 'ninguno' ? false
                  : !repetida;
      });
      actualizar();
    });
  });

  actualizar();
})();
