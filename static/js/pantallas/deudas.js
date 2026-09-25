(function () {
  var script = document.currentScript;
  if (!script) return;
  var d = script.dataset;
  var cuota = document.getElementById(d.cuota);
  var cuotas = document.getElementById(d.cuotas);
  var inicio = document.getElementById(d.inicio);
  var out = document.getElementById('cuotaPreview');
  var fin = document.getElementById('finPreview');
  var meses = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'];
  if (!cuota || !cuotas || !out || !fin) return;
  function paint() {
    var v = Number(cuota.value || 0), c = Number(cuotas.value || 0);
    if (!v || !c) {
      out.textContent = '$0';
      fin.textContent = 'Pon la cuota y cuántas son';
      return;
    }
    out.textContent = '$' + Math.round(v * c).toLocaleString('es-CL');
    var texto = c + ' cuota' + (c === 1 ? '' : 's') + ' de $' + Math.round(v).toLocaleString('es-CL');
    var base = inicio && inicio.value ? new Date(inicio.value + 'T00:00:00') : new Date();
    base.setMonth(base.getMonth() + c - 1);
    fin.textContent = texto + ' · última en ' + meses[base.getMonth()] + ' ' + base.getFullYear();
  }
  [cuota, cuotas, inicio].forEach(function (el) { if (el) el.addEventListener('input', paint); });
  paint();
})();
