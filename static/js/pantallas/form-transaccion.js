(function () {
  var script = document.currentScript;
  if (!script) return;
  var oculto = document.getElementById(script.dataset.tipo);
  var seg = document.getElementById('segTipoMov');
  var bloque = document.getElementById('bloquePagoForm');
  var monto = document.getElementById(script.dataset.monto);
  if (!seg || !oculto) return;

  function aplicar(tipo) {
    oculto.value = tipo;
    var esGasto = tipo !== 'INGRESO';
    seg.querySelectorAll('button').forEach(function (b) {
      var activo = b.dataset.value === tipo;
      b.className = activo ? (esGasto ? 'on-coral' : 'on-green') : '';
    });
    if (bloque) bloque.style.display = esGasto ? 'block' : 'none';
    if (monto) monto.style.color = esGasto ? 'var(--coral)' : 'var(--green)';
  }

  seg.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    e.preventDefault();
    aplicar(b.dataset.value);
  });
  aplicar(oculto.value || 'EGRESO');

  var segPago = document.getElementById('segPagoForm');
  var campo = document.getElementById('id_es_pendiente');
  var nota = document.getElementById('notaPagoForm');
  if (segPago) {
    segPago.addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      e.preventDefault();
      var pendiente = b.dataset.pendiente === '1';
      campo.value = pendiente ? '1' : '';
      segPago.querySelectorAll('button').forEach(function (x) {
        x.className = x === b ? (pendiente ? 'on-coral' : 'on-green') : '';
      });
      nota.textContent = pendiente
        ? 'Queda en la lista de pagos del mes para marcarlo cuando lo pagues.'
        : 'Cuenta como gasto del mes en los dos casos. La diferencia es si la plata ya se fue.';
    });
  }
})();
