(function () {
  var monto = document.getElementById('id_sub_monto');
  var anual = document.getElementById('subAnual');
  if (!monto) return;
  monto.addEventListener('input', function () {
    anual.textContent = '$' + Math.round(Number(monto.value || 0) * 12).toLocaleString('es-CL');
  });
})();
