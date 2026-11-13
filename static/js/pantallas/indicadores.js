(function () {
  var nodo = document.getElementById('datosIndicadores');
  var raiz = document.querySelector('[data-indicadores]');
  if (!nodo || !raiz) return;
  var series = JSON.parse(nodo.textContent || '{}');
  var META = [
    { id: 'dolar', nombre: 'Dólar', largo: 'Dólar observado', dec: 2, unidad: 'Dólares', corto: 'US$', uso: 'Sirve para compras en sitios de afuera y suscripciones en dólares. Cambia cada día hábil.' },
    { id: 'euro', nombre: 'Euro', largo: 'Euro', dec: 2, unidad: 'Euros', corto: '€', uso: 'Sirve para viajes y compras en Europa. Cambia cada día hábil.' },
    { id: 'uf', nombre: 'UF', largo: 'Unidad de fomento', dec: 2, unidad: 'UF', corto: 'UF', uso: 'Se usa en arriendos, dividendos, seguros y créditos. Cambia todos los días.' },
    { id: 'utm', nombre: 'UTM', largo: 'Unidad tributaria mensual', dec: 0, unidad: 'UTM', corto: 'UTM', uso: 'Se usa en multas, permiso de circulación y otros trámites. Cambia una vez al mes.' }
  ].filter(function (m) { return series[m.id] && series[m.id].length; });
  if (!META.length) return;

  var NS = 'http://www.w3.org/2000/svg';
  var W = 1000;
  var H = 260;
  var estado = { sel: META[0].id, rango: 30, alReves: false, vals: [], dias: [], pts: [], idx: null };
  var q = function (s) { return raiz.querySelector(s); };
  var hoja = q('[data-ind-hoja]');
  var graf = q('[data-ind-grafico]');
  var lista = q('[data-ind-lista]');
  var monto = q('[data-ind-monto]');

  function num(v, dec) { return v.toLocaleString('es-CL', { minimumFractionDigits: dec, maximumFractionDigits: dec }); }
  function plata(v, dec) { return '$' + num(v, dec); }
  function fecha(iso) { var p = iso.split('-'); return new Date(+p[0], +p[1] - 1, +p[2]); }
  function pct(a, b) {
    var p = a ? (b - a) / a * 100 : 0;
    return { txt: (p >= 0 ? '▲ ' : '▼ ') + num(Math.abs(p), 1) + '%', sube: p >= 0 };
  }
  function svgEl(tag, attrs) {
    var e = document.createElementNS(NS, tag);
    Object.keys(attrs).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    return e;
  }
  function trazar(vals, w, h) {
    var pad = Math.min(14, h * 0.12);
    var min = Math.min.apply(null, vals);
    var max = Math.max.apply(null, vals);
    var n = vals.length;
    if (max === min) { max += 1; min -= 1; }
    return vals.map(function (v, i) {
      return [n === 1 ? w / 2 : i / (n - 1) * w, pad + (1 - (v - min) / (max - min)) * (h - 2 * pad)];
    });
  }
  function texto(p) { return p.map(function (x) { return x[0].toFixed(1) + ',' + x[1].toFixed(1); }).join(' '); }
  function meta() { return META.find(function (m) { return m.id === estado.sel; }); }

  function cambioDe(m) {
    var s = series[m.id];
    var ult = s[s.length - 1][1];
    var j = s.length - 2;
    while (j > 0 && s[j][1] === ult) j--;
    var ant = s[Math.max(j, 0)][1];
    var sube = ult >= ant;
    var txt;
    if (m.id === 'utm') {
      txt = fecha(s[s.length - 1][0]).toLocaleDateString('es-CL', { month: 'long' });
      txt = txt.charAt(0).toUpperCase() + txt.slice(1);
    } else if (m.id === 'uf') {
      txt = (sube ? '+' : '−') + plata(Math.abs(ult - ant), 2);
    } else {
      txt = pct(ant, ult).txt;
    }
    return { txt: txt, sube: sube, valor: ult };
  }

  var tiles = META.map(function (m) {
    var c = cambioDe(m);
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'ind2c-tile ' + (c.sube ? 'sube' : 'baja');
    b.setAttribute('role', 'tab');
    var f1 = document.createElement('span');
    f1.className = 'ind2c-tile-fila';
    var nombre = document.createElement('b');
    nombre.textContent = m.nombre;
    var cambio = document.createElement('span');
    cambio.className = 'ind2c-tile-cambio';
    cambio.textContent = c.txt;
    f1.append(nombre, cambio);
    var f2 = document.createElement('span');
    f2.className = 'ind2c-tile-fila ind2c-tile-abajo';
    var valor = document.createElement('b');
    valor.className = 'ind2c-tile-valor';
    valor.textContent = plata(c.valor, m.dec);
    var spark = svgEl('svg', { viewBox: '0 0 96 28', preserveAspectRatio: 'none', class: 'ind2c-spark', 'aria-hidden': 'true' });
    spark.appendChild(svgEl('polyline', { points: texto(trazar(series[m.id].slice(-30).map(function (x) { return x[1]; }), 96, 28)) }));
    f2.append(valor, spark);
    b.append(f1, f2);
    b.addEventListener('click', function () {
      estado.sel = m.id;
      estado.alReves = false;
      monto.value = '1';
      vista();
    });
    lista.appendChild(b);
    return { id: m.id, el: b };
  });

  var svg = svgEl('svg', { viewBox: '0 0 ' + W + ' ' + H, preserveAspectRatio: 'none', 'aria-hidden': 'true' });
  var area = svgEl('path', { class: 'ind2c-area' });
  var linea = svgEl('polyline', { class: 'ind2c-linea' });
  svg.append(area, linea);
  var guia = document.createElement('span');
  guia.className = 'ind2c-guia';
  guia.hidden = true;
  var marca = document.createElement('span');
  marca.className = 'ind2c-marca';
  marca.hidden = true;
  graf.append(svg, guia, marca);

  function mostrar(i) {
    var m = meta();
    estado.idx = i;
    var n = estado.vals.length;
    if (i == null) {
      guia.hidden = true;
      marca.hidden = true;
      q('[data-ind-valor]').textContent = plata(estado.vals[n - 1], m.dec);
      q('[data-ind-fecha]').textContent = 'Hoy';
      return;
    }
    var p = estado.pts[i];
    guia.hidden = false;
    marca.hidden = false;
    guia.style.left = (p[0] / W * 100) + '%';
    marca.style.left = (p[0] / W * 100) + '%';
    marca.style.top = (p[1] / H * 100) + '%';
    q('[data-ind-valor]').textContent = plata(estado.vals[i], m.dec);
    q('[data-ind-fecha]').textContent = i === n - 1 ? 'Hoy' : fecha(estado.dias[i]).toLocaleDateString('es-CL', { weekday: 'long', day: 'numeric', month: 'long' });
  }

  function convertir() {
    var m = meta();
    var hoy = series[m.id][series[m.id].length - 1][1];
    var n = parseFloat(String(monto.value).replace(/\./g, '').replace(',', '.')) || 0;
    q('[data-ind-de]').textContent = estado.alReves ? 'Pesos' : m.unidad;
    q('[data-ind-a]').textContent = estado.alReves ? m.unidad + ', hoy' : 'En pesos, hoy';
    q('[data-ind-resultado]').textContent = estado.alReves
      ? num(n / hoy, 2) + ' ' + m.corto
      : '$' + Math.round(n * hoy).toLocaleString('es-CL');
    monto.setAttribute('aria-label', 'Monto en ' + (estado.alReves ? 'pesos' : m.unidad));
  }

  function vista() {
    var m = meta();
    var s = series[m.id].slice(-estado.rango);
    estado.vals = s.map(function (x) { return x[1]; });
    estado.dias = s.map(function (x) { return x[0]; });
    estado.pts = trazar(estado.vals, W, H);
    var c = pct(estado.vals[0], estado.vals[estado.vals.length - 1]);
    hoja.classList.toggle('sube', c.sube);
    hoja.classList.toggle('baja', !c.sube);
    linea.setAttribute('points', texto(estado.pts));
    area.setAttribute('d', 'M0,' + H + ' L' + texto(estado.pts).split(' ').join(' L') + ' L' + W + ',' + H + ' Z');
    var nombreRango = estado.rango === 7 ? 'en 7 días' : estado.rango === 30 ? 'en 30 días' : 'en un año';
    q('[data-ind-largo]').textContent = m.largo;
    q('[data-ind-cambio]').textContent = c.txt + ' ' + nombreRango;
    q('[data-ind-uso]').textContent = m.uso;
    q('[data-ind-desde]').textContent = fecha(estado.dias[0]).toLocaleDateString('es-CL', estado.rango === 365 ? { day: 'numeric', month: 'short', year: 'numeric' } : { day: 'numeric', month: 'short' });
    tiles.forEach(function (t) {
      var on = t.id === estado.sel;
      t.el.classList.toggle('on', on);
      t.el.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    raiz.querySelectorAll('[data-ind-rango]').forEach(function (b) {
      var on = +b.getAttribute('data-ind-rango') === estado.rango;
      b.classList.toggle('on', on);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    mostrar(null);
    convertir();
  }

  function indiceEn(x) {
    var r = graf.getBoundingClientRect();
    var n = estado.vals.length;
    return Math.max(0, Math.min(n - 1, Math.round((x - r.left) / r.width * (n - 1))));
  }
  graf.addEventListener('pointermove', function (e) { mostrar(indiceEn(e.clientX)); });
  graf.addEventListener('pointerdown', function (e) { mostrar(indiceEn(e.clientX)); });
  graf.addEventListener('pointerleave', function () { mostrar(null); });
  graf.addEventListener('pointercancel', function () { mostrar(null); });
  graf.addEventListener('blur', function () { mostrar(null); });
  graf.addEventListener('keydown', function (e) {
    var n = estado.vals.length;
    var i = estado.idx == null ? n - 1 : estado.idx;
    if (e.key === 'ArrowLeft') i = Math.max(0, i - 1);
    else if (e.key === 'ArrowRight') i = Math.min(n - 1, i + 1);
    else if (e.key === 'Home') i = 0;
    else if (e.key === 'End') i = n - 1;
    else return;
    e.preventDefault();
    mostrar(i);
  });
  raiz.querySelectorAll('[data-ind-rango]').forEach(function (b) {
    b.addEventListener('click', function () {
      estado.rango = +b.getAttribute('data-ind-rango');
      vista();
    });
  });
  monto.addEventListener('input', convertir);
  q('[data-ind-girar]').addEventListener('click', function () {
    estado.alReves = !estado.alReves;
    monto.value = estado.alReves ? '100.000' : '1';
    convertir();
  });
  vista();
})();
