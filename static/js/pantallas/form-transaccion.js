(function () {
  var NOTA_DEBO = 'Cuenta en el mes de la fecha. Si lo pagas más adelante, pon el día en que lo pagarás.';
  var NOTA_PAGADO = 'Cuenta como gasto del mes en los dos casos. La diferencia es si la plata ya se fue.';

  function iniciar(raiz) {
    var seg = raiz.querySelector('#segTipoMov');
    var form = seg && seg.closest('form');
    var oculto = form && form.querySelector('input[name="tipo"]');
    if (!seg || !oculto) return;
    var bloque = raiz.querySelector('#bloquePagoForm');
    var monto = form.querySelector('[name="monto"]');

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
      var b = e.target.closest('button');
      if (!b) return;
      e.preventDefault();
      aplicar(b.dataset.value);
    });
    aplicar(oculto.value || 'EGRESO');

    var segPago = raiz.querySelector('#segPagoForm');
    var campo = raiz.querySelector('#id_es_pendiente');
    var nota = raiz.querySelector('#notaPagoForm');
    if (!segPago || !campo) return;
    segPago.addEventListener('click', function (e) {
      var b = e.target.closest('button');
      if (!b) return;
      e.preventDefault();
      var pendiente = b.dataset.pendiente === '1';
      campo.value = pendiente ? '1' : '';
      segPago.querySelectorAll('button').forEach(function (x) {
        x.className = x === b ? (pendiente ? 'on-coral' : 'on-green') : '';
      });
      if (nota) nota.textContent = pendiente ? NOTA_DEBO : NOTA_PAGADO;
    });
  }

  window.finappFormMov = iniciar;
  iniciar(document);
})();
