(function () {
  var script = document.currentScript;
  var abrirPanel = !!(script && script.dataset.abrirPanel === '1');
  var form = document.getElementById('formRegistro');
  if (!form) return;

  var catsGasto = leerDatos('egreso');
  var catsIngreso = leerDatos('ingreso');

  var chips = document.getElementById('chipsGasto');

  function leerDatos(cual) {
    var cont = document.getElementById('chipsGasto');
    if (!cont || !cont.dataset[cual]) return [];
    try {
      var v = JSON.parse(cont.dataset[cual]);
      if (typeof v === 'string') v = JSON.parse(v);
      return Array.isArray(v) ? v : [];
    } catch (e) { return []; }
  }

  var campoTipo = document.getElementById('campoTipo');
  var campoCat = document.getElementById('campoCategoria');
  var campoMonto = document.getElementById('campoMonto');
  var labelCat = document.getElementById('labelCat');
  var montoView = document.getElementById('montoView');
  var segTipo = document.getElementById('segTipo');

  function pintarChips(tipo) {
    var lista = tipo === 'INGRESO' ? catsIngreso : catsGasto;
    labelCat.textContent = tipo === 'INGRESO' ? 'De dónde viene' : 'Categoría';
    chips.innerHTML = lista.map(function (c, i) {
      return '<button type="button" class="chip' + (i === 0 ? ' on' : '') +
             '" data-value="' + c[0] + '">' + c[1] + '</button>';
    }).join('');
    campoCat.value = lista[0][0];
  }

  function setTipo(tipo) {
    var esGasto = tipo !== 'INGRESO';
    campoTipo.value = esGasto ? 'EGRESO' : 'INGRESO';
    segTipo.querySelectorAll('button').forEach(function (b) {
      b.className = b.dataset.tipo === campoTipo.value ? (esGasto ? 'on-coral' : 'on-green') : '';
    });
    montoView.style.color = esGasto ? 'var(--coral)' : 'var(--green)';
    var prev = document.querySelector('[data-preview]');
    if (prev) prev.dataset.sign = esGasto ? '-1' : '1';
    var bloque = document.getElementById('bloquePago');
    if (bloque) bloque.style.display = esGasto ? 'block' : 'none';
    var labFecha = document.getElementById('labelFecha');
    if (labFecha) labFecha.textContent = esGasto ? 'Fecha del gasto' : 'Fecha del ingreso';
    pintarChips(campoTipo.value);
  }

  segTipo.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    setTipo(b.dataset.tipo);
  });

  chips.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    chips.querySelectorAll('button').forEach(function (x) { x.classList.remove('on'); });
    b.classList.add('on');
    campoCat.value = b.dataset.value;
  });

  document.querySelectorAll('[data-preset-tipo]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      setTipo(btn.dataset.presetTipo);
      var av = document.getElementById('avisoMonto');
      if (av) av.style.display = 'none';
    });
  });

  var teclado = form.querySelector('.keypad');
  var avisoMonto = document.getElementById('avisoMonto');
  var valor = '';
  function pintarMonto() {
    campoMonto.value = valor;
    if (valor && avisoMonto) avisoMonto.style.display = 'none';
    montoView.textContent = valor ? '$' + Number(valor).toLocaleString('es-CL') : '$0';
    var prev = document.querySelector('[data-preview]');
    if (prev) {
      var base = Number(prev.dataset.base || 0);
      var signo = Number(prev.dataset.sign || -1);
      var dias = Number(prev.dataset.dias || 1);
      var v = base + signo * Number(valor || 0);
      prev.textContent = '$' + Math.round(v).toLocaleString('es-CL');
      prev.style.color = v < 0 ? 'var(--coral)' : 'var(--text-primary)';
      var porDia = document.querySelector('[data-preview-dia]');
      if (porDia) porDia.textContent = '$' + Math.round(v / dias).toLocaleString('es-CL');
    }
  }
  teclado.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    e.preventDefault();
    var k = b.dataset.key;
    if (k === 'del') valor = valor.slice(0, -1);
    else if (valor.length <= 8) valor = (valor + k).replace(/^0+/, '');
    pintarMonto();
  });

  form.addEventListener('submit', function (e) {
    if (!Number(campoMonto.value || 0)) {
      e.preventDefault();
      if (avisoMonto) avisoMonto.style.display = 'block';
      montoView.style.transition = 'transform .12s';
      montoView.style.transform = 'scale(1.08)';
      montoView.style.color = 'var(--coral)';
      setTimeout(function () { montoView.style.transform = 'scale(1)'; }, 120);
    }
  });

  var segPago = document.getElementById('segPago');
  var campoSinPagar = document.getElementById('campoSinPagar');
  var notaPago = document.getElementById('notaPago');

  segPago.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    var yaPago = b.dataset.pagado === '1';
    campoSinPagar.value = yaPago ? '' : '1';
    segPago.querySelectorAll('button').forEach(function (x) {
      x.className = x === b ? (yaPago ? 'on-green' : 'on-coral') : '';
    });
    notaPago.textContent = yaPago
      ? 'Cuenta como gasto del mes en los dos casos. La diferencia es si la plata ya se fue.'
      : 'Queda en la lista de pagos del mes para marcarlo cuando lo pagues.';
  });

  setTipo('EGRESO');
  pintarMonto();

  if (abrirPanel) {
    var overlay = document.getElementById('modalGasto');
    if (overlay) { overlay.classList.add('open'); document.body.style.overflow = 'hidden'; }
  }
})();
