document.querySelectorAll('[data-monto]').forEach(function (b) {
  b.addEventListener('click', function () {
    var form = b.closest('form');
    form.querySelectorAll('[data-monto]').forEach(function (x) { x.classList.remove('on'); });
    b.classList.add('on');
    form.querySelector('input[name="monto"]').value = b.dataset.monto;
  });
});

function conectarTipoPrestamo(ids) {
  var seg = document.getElementById(ids.seg);
  if (!seg) return;
  var hidden = document.getElementById(ids.hidden);
  var campo = document.getElementById(ids.campo);
  var monto = document.getElementById(ids.monto);
  var cuotas = document.getElementById(ids.cuotas);
  var out = document.getElementById(ids.out);

  function paint() {
    var esCuotas = hidden.value === 'CUOTAS';
    var m = Number(monto.value || 0), c = Number((cuotas && cuotas.value) || 0);
    campo.style.display = esCuotas ? '' : 'none';
    if (!m) { out.textContent = '$0'; return; }
    out.textContent = esCuotas && c
      ? '$' + Math.round(m / c).toLocaleString('es-CL') + ' al mes durante ' + c + ' meses'
      : '$' + m.toLocaleString('es-CL') + ' de una vez';
  }

  seg.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    seg.querySelectorAll('button').forEach(function (x) { x.className = ''; });
    b.className = 'on';
    hidden.value = b.dataset.value;
    paint();
  });
  [monto, cuotas].forEach(function (el) { if (el) el.addEventListener('input', paint); });
  paint();
}

conectarTipoPrestamo({ seg: 'segTipoPrestamo', hidden: 'id_tipo_prestamo', campo: 'campoCuotas',
                       monto: 'id_monto_prestamo', cuotas: 'id_cuotas_prestamo', out: 'prestamoPreview' });
conectarTipoPrestamo({ seg: 'segTipoPersona', hidden: 'id_tipo_persona', campo: 'campoCuotasPersona',
                       monto: 'id_monto_persona', cuotas: 'id_cuotas_persona', out: 'personaPreview' });
