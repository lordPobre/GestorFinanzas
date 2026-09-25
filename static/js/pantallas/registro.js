(function () {
  var script = document.currentScript;
  if (!script) return;
  var p1 = document.getElementById(script.dataset.p1);
  var p2 = document.getElementById(script.dataset.p2);
  var bar = document.getElementById('fuerzaBar');
  var texto = document.getElementById('fuerzaTexto');
  var coincide = document.getElementById('coincide');
  if (!p1 || !p2) return;

  var niveles = [
    { ancho: '25%', color: 'linear-gradient(90deg,#dc2626,#f87171)', label: 'Muy débil: fácil de adivinar.' },
    { ancho: '50%', color: 'linear-gradient(90deg,#ea580c,#fb923c)', label: 'Débil: agrega números o símbolos.' },
    { ancho: '75%', color: 'linear-gradient(90deg,var(--amber-oscuro),var(--amber))', label: 'Buena.' },
    { ancho: '100%', color: 'linear-gradient(90deg,#059669,var(--green))', label: 'Fuerte.' }
  ];

  p1.addEventListener('input', function () {
    var v = p1.value, puntos = 0;
    if (v.length >= 8) puntos++;
    if (/[A-Z]/.test(v)) puntos++;
    if (/[0-9]/.test(v)) puntos++;
    if (/[^A-Za-z0-9]/.test(v)) puntos++;
    if (!v) { bar.style.width = '0%'; texto.textContent = 'Mézclala con números y mayúsculas.'; return; }
    var n = niveles[Math.max(0, puntos - 1)];
    bar.style.width = n.ancho;
    bar.style.background = n.color;
    texto.textContent = n.label;
  });

  p2.addEventListener('input', function () {
    if (!p2.value) { coincide.textContent = ''; coincide.style.color = 'var(--text-muted)'; return; }
    var igual = p1.value === p2.value;
    coincide.textContent = igual ? 'Coinciden.' : 'Todavía no coinciden.';
    coincide.style.color = igual ? 'var(--green)' : 'var(--coral)';
  });
})();
