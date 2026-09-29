(function () {
  document.addEventListener('click', function (e) {
    var boton = e.target.closest('[data-desplegar]');
    if (!boton) return;
    var caja = boton.closest('[data-desplegable]');
    if (!caja) return;
    var abierta = caja.classList.toggle('abierta');
    boton.setAttribute('aria-expanded', abierta ? 'true' : 'false');
  });

  document.querySelectorAll('[data-pestanas-sec]').forEach(function (barra) {
    var grupo = barra.getAttribute('data-pestanas-sec');
    var paneles = document.querySelectorAll('[data-panel-sec="' + grupo + '"]');
    function mostrar(cual) {
      barra.querySelectorAll('button').forEach(function (b) {
        var on = b.dataset.pestana === cual;
        b.classList.toggle('on', on);
        b.setAttribute('aria-selected', on ? 'true' : 'false');
      });
      paneles.forEach(function (p) { p.hidden = p.dataset.pestana !== cual; });
      try { sessionStorage.setItem('fintora-pestana-' + grupo, cual); } catch (e) {}
    }
    barra.addEventListener('click', function (e) {
      var b = e.target.closest('button');
      if (b && b.dataset.pestana) mostrar(b.dataset.pestana);
    });
    var guardada = null;
    try { guardada = sessionStorage.getItem('fintora-pestana-' + grupo); } catch (e) {}
    if (location.hash) {
      var porHash = barra.querySelector('[data-hash="' + location.hash.slice(1) + '"]');
      if (porHash) guardada = porHash.dataset.pestana;
    }
    var primera = barra.querySelector('button[data-pestana]');
    if (!guardada || !barra.querySelector('[data-pestana="' + guardada + '"]')) guardada = primera ? primera.dataset.pestana : null;
    if (guardada) mostrar(guardada);
  });

  var dona = document.querySelector('[data-dona]');
  if (dona) {
    var filas = document.querySelectorAll('[data-cat-total]');
    var total = 0, partes = [], acum = 0;
    filas.forEach(function (f) { total += Number(f.dataset.catTotal) || 0; });
    filas.forEach(function (f) {
      var v = Number(f.dataset.catTotal) || 0;
      if (!total || !v) return;
      var desde = acum / total * 100;
      acum += v;
      partes.push(f.dataset.catColor + ' ' + desde.toFixed(2) + '% ' + (acum / total * 100).toFixed(2) + '%');
    });
    var anillo = dona.querySelector('[data-dona-anillo]');
    if (anillo && partes.length) anillo.style.background = 'conic-gradient(' + partes.join(',') + ')';
    var t = dona.querySelector('[data-dona-total]');
    if (t) t.textContent = '$' + Math.round(total).toLocaleString('es-CL');
    var nota = dona.querySelector('[data-dona-nota]');
    if (nota && filas.length && total) nota.textContent = Math.round((Number(filas[0].dataset.catTotal) || 0) / total * 100) + '% de lo que gastaste este mes.';
  }

  document.querySelectorAll('.pl-slider').forEach(function (r) {
    function pintar() {
      var max = Number(r.max) || 1;
      r.style.setProperty('--lleno', (Number(r.value) / max * 100) + '%');
    }
    r.addEventListener('input', pintar);
    pintar();
  });
})();
