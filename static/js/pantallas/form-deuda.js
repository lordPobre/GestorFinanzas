(function () {
  var script = document.currentScript;
  if (!script) return;
  var d = script.dataset;
  var cuota = document.getElementById(d.cuota);
  var cuotas = document.getElementById(d.cuotas);
  var inicio = document.getElementById(d.inicio);
  var caja = document.getElementById('cajaCuota');
  var monto = document.getElementById('cuotaMonto');
  var fin = document.getElementById('cuotaFin');
  var MESES = ['enero','febrero','marzo','abril','mayo','junio','julio',
               'agosto','septiembre','octubre','noviembre','diciembre'];
  if (!cuota || !cuotas) return;

  function pintar() {
    var v = Number(cuota.value || 0), n = Number(cuotas.value || 0);
    if (v <= 0 || n <= 0) { caja.style.display = 'none'; return; }
    caja.style.display = 'block';
    monto.textContent = '$' + Math.round(v * n).toLocaleString('es-CL');
    var texto = n + ' cuota' + (n === 1 ? '' : 's') + ' de $' + Math.round(v).toLocaleString('es-CL');
    if (inicio && inicio.value) {
      var f = new Date(inicio.value + 'T00:00:00');
      f.setMonth(f.getMonth() + n - 1);
      texto += ' · terminas en ' + MESES[f.getMonth()] + ' ' + f.getFullYear();
    }
    fin.textContent = texto;
  }
  [cuota, cuotas, inicio].forEach(function (el) { if (el) el.addEventListener('input', pintar); });
  pintar();
})();
