(function () {
  var hoja = document.getElementById('modalAnotar');
  if (hoja) {
    hoja.addEventListener('click', function (e) {
      if (e.target.closest('[data-open]')) hoja.classList.remove('open');
    });
  }

  var form = document.getElementById('formRegistro');
  if (!form) return;

  var MARCAS = [];
  var GLIFOS = {};
  var urlMarcas = document.currentScript && document.currentScript.dataset.marcas;
  function normalizar(t) {
    return (t || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  }
  function escapar(t) { return t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

  var campoDesc = document.getElementById('campoDesc');
  var campoTipo = document.getElementById('campoTipo');
  var marca = document.getElementById('anotarMarca');
  var montoView = document.getElementById('montoView');
  var btnGuardar = document.getElementById('btnGuardar');

  function pintarMarca() {
    if (!marca) return;
    var texto = normalizar(campoDesc ? campoDesc.value : '');
    var m = null;
    for (var i = 0; texto && i < MARCAS.length; i++) {
      if (MARCAS[i][0].test(texto)) { m = MARCAS[i][1]; break; }
    }
    var esGasto = !campoTipo || campoTipo.value !== 'INGRESO';
    if (m) {
      marca.style.background = m.fondo;
      marca.style.color = m.tinta;
      marca.innerHTML = '';
      if (m.glifo && GLIFOS[m.glifo]) {
        var ns = 'http://www.w3.org/2000/svg';
        var svg = document.createElementNS(ns, 'svg');
        svg.setAttribute('viewBox', '0 0 24 24');
        svg.setAttribute('class', 'marca-glifo');
        var path = document.createElementNS(ns, 'path');
        path.setAttribute('d', GLIFOS[m.glifo]);
        path.setAttribute('fill', 'currentColor');
        svg.appendChild(path);
        marca.appendChild(svg);
      } else if (m.fa) {
        var ic = document.createElement('i');
        ic.className = m.fa;
        marca.appendChild(ic);
      } else {
        var letra = document.createElement('b');
        letra.textContent = m.letra || m.nombre.charAt(0).toUpperCase();
        marca.appendChild(letra);
      }
      marca.classList.add('reconocida');
    } else {
      marca.style.background = '';
      marca.style.color = '';
      marca.innerHTML = '<i class="fas ' + (esGasto ? 'fa-receipt' : 'fa-arrow-down') + '"></i>';
      marca.classList.remove('reconocida');
      marca.classList.toggle('ingreso', !esGasto);
    }
  }

  if (campoDesc) campoDesc.addEventListener('input', pintarMarca);
  document.addEventListener('click', function (e) {
    if (e.target.closest('#segTipo button, [data-preset-tipo]')) setTimeout(pintarMarca, 0);
  });

  if (montoView && btnGuardar) {
    var pintarBoton = function () {
      var t = montoView.textContent.trim();
      btnGuardar.textContent = t && t !== '$0' ? 'Guardar ' + t : 'Guardar';
    };
    new MutationObserver(pintarBoton).observe(montoView, { childList: true, characterData: true, subtree: true });
    pintarBoton();
  }

  var seg = document.getElementById('segFecha');
  var campoFecha = document.getElementById('campoFecha');
  var texto = document.getElementById('fechaTexto');
  if (seg && campoFecha) {
    var MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
    var hoy = seg.dataset.hoy || campoFecha.value;
    var partes = hoy.split('-').map(Number);
    var base = new Date(Date.UTC(partes[0], partes[1] - 1, partes[2]));
    var iso = function (d) { return d.toISOString().slice(0, 10); };
    var corta = function (d) { return d.getUTCDate() + ' ' + MESES[d.getUTCMonth()]; };
    var ayer = new Date(base.getTime() - 86400000);

    var elegir = function (cual) {
      seg.querySelectorAll('button').forEach(function (b) {
        b.classList.toggle('on', b.dataset.fecha === cual);
      });
      if (cual === 'otra') {
        campoFecha.hidden = false;
        if (texto) texto.textContent = '';
        campoFecha.focus();
        if (campoFecha.showPicker) { try { campoFecha.showPicker(); } catch (e) {} }
        return;
      }
      campoFecha.hidden = true;
      var d = cual === 'ayer' ? ayer : base;
      campoFecha.value = iso(d);
      if (texto) texto.textContent = (cual === 'ayer' ? 'Ayer, ' : 'Hoy, ') + corta(d);
    };

    seg.addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      elegir(b.dataset.fecha);
    });
    elegir('hoy');
  }

  pintarMarca();

  if (urlMarcas && window.fetch) {
    fetch(urlMarcas).then(function (r) { return r.ok ? r.json() : null; }).then(function (datos) {
      if (!datos) return;
      GLIFOS = datos.glifos || {};
      MARCAS = (datos.marcas || []).map(function (m) {
        var claves = m.claves.map(escapar).join('|');
        return [new RegExp('(^|[^a-z0-9])(' + claves + ')(?=[^a-z0-9]|$)'), m];
      });
      pintarMarca();
    }).catch(function () {});
  }
})();
