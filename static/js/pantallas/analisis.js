(function () {
  var script = document.currentScript;
  var GRID = 'rgba(255,255,255,.055)';
  var TICK = 'rgba(245, 245, 245, .62)';
  var FONT = "'Manrope', sans-serif";

  var el = document.getElementById('chartSerie');
  if (!el || !window.Chart || !script) return;

  var angosto = window.innerWidth < 720;
  var idxActual = Number(script.dataset.indiceActual || 0);
  var etiquetas = JSON.parse(document.getElementById('d-serie_meses_json').textContent);
  var pagado = JSON.parse(document.getElementById('d-serie_pagado_json').textContent);
  var pendiente = JSON.parse(document.getElementById('d-serie_pendiente_json').textContent);

  var marcaHoy = {
    id: 'marcaHoy',
    beforeDatasetsDraw: function (chart) {
      var x = chart.scales.x.getPixelForValue(idxActual);
      var area = chart.chartArea;
      var ancho = chart.scales.x.width / etiquetas.length;
      var c = chart.ctx;
      c.save();
      c.fillStyle = 'rgba(255,170,44,.07)';
      c.fillRect(x - ancho / 2, area.top, ancho, area.bottom - area.top);
      c.beginPath();
      c.setLineDash([4, 4]);
      c.lineWidth = 1;
      c.strokeStyle = 'rgba(255,170,44,.4)';
      c.moveTo(x + ancho / 2, area.top);
      c.lineTo(x + ancho / 2, area.bottom);
      c.stroke();
      c.setLineDash([]);
      if (!angosto) {
        c.fillStyle = '#ffaa2c';
        c.font = "10px 'Manrope', sans-serif";
        c.textAlign = 'center';
        c.fillText('este mes', x, area.top + 12);
      }
      c.restore();
    }
  };

  new Chart(el, {
    type: 'bar',
    data: {
      labels: etiquetas,
      datasets: [
        { label: 'Pagado', data: pagado,
          backgroundColor: 'rgba(52,211,153,.85)', stack: 'cuota',
          borderRadius: 5, borderSkipped: false, maxBarThickness: 26 },
        { label: 'Falta pagar', data: pendiente,
          backgroundColor: 'rgba(251,146,60,.85)', stack: 'cuota',
          borderRadius: 5, borderSkipped: false, maxBarThickness: 26 }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(33,33,33,.96)',
          borderColor: 'rgba(255,170,44,.28)', borderWidth: 1,
          titleFont: { family: "'Manrope', sans-serif", size: 12, weight: '600' },
          bodyFont: { family: FONT, size: 12 },
          footerFont: { family: FONT, size: 11, weight: '400' },
          footerColor: 'rgba(241,240,255,.5)',
          padding: 13, cornerRadius: 14, boxPadding: 5, usePointStyle: true,
          filter: function (c) { return c.parsed.y > 0; },
          callbacks: {
            title: function (items) {
              var i = items[0].dataIndex;
              var total = (pagado[i] || 0) + (pendiente[i] || 0);
              return items[0].label + ' · $' + total.toLocaleString('es-CL');
            },
            label: function (c) {
              return ' ' + c.dataset.label + ': $' + Math.round(c.parsed.y).toLocaleString('es-CL');
            },
            footer: function (items) {
              var i = items[0].dataIndex;
              if (!pendiente[i]) return 'Mes cerrado';
              if (i < idxActual) return 'Quedó sin pagar';
              if (i === idxActual) return 'Es lo que te toca este mes';
              return 'Todavía no vence';
            }
          }
        }
      },
      scales: {
        x: { stacked: true, grid: { display: false }, border: { display: false },
             ticks: { color: TICK, font: { family: FONT, size: angosto ? 9 : 10 },
                      maxRotation: 0, autoSkipPadding: angosto ? 26 : 8,
                      callback: function (v) {
                        var l = this.getLabelForValue(v);
                        return angosto ? String(l).split(' ')[0] : l;
                      } } },
        y: { stacked: true, grid: { color: GRID }, border: { display: false },
             beginAtZero: true,
             ticks: { color: TICK, font: { family: FONT, size: angosto ? 9 : 10 },
                      maxTicksLimit: angosto ? 5 : 7,
                      callback: function (v) { return '$' + (v / 1000) + 'k'; } } }
      }
    },
    plugins: [marcaHoy]
  });
})();
