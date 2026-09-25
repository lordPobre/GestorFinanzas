(function () {
  var script = document.currentScript;
  if (!script) return;
  var d = script.dataset;
  var meta = document.getElementById(d.meta);
  var actual = document.getElementById(d.actual);
  var fecha = document.getElementById(d.fecha);
  var caja = document.getElementById('cajaPlan');
  var mes = document.getElementById('planMes');
  var nota = document.getElementById('planNota');
  if (!meta || !fecha) return;

  function pintar() {
    var falta = Number(meta.value || 0) - Number(actual && actual.value || 0);
    if (falta <= 0 || !fecha.value) { caja.style.display = 'none'; return; }
    var hoy = new Date(), fin = new Date(fecha.value);
    var meses = (fin.getFullYear() - hoy.getFullYear()) * 12 + (fin.getMonth() - hoy.getMonth());
    if (meses <= 0) {
      caja.style.display = 'block';
      mes.textContent = '$' + Math.round(falta).toLocaleString('es-CL');
      nota.textContent = 'La fecha es este mes: tendrías que juntarlo todo de una vez.';
      return;
    }
    caja.style.display = 'block';
    mes.textContent = '$' + Math.round(falta / meses).toLocaleString('es-CL');
    nota.textContent = 'Te faltan $' + Math.round(falta).toLocaleString('es-CL')
      + ' y quedan ' + meses + ' mes' + (meses === 1 ? '' : 'es') + '.';
  }
  [meta, actual, fecha].forEach(function (el) { if (el) el.addEventListener('input', pintar); });
  pintar();
})();
