(function () {
  var nombre = document.querySelector('[data-nombre-corto]');
  if (nombre) {
    var primero = nombre.textContent.trim().split(/\s+/)[0];
    if (primero) nombre.textContent = primero;
  }

  var caja = document.querySelector('[data-cielo]');
  if (!caja) return;
  var SVG = 'http://www.w3.org/2000/svg';
  var quieto = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var partes = null;

  function el(tag, attrs, padre) {
    var e = document.createElementNS(SVG, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (padre) padre.appendChild(e);
    return e;
  }

  function hora() {
    var d = new Date();
    return d.getHours() + d.getMinutes() / 60;
  }

  function esDia(h) { return h >= 7 && h < 20; }

  function construir(dia) {
    caja.innerHTML = '';
    var svg = el('svg', { viewBox: '0 0 46 30', 'aria-hidden': 'true', focusable: 'false' }, caja);
    partes = { dia: dia };
    if (dia) {
      el('path', { d: 'M4 26 Q23 -2 42 26', fill: 'none', stroke: 'rgba(255,208,138,.28)', 'stroke-width': 1, 'stroke-dasharray': '1.5 2.5' }, svg);
      el('line', { x1: 0, y1: 26.5, x2: 46, y2: 26.5, stroke: 'rgba(255,208,138,.35)', 'stroke-width': 1 }, svg);
      partes.brillo = el('circle', { r: 7.5, fill: '#ffbb56', 'class': 'cielo-brillo' }, svg);
      var grupo = el('g', { 'class': 'cielo-rayos' }, svg);
      partes.rayos = [];
      for (var a = 0; a < 360; a += 45) {
        partes.rayos.push({ ang: a * Math.PI / 180, linea: el('line', { stroke: '#ffd08a', 'stroke-width': 1.4, 'stroke-linecap': 'round' }, grupo) });
      }
      partes.sol = el('circle', { r: 4.6 }, svg);
    } else {
      var defs = el('defs', {}, svg);
      var mascara = el('mask', { id: 'cieloMedialuna' }, defs);
      el('rect', { x: 0, y: 0, width: 46, height: 30, fill: '#fff' }, mascara);
      partes.sombra = el('circle', { r: 5.2, fill: '#000' }, mascara);
      [[7, 8, 0, .9], [15, 21, .9, .7], [39, 7, 1.6, .8], [33, 24, .4, .6]].forEach(function (s) {
        var e = el('circle', { cx: s[0], cy: s[1], r: s[3], fill: '#e8eeff', 'class': 'cielo-estrella' }, svg);
        e.style.animationDelay = s[2] + 's';
      });
      partes.luna = el('g', { 'class': 'cielo-luna' }, svg);
      partes.halo = el('circle', { r: 8.5, fill: 'rgba(200,215,255,.14)' }, partes.luna);
      partes.disco = el('circle', { r: 6, fill: '#dfe7ff', mask: 'url(#cieloMedialuna)' }, partes.luna);
    }
  }

  function posicionar(avance) {
    var h = hora();
    var e = 1 - Math.pow(1 - avance, 3);
    if (partes.dia) {
      var t = Math.max(0, Math.min(1, (h - 7) / 13));
      var tv = t * e;
      var x = 6 + 34 * tv, y = 26 - 17 * Math.sin(Math.PI * tv);
      var tibio = t < .15 || t > .85;
      caja.className = 'saludo-cielo' + (tibio ? ' tibio' : '');
      partes.brillo.setAttribute('cx', x);
      partes.brillo.setAttribute('cy', y);
      partes.sol.setAttribute('cx', x);
      partes.sol.setAttribute('cy', y);
      partes.sol.setAttribute('fill', tibio ? '#ffa45c' : '#ffc24d');
      partes.rayos.forEach(function (r) {
        r.linea.setAttribute('x1', x + Math.cos(r.ang) * 6);
        r.linea.setAttribute('y1', y + Math.sin(r.ang) * 6);
        r.linea.setAttribute('x2', x + Math.cos(r.ang) * 8.2);
        r.linea.setAttribute('y2', y + Math.sin(r.ang) * 8.2);
      });
    } else {
      var n = h >= 20 ? (h - 20) / 11 : (h + 4) / 11;
      var mx = 12 + 22 * n, my = 13 - 4 * Math.sin(Math.PI * n) + (1 - e) * 14;
      caja.className = 'saludo-cielo noche';
      partes.halo.setAttribute('cx', mx);
      partes.halo.setAttribute('cy', my);
      partes.disco.setAttribute('cx', mx);
      partes.disco.setAttribute('cy', my);
      partes.sombra.setAttribute('cx', mx + 3.4);
      partes.sombra.setAttribute('cy', my - 2.2);
      partes.luna.style.opacity = e;
    }
  }

  function actualizar(avance) {
    var dia = esDia(hora());
    if (!partes || partes.dia !== dia) construir(dia);
    posicionar(avance);
  }

  if (quieto) {
    actualizar(1);
  } else {
    var inicio = null;
    var paso = function (t) {
      if (inicio === null) inicio = t;
      var a = Math.min(1, (t - inicio) / 1400);
      actualizar(a);
      if (a < 1) window.requestAnimationFrame(paso);
    };
    window.requestAnimationFrame(paso);
  }

  window.setInterval(function () { actualizar(1); }, 60000);
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) actualizar(1);
  });
})();
