(function () {
  var seg = document.getElementById('segTipoPr');
  var campo = document.getElementById('campoCuotasPr');
  var monto = document.getElementById('id_pr_monto');
  var cuotas = document.getElementById('id_pr_cuotas');
  var caja = document.getElementById('cajaPr');
  var valor = document.getElementById('prCuota');
  if (!seg) return;

  function pintar() {
    var enCuotas = document.getElementById('id_pr_tipo').value === 'CUOTAS';
    var m = Number(monto.value || 0), n = Number(cuotas.value || 0);
    if (!enCuotas || m <= 0 || n <= 0) { caja.style.display = 'none'; return; }
    caja.style.display = 'block';
    valor.textContent = '$' + Math.round(m / n).toLocaleString('es-CL');
  }

  seg.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    campo.style.display = b.dataset.value === 'CUOTAS' ? 'block' : 'none';
    pintar();
  });
  [monto, cuotas].forEach(function (el) { if (el) el.addEventListener('input', pintar); });
})();
