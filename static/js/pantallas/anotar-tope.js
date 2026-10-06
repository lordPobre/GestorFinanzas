(function () {
  var caja = document.getElementById('avisoTope');
  var form = document.getElementById('formRegistro');
  if (!caja || !form) return;
  var topes = {};
  try { topes = JSON.parse(caja.dataset.topes || '{}'); if (typeof topes === 'string') topes = JSON.parse(topes); } catch (e) { topes = {}; }
  if (!topes || !Object.keys(topes).length) return;
  var simbolo = caja.dataset.simbolo || '$';
  var mes = caja.dataset.mes || '';
  var campoTipo = document.getElementById('campoTipo');
  var campoCat = document.getElementById('campoCategoria');
  var campoMonto = document.getElementById('campoMonto');
  var campoFecha = document.getElementById('campoFecha');
  var montoView = document.getElementById('montoView');
  function plata(n) { return simbolo + Math.round(n).toLocaleString('es-CL'); }
  function monto() {
    var v = parseFloat(String((campoMonto && campoMonto.value) || '').replace(',', '.'));
    if (!isNaN(v) && v > 0) return v;
    var t = ((montoView && montoView.textContent) || '').replace(/[^\d]/g, '');
    return t ? parseInt(t, 10) : 0;
  }
  function pintar() {
    var t = topes[campoCat && campoCat.value];
    var m = monto();
    var esGasto = !campoTipo || campoTipo.value !== 'INGRESO';
    var mismoMes = !campoFecha || !mes || (campoFecha.value || '').slice(0, 7) === mes;
    if (!t || !esGasto || !mismoMes || m <= 0) { caja.hidden = true; return; }
    var nombre = t[0], tope = t[1], llevas = t[2], total = llevas + m;
    var pct = tope > 0 ? Math.round(total / tope * 100) : 0;
    if (pct < 80) { caja.hidden = true; return; }
    var pasa = total > tope;
    caja.className = 'anotar-tope ' + (pasa ? 'rojo' : 'amarillo');
    caja.textContent = '';
    var b = document.createElement('b');
    b.textContent = pasa ? 'Con esto pasas tu tope de ' + nombre : 'Con esto llegas al ' + pct + ' % de tu tope de ' + nombre;
    var s = document.createElement('span');
    s.textContent = 'Llevas ' + plata(llevas) + ' de ' + plata(tope) + '. ' +
      (pasa ? 'Quedarías ' + plata(total - tope) + ' por encima.' : 'Te quedarían ' + plata(tope - total) + '.');
    var barra = document.createElement('span'); barra.className = 'anotar-tope-barra';
    var lleno = document.createElement('span'); lleno.style.width = Math.min(100, Math.round(llevas / tope * 100)) + '%';
    var nuevo = document.createElement('span'); nuevo.className = 'nuevo';
    nuevo.style.width = Math.max(0, Math.min(100, pct) - Math.min(100, Math.round(llevas / tope * 100))) + '%';
    barra.appendChild(lleno); barra.appendChild(nuevo);
    caja.appendChild(b); caja.appendChild(s); caja.appendChild(barra);
    caja.hidden = false;
  }
  if (montoView) new MutationObserver(pintar).observe(montoView, { childList: true, characterData: true, subtree: true });
  document.addEventListener('click', function (e) {
    if (e.target.closest('#chipsGasto, #segTipo, #segFecha, [data-preset-tipo]')) setTimeout(pintar, 0);
  });
  if (campoFecha) campoFecha.addEventListener('change', pintar);
  pintar();
})();
