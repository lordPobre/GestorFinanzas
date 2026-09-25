(function () {
  if (typeof Chart === 'undefined') return;
  var TICK = 'rgba(245, 245, 245, .62)';
  var TEXTO = 'rgba(245,245,245,.72)';
  var GRID = 'rgba(255,255,255,.06)';
  var FONT = "'Manrope', sans-serif";
  var tooltip = {
    backgroundColor: 'rgba(24,24,24,.97)', borderColor: 'rgba(255,255,255,.1)', borderWidth: 1,
    titleColor: '#f5f5f5', titleFont: { family: FONT, size: 12.5, weight: '700' },
    bodyColor: TEXTO, bodyFont: { family: FONT, size: 12 },
    padding: 13, cornerRadius: 14, boxPadding: 5, usePointStyle: true,
    callbacks: { label: function (c) { return ' ' + c.dataset.label + ': $' + Math.round(c.parsed.x || c.parsed.y).toLocaleString('es-CL'); } }
  };
  function corto(v) {
    v = Math.abs(v);
    if (v >= 1000000) return '$' + (v / 1000000).toFixed(1).replace('.', ',').replace(',0', '') + 'M';
    if (v >= 1000) return '$' + Math.round(v / 1000) + 'k';
    return '$' + Math.round(v);
  }

  function cuotasDato(nombre) {
    var c = document.getElementById('chartCuotas');
    if (!c || !c.dataset[nombre]) return [];
    try {
      var v = JSON.parse(c.dataset[nombre]);
      if (typeof v === 'string') v = JSON.parse(v);
      return Array.isArray(v) ? v : [];
    } catch (e) { return []; }
  }

  var cuotasEl = document.getElementById('chartCuotas');
  var labels = cuotasDato('labels');
  if (cuotasEl && labels.length) {
    new Chart(cuotasEl, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [

          { label: 'Cuota al mes', data: cuotasDato('data'),
            backgroundColor: '#ffaa2c', hoverBackgroundColor: '#ffbb56',
            borderRadius: 6, borderSkipped: false, maxBarThickness: 15 },

          { label: 'Te falta', data: cuotasDato('restante'),
            backgroundColor: '#818cf8', hoverBackgroundColor: '#9aa3fa',
            borderRadius: 6, borderSkipped: false, maxBarThickness: 15 }
        ]
      },
      options: {
        indexAxis: 'y',
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: TICK, font: { family: FONT, size: 11 }, usePointStyle: true, boxWidth: 7, padding: 14 } },
          tooltip: tooltip
        },
        scales: {
          x: { grid: { color: GRID }, border: { display: false },
               ticks: { color: TICK, font: { family: FONT, size: 10 },
                        callback: corto } },
          y: { grid: { display: false }, border: { display: false },
               ticks: { color: 'rgba(245,245,245,.72)', font: { family: FONT, size: 11, weight: '600' } } }
        }
      }
    });
  } else if (cuotasEl) {
    cuotasEl.parentElement.innerHTML =
      '<div class="empty" style="padding:36px 12px">' +
      '<i class="fas fa-credit-card" style="font-size:24px"></i>' +
      '<div class="empty-title" style="font-size:14px">Sin cuotas activas</div>' +
      '<div class="empty-text" style="font-size:11.5px">No tienes compras a plazo por pagar.</div></div>';
  }
})();
