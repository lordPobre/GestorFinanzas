(function () {
  var DIA = 86400000;
  var MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];

  function fecha(s) {
    var p = (s || '').split('-').map(Number);
    return p.length === 3 && p[0] ? Date.UTC(p[0], p[1] - 1, p[2]) : NaN;
  }
  function plata(n) { return '$' + Math.round(n).toLocaleString('es-CL'); }
  function serie(el, nombre) {
    var bruto = el.dataset[nombre];
    if (!bruto) return [];
    try {
      var v = JSON.parse(bruto);
      if (typeof v === 'string') v = JSON.parse(v);
      return Array.isArray(v) ? v : [];
    } catch (e) { return []; }
  }

  var linea = document.querySelector('[data-linea]');
  var base = linea ? fecha(linea.dataset.hoy) : NaN;

  (function pestanas() {
    var barra = document.querySelector('[data-pestanas]');
    if (!barra) return;
    var paneles = document.querySelectorAll('.ini-panel [data-panel]');
    function mostrar(cual) {
      barra.querySelectorAll('button').forEach(function (b) {
        var on = b.dataset.pestana === cual;
        b.classList.toggle('on', on);
        b.setAttribute('aria-selected', on ? 'true' : 'false');
      });
      paneles.forEach(function (p) { p.classList.toggle('oculto-tel', p.dataset.panel !== cual); });
      try { sessionStorage.setItem('fintora-pestana-inicio', cual); } catch (e) {}
    }
    barra.addEventListener('click', function (e) {
      var b = e.target.closest('button');
      if (b) mostrar(b.dataset.pestana);
    });
    var guardada = null;
    try { guardada = sessionStorage.getItem('fintora-pestana-inicio'); } catch (e) {}
    if (!guardada || !barra.querySelector('[data-pestana="' + guardada + '"]')) guardada = 'pagar';
    mostrar(guardada);
  })();

  (function listaTelefono() {
    var lista = document.querySelector('[data-lista-pagar]');
    if (!lista) return;
    var filas = lista.querySelectorAll('.ini-fila');
    if (!filas.length) { lista.querySelector('[data-lista-pagar-vacia]').hidden = false; return; }
    if (isNaN(base)) return;
    filas.forEach(function (f) {
      if (f.classList.contains('atrasado')) return;
      var dif = Math.round((fecha(f.dataset.fecha) - base) / DIA);
      if (dif <= 7) f.classList.add('pronto');
    });
  })();

  (function regla() {
    if (!linea || isNaN(base)) return;
    var caja = linea.querySelector('[data-regla]');
    var dias = caja.querySelector('[data-regla-dias]');
    var sub = linea.querySelector('[data-linea-sub]');
    var vacia = caja.querySelector('[data-regla-vacia]');
    var ANTES = 3, TOTAL = 15, FILA = 64, GAP = 10;
    var etiquetas = [];
    for (var k = 0; k < TOTAL; k++) {
      var d = new Date(base + (k - ANTES) * DIA);
      var s = document.createElement('span');
      s.textContent = k === ANTES ? 'Hoy' : String(d.getUTCDate());
      if (k === ANTES) s.className = 'hoy';
      dias.appendChild(s);
      etiquetas.push(s);
    }

    var tarjetas = Array.prototype.slice.call(caja.querySelectorAll('.ini-pago'));
    var atrasados = tarjetas.filter(function (t) { return t.classList.contains('atrasado'); });
    var items = [];

    if (atrasados.length === 1) {
      var dif0 = Math.round((fecha(atrasados[0].dataset.fecha) - base) / DIA);
      items.push({ el: atrasados[0], col: Math.max(0, Math.min(ANTES - 1, dif0 + ANTES)), tono: 'atraso', monto: Number(atrasados[0].dataset.monto) || 0 });
    } else if (atrasados.length > 1) {
      var total = 0;
      atrasados.forEach(function (t) { total += Number(t.dataset.monto) || 0; t.remove(); });
      var g = document.createElement('div');
      g.setAttribute('role', 'button');
      g.tabIndex = 0;
      g.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); g.click(); } });
      g.className = 'ini-pago atrasado grupo';
      g.setAttribute('data-open', '#modalAtrasados');
      g.innerHTML = '<span class="ini-ficha"><i class="fas fa-triangle-exclamation"></i></span>' +
        '<span class="ini-pago-txt"><span class="ini-pago-nombre">' + atrasados.length + ' pagos atrasados</span>' +
        '<span class="ini-pago-meta">' + plata(total) + ' en total</span></span>' +
        '<span class="ini-pago-ver">Revisar</span>';
      caja.appendChild(g);
      items.push({ el: g, col: 0, tono: 'atraso', monto: total, n: atrasados.length });
    }

    tarjetas.forEach(function (t) {
      if (t.classList.contains('atrasado')) return;
      var dif = Math.round((fecha(t.dataset.fecha) - base) / DIA);
      if (isNaN(dif) || dif > TOTAL - ANTES - 1) { t.hidden = true; return; }
      var tono = dif <= 7 ? 'pronto' : 'luego';
      t.classList.add(tono);
      items.push({ el: t, col: Math.max(ANTES, dif + ANTES), tono: tono, monto: Number(t.dataset.monto) || 0 });
    });
    items.sort(function (a, b) { return a.col - b.col; });

    function x(col, W) { return col === 0 ? 1 : (col + 0.5) / TOTAL * W; }

    function pintar() {
      var W = caja.clientWidth;
      if (!W) return;
      caja.querySelectorAll('.ini-palito').forEach(function (p) { p.remove(); });
      etiquetas.forEach(function (e, i) { e.className = i === ANTES ? 'hoy' : ''; });
      var fin = [-Infinity, -Infinity, -Infinity];
      var filas = 1, suma = 0, cuenta = 0, fuera = 0;
      items.forEach(function (it) {
        it.el.hidden = false;
        it.el.style.visibility = 'hidden';
        it.el.style.left = '0px';
        it.fila = -1;
      });
      items.forEach(function (it) {
        var w = it.el.offsetWidth, cx = x(it.col, W);
        var ideal = it.col === 0 ? 0 : Math.max(0, Math.min(W - w, cx - w / 2));
        for (var r = 0; r < 3; r++) {
          var l = Math.max(ideal, fin[r] + GAP);
          if (l + w <= W && cx >= l && cx <= l + w) { it.left = l; it.fila = r; fin[r] = l + w; break; }
        }
        if (it.fila < 0) { fuera += it.n || 1; it.el.hidden = true; return; }
        filas = Math.max(filas, it.fila + 1);
        suma += it.monto;
        cuenta += it.n || 1;
      });
      var y = (filas - 1) * FILA + 92;
      caja.style.setProperty('--y', y + 'px');
      caja.style.height = (y + 26) + 'px';
      items.forEach(function (it) {
        if (it.fila < 0) return;
        var top = (filas - 1 - it.fila) * FILA;
        it.el.style.left = it.left + 'px';
        it.el.style.top = top + 'px';
        it.el.style.visibility = '';
        var palo = document.createElement('span');
        palo.className = 'ini-palito ' + it.tono;
        var arriba = top + it.el.offsetHeight + 8;
        palo.style.left = x(it.col, W) + 'px';
        palo.style.top = arriba + 'px';
        palo.style.height = Math.max(0, y - arriba) + 'px';
        caja.appendChild(palo);
        var et = etiquetas[it.col];
        if (et && it.col !== ANTES) et.classList.add(it.tono);
      });
      var hoyX = x(ANTES, W);
      caja.querySelector('[data-regla-hecho]').style.width = hoyX + 'px';
      caja.querySelector('[data-regla-hoy]').style.left = hoyX + 'px';
      vacia.hidden = cuenta > 0;
      if (sub) {
        sub.textContent = cuenta
          ? plata(suma) + ' por pagar en ' + cuenta + (cuenta === 1 ? ' pago' : ' pagos') + (fuera ? ' · ' + fuera + ' más en el calendario' : '')
          : 'Nada por pagar en estos días';
      }
    }

    pintar();
    var espera = null;
    window.addEventListener('resize', function () {
      if (espera) cancelAnimationFrame(espera);
      espera = requestAnimationFrame(pintar);
    });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(pintar);
  })();

  (function barras() {
    var caja = document.querySelector('[data-barras]');
    if (!caja) return;
    var meses = serie(caja, 'meses');
    var gastos = serie(caja, 'gastos');
    var cuotas = serie(caja, 'cuotas');
    var n = Math.min(6, meses.length);
    if (!n) return;
    var desde = meses.length - n;
    var vals = [], nombres = [];
    for (var i = desde; i < meses.length; i++) {
      vals.push((Number(gastos[i]) || 0) + (Number(cuotas[i]) || 0));
      var m = String(meses[i]).split(' ')[0];
      nombres.push(m.charAt(0).toUpperCase() + m.slice(1, 3).toLowerCase());
    }
    var max = Math.max.apply(null, vals.concat([1]));
    vals.forEach(function (v, k) {
      var col = document.createElement('div');
      col.className = 'ini-barra-col' + (k === n - 1 ? ' actual' : '');
      col.title = nombres[k] + ': ' + plata(v);
      var hueco = document.createElement('b');
      var barra = document.createElement('i');
      barra.style.height = (v > 0 ? Math.max(4, v / max * 90) : 2) + '%';
      hueco.appendChild(barra);
      var et = document.createElement('span');
      et.textContent = nombres[k];
      col.appendChild(hueco);
      col.appendChild(et);
      caja.appendChild(col);
    });

    var comparar = document.querySelector('[data-comparar]');
    if (!comparar || n < 2) return;
    var antes = vals[n - 2], ahora = vals[n - 1];
    var nombre = caja.dataset.anterior;
    if (!nombre) {
      var idx = MESES.findIndex(function (x) { return x.slice(0, 3) === nombres[n - 2].toLowerCase(); });
      nombre = idx >= 0 ? MESES[idx] : nombres[n - 2].toLowerCase();
    }
    if (antes <= 0) return;
    var pct = Math.round((1 - ahora / antes) * 100);
    if (pct > 0) comparar.textContent = 'Gastas ' + pct + '% menos que en ' + nombre;
    else if (pct < 0) { comparar.textContent = 'Gastas ' + Math.abs(pct) + '% más que en ' + nombre; comparar.classList.add('sube'); }
    else comparar.textContent = 'Igual que en ' + nombre;
  })();

  (function arrastre() {
    var x0 = 0, y0 = 0;
    document.addEventListener('pointerdown', function (e) { x0 = e.clientX; y0 = e.clientY; }, true);
    document.querySelectorAll('[data-tarjeta-link]').forEach(function (a) {
      a.addEventListener('click', function (e) {
        if (e.detail === 0) return;
        if (Math.abs(e.clientX - x0) > 10 || Math.abs(e.clientY - y0) > 10) e.preventDefault();
      });
    });
  })();
})();
