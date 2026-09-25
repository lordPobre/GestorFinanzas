(function () {
  var script = document.currentScript;
  if (!script) return;
  var p1 = document.getElementById(script.dataset.p1);
  var p2 = document.getElementById(script.dataset.p2);
  var bar = document.getElementById('fuerzaBar');
  var texto = document.getElementById('fuerzaTexto');
  var coincide = document.getElementById('coincide');

  var niveles = [
    { ancho: '25%', color: 'linear-gradient(90deg,#dc2626,#f87171)', label: 'Muy débil: fácil de adivinar.' },
    { ancho: '50%', color: 'linear-gradient(90deg,#ea580c,#fb923c)', label: 'Débil: agrega números o símbolos.' },
    { ancho: '75%', color: 'linear-gradient(90deg,var(--amber-oscuro),var(--amber))', label: 'Buena.' },
    { ancho: '100%', color: 'linear-gradient(90deg,#059669,var(--green))', label: 'Fuerte.' }
  ];

  if (p1) {
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
  }

  if (p2) {
    p2.addEventListener('input', function () {
      if (!p2.value) { coincide.textContent = ''; coincide.style.color = 'var(--text-muted)'; return; }
      var igual = p1.value === p2.value;
      coincide.textContent = igual ? 'Coinciden.' : 'Todavía no coinciden.';
      coincide.style.color = igual ? 'var(--green)' : 'var(--coral)';
    });
  }

  var codigo = document.getElementById('id_codigo_2fa');
  if (codigo) {
    codigo.addEventListener('input', function () {
      if (document.getElementById('esRespaldo').value === '1') return;
      codigo.value = codigo.value.replace(/[^0-9]/g, '');
    });
  }

  var btn = document.getElementById('btnRespaldo');
  if (btn && codigo) {
    btn.addEventListener('click', function () {
      document.getElementById('esRespaldo').value = '1';
      codigo.value = '';
      codigo.maxLength = 9;
      codigo.placeholder = 'ABCD-2345';
      codigo.setAttribute('inputmode', 'text');
      codigo.style.letterSpacing = '.1em';
      codigo.style.fontSize = '18px';
      var etiqueta = document.querySelector('label[for="id_codigo_2fa"]');
      if (etiqueta) etiqueta.textContent = 'Código de respaldo';
      btn.hidden = true;
      codigo.focus();
    });
  }
})();
