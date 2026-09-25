(function () {
  var pasos = Array.prototype.slice.call(document.querySelectorAll('.paso'));
  var marcas = Array.prototype.slice.call(document.querySelectorAll('#pasos > span'));
  var actual = 0;

  function mostrar(i) {
    actual = Math.max(0, Math.min(i, pasos.length - 1));
    pasos.forEach(function (p, k) { p.classList.toggle('activo', k === actual); });
    marcas.forEach(function (m, k) { m.classList.toggle('on', k <= actual); });
    var campo = pasos[actual].querySelector('input');
    if (campo) setTimeout(function () { campo.focus(); }, 80);
  }

  document.addEventListener('click', function (e) {
    if (e.target.closest('[data-siguiente]')) { e.preventDefault(); mostrar(actual + 1); }
    if (e.target.closest('[data-atras]')) { e.preventDefault(); mostrar(actual - 1); }

    var chip = e.target.closest('[data-atajos] > button');
    if (chip) {
      e.preventDefault();
      var grupo = chip.parentElement;
      var campo = document.querySelector(grupo.dataset.atajos);
      grupo.querySelectorAll('button').forEach(function (b) { b.classList.remove('on'); });
      chip.classList.add('on');
      if (campo) { campo.value = chip.dataset.monto; campo.dispatchEvent(new Event('input')); }
    }
  });

  document.getElementById('formOb').addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && actual < pasos.length - 1) { e.preventDefault(); mostrar(actual + 1); }
  });

  var valorCuota = document.getElementById('deuda_cuota');
  var n = document.getElementById('deuda_cuotas');
  var caja = document.getElementById('cajaCuotaOb');
  var monto = document.getElementById('cuotaObMonto');
  function cuota() {
    var v = Number(valorCuota.value || 0), c = Number(n.value || 0);
    if (v <= 0 || c <= 0) { caja.style.display = 'none'; return; }
    caja.style.display = 'block';
    monto.textContent = '$' + Math.round(v * c).toLocaleString('es-CL');
  }
  [valorCuota, n].forEach(function (el) { el.addEventListener('input', cuota); });

  var pres = document.getElementById('presupuesto');
  var ingreso = document.getElementById('ingreso_monto');
  var nota = document.getElementById('notaPresupuesto');
  pres.addEventListener('input', function () {
    var p = Number(pres.value || 0), i = Number(ingreso.value || 0);
    if (!p || !i) {
      nota.textContent = 'Puedes cambiarlo cuando quieras desde tu perfil.';
      nota.style.color = '';
      return;
    }
    if (p >= i) {
      nota.textContent = 'Ese límite es igual o mayor a lo que entra. No te dejaría margen.';
      nota.style.color = 'var(--coral)';
    } else {
      nota.textContent = 'Te quedarían $' + Math.round(i - p).toLocaleString('es-CL') + ' de margen al mes.';
      nota.style.color = 'var(--green)';
    }
  });
})();
