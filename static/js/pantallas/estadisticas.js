(function () {
  var el = document.getElementById('chartFlujo');
  if (!el || typeof Chart === 'undefined') return;

  function serie(nombre) {
    var bruto = el.dataset[nombre];
    if (!bruto) return [];
    try {
      var v = JSON.parse(bruto);
      if (typeof v === 'string') v = JSON.parse(v);
      return Array.isArray(v) ? v : [];
    } catch (e) { return []; }
  }

  var VERDE = '#53d258', CORAL = '#e25c5c';
  var TICK  = 'rgba(245, 245, 245, .62)';
  var TEXTO = 'rgba(245,245,245,.72)';
  var FONT  = "'Manrope', sans-serif";
  var quieto = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function angosto() { return (el.clientWidth || window.innerWidth) < 520; }

  var meses = serie('meses');
  var ingresos = serie('ingresos');

  var salidas = serie('gastos');

  function pesos(v) { return '$' + Math.round(v).toLocaleString('es-CL'); }
  function corto(v) {
    v = Math.abs(v);
    if (v >= 1000000) return '$' + (v / 1000000).toFixed(1).replace('.', ',').replace(',0', '') + 'M';
    if (v >= 1000) return '$' + Math.round(v / 1000) + 'k';
    return '$' + Math.round(v);
  }

  var faro = {
    id: 'faro',
    afterDatasetsDraw: function (chart) {
      var meta = chart.getDatasetMeta(0);
      if (!meta.data.length) return;
      var p = meta.data[meta.data.length - 1];
      if (!p) return;
      var c = chart.ctx;
      var t = chart.$pulso || 0;
      c.save();
      c.beginPath();
      c.arc(p.x, p.y, 5 + t * 7, 0, Math.PI * 2);
      c.fillStyle = 'rgba(83,210,88,' + (0.22 * (1 - t)) + ')';
      c.fill();
      c.beginPath();
      c.arc(p.x, p.y, 4.5, 0, Math.PI * 2);
      c.fillStyle = VERDE;
      c.fill();
      c.strokeStyle = '#383838';
      c.lineWidth = 2.5;
      c.stroke();
      c.restore();
    },
  };

  function rango(series) {
    var vals = [];
    series.forEach(function (s) {
      s.forEach(function (v) { if (v > 0) vals.push(v); });
    });
    if (!vals.length) return { piso: 0, techo: 100000 };
    var min = Math.min.apply(null, vals);
    var max = Math.max.apply(null, vals);
    var margen = Math.max((max - min) * 0.35, max * 0.08);
    var piso = Math.max(0, min - margen), techo = max + margen;
    var bruto = (techo - piso) / 4, pot = Math.pow(10, Math.floor(Math.log10(bruto)));
    var paso = [1, 2, 2.5, 5, 10].map(function (f) { return f * pot; }).filter(function (p) { return p >= bruto; })[0];
    return { piso: Math.floor(piso / paso) * paso, techo: Math.ceil(techo / paso) * paso, paso: paso };
  }
  var r0 = rango([ingresos, salidas]);
  var piso = r0.piso, techo = r0.techo;

  var chart = new Chart(el, {
    type: 'line',
    data: {
      labels: meses,
      datasets: [
        {
          label: 'Entra', data: ingresos,
          borderColor: VERDE, borderWidth: 2.5,

          fill: { target: '+1',
                  above: 'rgba(83,210,88,.17)',
                  below: 'rgba(226,92,92,.17)' },
          tension: 0.38,
          pointRadius: 0,
          pointHoverRadius: 6,
          pointHoverBackgroundColor: VERDE,
          pointHoverBorderColor: '#383838',
          pointHoverBorderWidth: 2.5,
        },
        {
          label: 'Sale', data: salidas,
          borderColor: CORAL, borderWidth: 2.5,
          fill: false,
          tension: 0.38,
          pointRadius: 0,
          pointHoverRadius: 6,
          pointHoverBackgroundColor: CORAL,
          pointHoverBorderColor: '#383838',
          pointHoverBorderWidth: 2.5,
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: quieto ? false : { duration: 900, easing: 'easeOutQuart' },
      interaction: { mode: 'index', intersect: false, axis: 'x' },
      layout: { padding: { top: 10, right: 10, bottom: 0, left: 0 } },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(24,24,24,.97)',
          borderColor: 'rgba(255,255,255,.1)',
          borderWidth: 1,
          titleColor: '#f5f5f5',
          titleFont: { family: FONT, size: 12.5, weight: '800' },
          bodyColor: TEXTO,
          bodyFont: { family: FONT, size: 12 },
          footerColor: '#ffaa2c',
          footerFont: { family: FONT, size: 11.5, weight: '700' },
          padding: 14, cornerRadius: 14, caretSize: 6,
          usePointStyle: true, boxWidth: 8, boxHeight: 8, boxPadding: 6,
          callbacks: {
            label: function (c) { return ' ' + c.dataset.label + ': ' + pesos(c.parsed.y); },

            footer: function (items) {
              if (items.length < 2) return '';
              var i = items[0].dataIndex;
              var saldo = (chart.data.datasets[0].data[i] || 0) - (chart.data.datasets[1].data[i] || 0);
              return (saldo >= 0 ? '↑ Te quedaron ' : '↓ Te faltaron ') + pesos(Math.abs(saldo));
            },
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          border: { color: 'rgba(255,255,255,.08)' },
          ticks: { color: TICK,
                   font: function () { return { family: FONT, size: angosto() ? 10 : 11, weight: '600' }; },
                   maxRotation: 0, minRotation: 0, padding: 8,
                   autoSkip: true, autoSkipPadding: 14,

                   callback: function (v) {
                     var l = this.getLabelForValue(v);
                     return angosto() ? String(l).split(' ')[0] : l;
                   } },
        },
        y: {
          grid: { color: 'rgba(255,255,255,.06)', drawTicks: false },
          border: { display: false },

          min: piso, max: techo,
          ticks: { color: TICK, font: { family: FONT, size: 10.5 },
                   stepSize: r0.paso, maxTicksLimit: 7, padding: 10, callback: corto },
        },
      },
    },
    plugins: [faro],
  });

  if (!quieto) {
    var t0 = null;
    (function pulsar(ts) {
      if (t0 === null) t0 = ts;
      var ciclo = ((ts - t0) % 2200) / 2200;
      chart.$pulso = ciclo;
      chart.draw();
      if (!document.hidden) window.requestAnimationFrame(pulsar);
      else window.setTimeout(function () { window.requestAnimationFrame(pulsar); }, 400);
    })(0);
  }

  var conDatos = meses.filter(function (m, i) { return ingresos[i] > 0 || salidas[i] > 0; }).length;
  if (conDatos <= 1) {
    var nota = document.getElementById('notaPocoHistorial');
    if (nota) nota.style.display = 'block';
  }

  var seg = document.getElementById('segRango');
  if (seg) {
    seg.addEventListener('click', function (e) {
      var b = e.target.closest('button');
      if (!b) return;
      seg.querySelectorAll('button').forEach(function (x) { x.classList.remove('on'); });
      b.classList.add('on');
      var n = Number(b.dataset.meses);
      chart.data.labels = meses.slice(-n);
      chart.data.datasets[0].data = ingresos.slice(-n);
      chart.data.datasets[1].data = salidas.slice(-n);
      var r = rango([ingresos.slice(-n), salidas.slice(-n)]);
      chart.options.scales.y.min = r.piso;
      chart.options.scales.y.max = r.techo;
      chart.options.scales.y.ticks.stepSize = r.paso;
      chart.update();
    });
  }
})();
