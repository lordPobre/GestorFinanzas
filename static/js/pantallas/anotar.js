(function () {
  var hoja = document.getElementById('modalAnotar');
  if (hoja) {
    hoja.addEventListener('click', function (e) {
      if (e.target.closest('[data-open]')) hoja.classList.remove('open');
    });
  }

  var form = document.getElementById('formRegistro');
  if (!form) return;

  var MARCAS = [
    [/spotify/i, { fondo: '#121212', color: '#1ed760', icono: 'fab fa-spotify' }],
    [/netflix/i, { fondo: '#0b0b0b', color: '#e50914', letra: 'N' }],
    [/uber/i, { fondo: '#000000', color: '#ffffff', icono: 'fab fa-uber' }],
    [/l[ií]der|walmart/i, { fondo: '#0071ce', color: '#ffc220', letra: 'L' }],
    [/jumbo/i, { fondo: '#1f9a3a', color: '#ffffff', letra: 'J' }],
    [/santa isabel/i, { fondo: '#d71920', color: '#ffffff', letra: 'S' }],
    [/tottus/i, { fondo: '#6cb33f', color: '#ffffff', letra: 'T' }],
    [/unimarc/i, { fondo: '#e30613', color: '#ffffff', letra: 'U' }],
    [/copec/i, { fondo: '#d52b1e', color: '#ffffff', letra: 'C' }],
    [/shell/i, { fondo: '#f7d117', color: '#dd1d21', letra: 'S' }],
    [/rappi/i, { fondo: '#ff441f', color: '#ffffff', letra: 'R' }],
    [/pedidos ?ya/i, { fondo: '#fa0050', color: '#ffffff', letra: 'P' }],
    [/ripley/i, { fondo: '#4b2a7b', color: '#ffffff', letra: 'R' }],
    [/falabella/i, { fondo: '#aad500', color: '#1a2b00', letra: 'F' }],
    [/paris/i, { fondo: '#0a5ea8', color: '#ffffff', letra: 'P' }],
    [/mercado ?libre/i, { fondo: '#ffe600', color: '#2d3277', letra: 'M' }],
    [/amazon|prime video/i, { fondo: '#131a22', color: '#ff9900', icono: 'fab fa-amazon' }],
    [/apple|icloud/i, { fondo: '#1c1c1e', color: '#ffffff', icono: 'fab fa-apple' }],
    [/disney/i, { fondo: '#0f1a4a', color: '#9fc0ff', letra: 'D' }],
    [/youtube/i, { fondo: '#0f0f0f', color: '#ff0033', icono: 'fab fa-youtube' }],
    [/steam/i, { fondo: '#171a21', color: '#c7d5e0', icono: 'fab fa-steam' }],
    [/playstation/i, { fondo: '#003791', color: '#ffffff', icono: 'fab fa-playstation' }]
  ];

  var campoDesc = document.getElementById('campoDesc');
  var campoTipo = document.getElementById('campoTipo');
  var marca = document.getElementById('anotarMarca');
  var montoView = document.getElementById('montoView');
  var btnGuardar = document.getElementById('btnGuardar');

  function pintarMarca() {
    if (!marca) return;
    var texto = campoDesc ? campoDesc.value : '';
    var m = null;
    for (var i = 0; i < MARCAS.length; i++) {
      if (MARCAS[i][0].test(texto)) { m = MARCAS[i][1]; break; }
    }
    var esGasto = !campoTipo || campoTipo.value !== 'INGRESO';
    if (m) {
      marca.style.background = m.fondo;
      marca.style.color = m.color;
      marca.innerHTML = m.icono ? '<i class="' + m.icono + '"></i>' : m.letra;
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
})();
