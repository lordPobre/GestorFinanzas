(function () {
  var script = document.currentScript;
  var monto = document.getElementById('id_sub_monto');
  var anual = document.getElementById('subAnual');
  var nota = document.getElementById('subNota');
  if (!monto || !script) return;
  var actual = Number(script.dataset.totalMensual || 0) || 0;
  monto.addEventListener('input', function () {
    var m = Number(monto.value || 0);
    anual.textContent = '$' + Math.round(m * 12).toLocaleString('es-CL');
    nota.textContent = m
      ? 'Tu total mensual pasaría a $' + Math.round(actual + m).toLocaleString('es-CL') + '.'
      : 'Se suma a tus $' + actual.toLocaleString('es-CL') + ' mensuales actuales.';
  });
})();
