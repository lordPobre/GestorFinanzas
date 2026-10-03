(function () {
  var caja = document.querySelector('[data-consejos]');
  if (!caja) return;
  var CLAVE = 'fintora-consejos-ocultos';
  var total = caja.querySelector('[data-consejos-total]');
  var ocultos = [];
  try { ocultos = JSON.parse(localStorage.getItem(CLAVE) || '[]') || []; } catch (e) { ocultos = []; }

  function actualizar() {
    var suma = 0;
    var visibles = 0;
    caja.querySelectorAll('[data-consejo]').forEach(function (t) {
      if (t.hidden) return;
      visibles++;
      suma += Number(t.dataset.ahorro || 0) || 0;
    });
    caja.hidden = visibles === 0;
    if (total) total.textContent = '$' + Math.round(suma).toLocaleString('es-CL');
  }

  caja.querySelectorAll('[data-consejo]').forEach(function (t) {
    if (ocultos.indexOf(t.dataset.consejo) >= 0) t.hidden = true;
    var elegir = t.querySelector('[data-consejo-elegir]');
    var lista = t.querySelector('[data-consejo-lista]');
    var ocultar = t.querySelector('[data-consejo-ocultar]');
    if (elegir && lista) {
      elegir.addEventListener('click', function () {
        var abrir = lista.hidden;
        lista.hidden = !abrir;
        elegir.setAttribute('aria-expanded', abrir ? 'true' : 'false');
      });
    }
    if (ocultar) {
      ocultar.addEventListener('click', function () {
        if (ocultos.indexOf(t.dataset.consejo) < 0) ocultos.push(t.dataset.consejo);
        try { localStorage.setItem(CLAVE, JSON.stringify(ocultos)); } catch (e) {}
        t.hidden = true;
        actualizar();
      });
    }
  });
  actualizar();
})();

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
