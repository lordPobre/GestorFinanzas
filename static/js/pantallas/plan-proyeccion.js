(function () {
  var nodo = document.getElementById('d-plan');
  var $ = function (id) { return document.getElementById(id); };
  if (!nodo || !$('cuentaGrafico') || !$('dapGrafico')) return;
  var d = JSON.parse(nodo.textContent);
  var SVG = 'http://www.w3.org/2000/svg';
  var MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
               'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
  var CORTOS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];

  var estado = {
    ahorro: Number(d.ahorro) || 0,
    llevas: Number(d.llevas) || 0,
    tasaCuenta: 0,
    aporte: Number(d.ahorro) || 0,
    inicial: Number(d.meta) || 0,
    tasa: 0,
    plazo: 30,
    meses: 24
  };

  function plata(n) { return (d.simbolo || '$') + Math.round(n).toLocaleString('es-CL'); }
  function indice(n) { return d.mes - 1 + n - 1; }
  function mes(n) { var t = indice(n); return MESES[t % 12] + ' ' + (d.anio + Math.floor(t / 12)); }
  function corto(n) { var t = indice(n); return CORTOS[t % 12] + ' ' + (d.anio + Math.floor(t / 12)); }
  function mayus(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
  function meses(n) { return n + (n === 1 ? ' mes' : ' meses'); }
  function numero(txt) { return Number(String(txt || '').replace(/\D/g, '')) || 0; }
  function porcentaje(txt, tope) {
    var v = parseFloat(String(txt || '').replace(',', '.'));
    return isFinite(v) && v > 0 && v < tope ? v / 100 : 0;
  }

  function el(tag, attrs, padre) {
    var e = document.createElementNS(SVG, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (padre) padre.appendChild(e);
    return e;
  }

  function degradado(defs, id, color, arriba, abajo) {
    var g = el('linearGradient', { id: id, x1: 0, y1: 0, x2: 0, y2: 1 }, defs);
    el('stop', { offset: 0, 'stop-color': color, 'stop-opacity': arriba }, g);
    el('stop', { offset: 1, 'stop-color': color, 'stop-opacity': abajo }, g);
  }

  function eje(caja, textos, marca) {
    caja.innerHTML = '';
    textos.forEach(function (t, i) {
      var s = document.createElement('span');
      s.textContent = t;
      if (i === marca) s.className = 'marca';
      caja.appendChild(s);
    });
  }

  function grafico(caja, cfg) {
    caja.innerHTML = '';
    var W = 600, H = cfg.alto;
    var X = function (k) { return (k / cfg.n * W).toFixed(1); };
    var Y = function (v) { return (H - v / cfg.max * H).toFixed(1); };
    var puntos = function (lista) { return lista.map(function (v, k) { return X(k) + ',' + Y(v); }); };
    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, preserveAspectRatio: 'none', 'class': 'pl-graf-svg', 'aria-hidden': 'true', focusable: 'false' }, caja);
    svg.style.height = H + 'px';
    var defs = el('defs', {}, svg);
    (cfg.degradados || []).forEach(function (g) { degradado(defs, g[0], g[1], g[2], g[3]); });
    el('line', { x1: 0, y1: H / 2, x2: W, y2: H / 2, 'class': 'pl-graf-guia' }, svg);

    cfg.capas.forEach(function (c) {
      var p = puntos(c.valores), trazo;
      if (c.tipo === 'area') trazo = 'M0,' + H + ' L' + p.join(' L') + ' L' + W + ',' + H + ' Z';
      else if (c.tipo === 'banda') trazo = 'M' + p.join(' L') + ' L' + puntos(c.base).reverse().join(' L') + ' Z';
      else trazo = 'M' + p.join(' L');
      var attrs = { d: trazo };
      if (c.relleno) attrs.fill = c.relleno;
      if (c.clase) attrs['class'] = c.clase;
      el('path', attrs, svg);
    });

    if (cfg.meta != null) el('line', { x1: 0, y1: Y(cfg.meta), x2: W, y2: Y(cfg.meta), 'class': 'pl-graf-meta' }, svg);
    if (cfg.marca) el('line', { x1: X(cfg.marca), y1: 0, x2: X(cfg.marca), y2: H, 'class': 'pl-graf-marca' }, svg);
    var cursor = el('line', { x1: -10, y1: 0, x2: -10, y2: H, 'class': 'pl-graf-cursor' }, svg);

    if (cfg.etiquetaMeta) {
      var etq = document.createElement('span');
      etq.className = 'pl-graf-etq-meta';
      etq.textContent = cfg.etiquetaMeta;
      etq.style.top = Y(cfg.meta) + 'px';
      caja.appendChild(etq);
    }
    var punto = document.createElement('span');
    punto.className = 'pl-graf-punto';
    caja.appendChild(punto);

    function mover(x) {
      var b = caja.getBoundingClientRect();
      var k = Math.round(Math.max(0, Math.min(1, (x - b.left) / b.width)) * cfg.n);
      cursor.setAttribute('x1', X(k));
      cursor.setAttribute('x2', X(k));
      punto.style.left = (k / cfg.n * 100) + '%';
      punto.style.top = Y(cfg.seguir[k]) + 'px';
      punto.classList.add('on');
      cfg.alMover(k);
    }
    caja.onpointermove = function (e) { mover(e.clientX); };
    caja.onpointerdown = function (e) { mover(e.clientX); };
    caja.onpointerleave = function () {
      cursor.setAttribute('x1', -10);
      cursor.setAttribute('x2', -10);
      punto.classList.remove('on');
      cfg.alMover(null);
    };
  }

  function cuenta() {
    var r = estado.tasaCuenta ? Math.pow(1 + estado.tasaCuenta, 1 / 12) - 1 : 0;
    var saldo = estado.llevas, n = 0;
    while (saldo < d.meta && estado.ahorro > 0 && n < 240) { saldo = saldo * (1 + r) + estado.ahorro; n++; }
    var completo = saldo >= d.meta ? n : null;
    var tramo = Math.max(6, (completo === null ? 12 : completo) + 2);
    var saldos = [estado.llevas], puestos = [estado.llevas], s = estado.llevas;
    for (var k = 1; k <= tramo; k++) {
      s = s * (1 + r) + estado.ahorro;
      saldos.push(s);
      puestos.push(estado.llevas + estado.ahorro * k);
    }
    return { n: completo, tramo: tramo, saldos: saldos, puestos: puestos, r: r };
  }

  function pintarCuenta() {
    var c = cuenta();
    grafico($('cuentaGrafico'), {
      alto: 170,
      max: Math.max(c.saldos[c.tramo], d.meta) * 1.15,
      n: c.tramo,
      seguir: c.saldos,
      degradados: [['gCuenta', '#53d258', .75, .08]],
      capas: [
        { tipo: 'area', valores: c.saldos, relleno: 'url(#gCuenta)' },
        { tipo: 'linea', valores: c.saldos, clase: 'pl-graf-linea-verde' }
      ],
      meta: d.meta,
      etiquetaMeta: 'Meta ' + plata(d.meta),
      marca: c.n,
      alMover: function (k) {
        if (k === null) {
          $('cuentaHoverMes').textContent = 'Tu fondo en la cuenta de ahorro';
          $('cuentaHoverValor').textContent = '';
          return;
        }
        $('cuentaHoverMes').textContent = k === 0 ? 'Hoy' : mayus(mes(k));
        $('cuentaHoverValor').textContent = plata(c.saldos[k]) +
          (c.r && k ? ' · intereses ' + plata(c.saldos[k] - c.puestos[k]) : '');
      }
    });
    eje($('cuentaEje'), ['Hoy', c.n ? 'Completo: ' + corto(c.n) : '', corto(c.tramo)], 1);

    var r = $('planCuentaResultado');
    if (estado.llevas >= d.meta) r.textContent = 'Ya completaste el fondo.';
    else if (c.n === null) r.textContent = 'Sin aporte mensual el fondo no avanza.';
    else {
      r.textContent = 'Completas el fondo en ' + mes(c.n) + ', en ' + meses(c.n) + '.' +
        (c.r ? ' La cuenta te suma ' + plata(c.saldos[c.n] - c.puestos[c.n]) + ' de intereses en ese tiempo.' : '');
    }
    return c.n || 0;
  }

  function serieDeposito() {
    var r = estado.tasa, base = estado.inicial, espera = 0;
    var total = [base], puesto = [base];
    for (var k = 1; k <= estado.meses; k++) {
      if (estado.plazo === 30) {
        base = base * (1 + r) + estado.aporte;
      } else {
        espera += estado.aporte;
        if (k % 3 === 0) { base = base * (1 + r) + espera; espera = 0; }
      }
      total.push(base + espera);
      puesto.push(estado.inicial + estado.aporte * k);
    }
    return { total: total, puesto: puesto };
  }

  function pintarDeposito(desde) {
    var s = serieDeposito(), N = estado.meses, r = estado.tasa;
    var fin = s.total[N], puesto = s.puesto[N], interes = fin - puesto;

    document.querySelectorAll('[data-dap="inicio"]').forEach(function (e) { e.textContent = mes(desde); });
    document.querySelectorAll('[data-dap="aporte"]').forEach(function (e) { e.textContent = plata(estado.aporte); });
    document.querySelectorAll('[data-dap="meses"]').forEach(function (e) {
      e.textContent = N >= 12 && N % 12 === 0 ? N + ' meses (' + (N / 12) + (N === 12 ? ' año)' : ' años)') : N + ' meses';
    });
    $('dapTotal').textContent = plata(fin);
    $('dapPuesto').textContent = plata(puesto);
    $('dapInteres').textContent = r ? plata(interes) : '—';
    $('dapInteresCaja').classList.toggle('sin', !r);

    var capas = [{ tipo: 'area', valores: s.puesto, relleno: 'url(#gDapPuesto)' }];
    if (r) {
      capas.push({ tipo: 'banda', valores: s.total, base: s.puesto, relleno: 'url(#gDapInteres)' });
      capas.push({ tipo: 'linea', valores: s.total, clase: 'pl-graf-linea-verde' });
      capas.push({ tipo: 'linea', valores: s.puesto, clase: 'pl-graf-linea-azul' });
    }
    grafico($('dapGrafico'), {
      alto: 200,
      max: Math.max(fin, 1) * 1.1,
      n: N,
      seguir: s.total,
      degradados: [['gDapPuesto', '#4b8cff', .55, .12], ['gDapInteres', '#53d258', .9, .5]],
      capas: capas,
      alMover: function (k) {
        if (k === null) {
          $('dapHoverMes').textContent = 'Pasa el dedo por el gráfico';
          $('dapHoverValor').textContent = '';
          return;
        }
        $('dapHoverMes').textContent = mayus(mes(desde + k));
        $('dapHoverValor').textContent = r
          ? plata(s.total[k]) + ' · intereses ' + plata(s.total[k] - s.puesto[k])
          : plata(s.puesto[k]);
      }
    });
    eje($('dapEje'), [corto(desde), corto(desde + Math.round(N / 2)), corto(desde + N)]);

    var res = $('dapResultado');
    var plazoTxt = estado.plazo === 30 ? '30 días' : '90 días';
    var tasaTxt = $('dapTasa').value.replace('.', ',');
    res.classList.toggle('verde', !!r);
    res.classList.toggle('ambar', !r);
    if (!estado.aporte && !estado.inicial) res.textContent = 'Pon un monto inicial o algo para sumar al mes.';
    else if (r) {
      res.textContent = 'En ' + mes(desde + N) + ' tendrías ' + plata(fin) + ': ' + plata(puesto) +
        ' que pusiste y ' + plata(interes) + ' de intereses, con un depósito a ' + plazoTxt + ' al ' + tasaTxt + '%.';
    } else {
      res.textContent = 'Sin intereses, en ' + mes(desde + N) + ' tendrías ' + plata(puesto) +
        ' guardados. Escribe la tasa que te ofrece tu banco para ver cuánto ganarías.';
    }
    $('dapNota').textContent = (estado.plazo === 30
      ? 'Estimación antes de impuestos, con la tasa que escribiste. Supone que cada mes renuevas el depósito y le sumas lo que elegiste.'
      : 'Estimación antes de impuestos, con la tasa que escribiste. Lo que sumas cada mes entra al depósito en la siguiente renovación, cada 3 meses.') +
      ' La tasa cambia en cada renovación y Fintora no recomienda bancos ni instrumentos.';
  }

  function pintar() { pintarDeposito(pintarCuenta()); }

  function campoPlata(input, clave) {
    input.addEventListener('input', function () { estado[clave] = numero(input.value); pintar(); });
    input.addEventListener('blur', function () { input.value = estado[clave] ? plata(estado[clave]) : ''; });
  }
  function campoTasa(input, clave, tope) {
    input.addEventListener('input', function () {
      input.value = input.value.replace(/[^\d.,]/g, '');
      estado[clave] = porcentaje(input.value, tope);
      input.classList.toggle('error', !!input.value && !estado[clave]);
      pintar();
    });
  }

  var inAhorro = $('planAhorro');
  if (inAhorro) inAhorro.addEventListener('input', function () { estado.ahorro = +inAhorro.value; pintar(); });
  campoPlata($('cuentaLlevas'), 'llevas');
  campoTasa($('cuentaTasa'), 'tasaCuenta', 50);
  campoPlata($('dapInicial'), 'inicial');
  campoTasa($('dapTasa'), 'tasa', 20);
  $('dapAporte').addEventListener('input', function () { estado.aporte = +$('dapAporte').value; pintar(); });
  $('dapMeses').addEventListener('input', function () { estado.meses = +$('dapMeses').value; pintar(); });

  document.querySelectorAll('[data-dap-plazo]').forEach(function (b) {
    b.addEventListener('click', function () {
      estado.plazo = Number(b.dataset.dapPlazo);
      document.querySelectorAll('[data-dap-plazo]').forEach(function (o) {
        o.setAttribute('aria-pressed', o === b ? 'true' : 'false');
      });
      $('dapTasaLabel').textContent = estado.plazo === 30 ? 'Tasa por 30 días' : 'Tasa por 90 días';
      $('dapTasa').placeholder = estado.plazo === 30 ? 'Ej: 0,40' : 'Ej: 1,20';
      $('dapTasa').value = '';
      $('dapTasa').classList.remove('error');
      estado.tasa = 0;
      pintar();
    });
  });

  pintar();
})();
