(function () {
  var script = document.currentScript;
  var seg = document.getElementById('segPerfil');
  if (!seg || !script) return;
  var d = script.dataset;
  var paneles = {
    datos: document.getElementById('panelDatos'),
    seguridad: document.getElementById('panelSeguridad')
  };
  if (!paneles.datos || !paneles.seguridad) return;

  seg.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    seg.querySelectorAll('button').forEach(function (x) { x.classList.remove('on'); });
    b.classList.add('on');
    Object.keys(paneles).forEach(function (k) {
      paneles[k].style.display = (k === b.dataset.panel) ? 'block' : 'none';
    });
  });

  if (d.pwErrores === '1' || location.hash === '#seguridad') {
    var bs = seg.querySelector('[data-panel="seguridad"]');
    if (bs) bs.click();
  }

  var p1 = document.getElementById(d.p1);
  var p2 = document.getElementById(d.p2);
  var aviso = document.getElementById('coincide');
  if (p1 && p2) {
    p2.addEventListener('input', function () {
      if (!p2.value) { aviso.textContent = ''; return; }
      var igual = p1.value === p2.value;
      aviso.textContent = igual ? 'Coinciden.' : 'Todavía no coinciden.';
      aviso.style.color = igual ? 'var(--green)' : 'var(--coral)';
    });
  }
})();
