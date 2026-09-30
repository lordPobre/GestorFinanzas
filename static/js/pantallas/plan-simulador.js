(() => {
  const caja = document.querySelector('[data-simulador]');
  const nodo = document.getElementById('d-plan');
  if (!caja || !nodo) return;
  const d = JSON.parse(nodo.textContent);
  const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
  const LARGOS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
                  'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
  const HORIZONTE = 12;
  const inCuota = document.getElementById('simCuota');
  const inCuotas = document.getElementById('simCuotas');
  const grafico = document.getElementById('simGrafico');
  const leyenda = document.getElementById('simLeyenda');
  const resultado = document.getElementById('simResultado');
  const inAhorro = document.getElementById('planAhorro');
  const inExtra = document.getElementById('planExtra');

  const plata = (n) => (n < 0 ? '−' : '') + (d.simbolo || '$') + Math.round(Math.abs(n)).toLocaleString('es-CL');
  const fecha = (k) => {
    const t = d.mes - 1 + k;
    return { mes: t % 12, anio: d.anio + Math.floor(t / 12) };
  };
  const nombreMes = (k) => { const f = fecha(k); return LARGOS[f.mes] + ' ' + f.anio; };
  const fines = (d.deudas || []).map((x) => ({ cuota: x.cuota, fin: Math.ceil(x.saldo / x.cuota) }));
  const liberado = (k) => fines.reduce((s, x) => s + (x.fin < k + 1 ? x.cuota : 0), 0);
  const numero = (el, min, max) => {
    const v = Math.round(Number(String(el.value).replace(/[^0-9]/g, '')) || 0);
    return Math.max(min, Math.min(max, v));
  };

  function mensaje(clase, texto, nota) {
    resultado.className = 'pl-resultado' + (clase ? ' ' + clase : '');
    resultado.textContent = texto;
    if (nota) {
      const s = document.createElement('small');
      s.textContent = nota;
      resultado.appendChild(s);
    }
  }

  function pintar() {
    const cuota = numero(inCuota, 0, 99999999);
    const n = numero(inCuotas, 1, 48);
    grafico.innerHTML = '';
    if (!cuota) {
      leyenda.hidden = true;
      mensaje('', 'Escribe el valor de la cuota para ver cómo quedarían tus meses.');
      return;
    }
    const plan = (inAhorro ? +inAhorro.value : 0) + (inExtra ? +inExtra.value : 0);
    const meses = [];
    for (let k = 1; k <= HORIZONTE; k++) {
      const sin = d.sobra + liberado(k);
      meses.push({ k, sin, con: sin - (k <= n ? cuota : 0) });
    }
    const maxPos = Math.max(1, ...meses.map((m) => Math.max(m.sin, m.con)));
    const maxNeg = Math.max(0, ...meses.map((m) => -Math.min(0, m.con)));
    const rango = maxPos + maxNeg;
    const alto = (v) => (Math.abs(v) / rango * 100) + '%';
    const cero = (maxNeg / rango * 100) + '%';

    meses.forEach((m) => {
      const col = document.createElement('div');
      col.className = 'pl-sim-col';
      col.title = nombreMes(m.k) + ': ' + plata(m.con) + ' libre con la compra';
      const area = document.createElement('div');
      area.className = 'pl-sim-area';
      const linea = document.createElement('span');
      linea.className = 'pl-sim-cero';
      linea.style.bottom = cero;
      const sin = document.createElement('span');
      sin.className = 'pl-sim-barra sin';
      sin.style.bottom = cero;
      sin.style.height = alto(m.sin);
      const con = document.createElement('span');
      con.className = 'pl-sim-barra con' + (m.con < 0 ? ' falta' : m.con < plan ? ' justo' : '');
      if (m.con >= 0) { con.style.bottom = cero; con.style.height = alto(m.con); }
      else { con.style.top = (100 - parseFloat(cero)) + '%'; con.style.height = alto(m.con); }
      area.appendChild(sin);
      area.appendChild(con);
      area.appendChild(linea);
      const et = document.createElement('span');
      const f = fecha(m.k);
      et.className = 'pl-sim-mes' + (f.mes === 0 ? ' anio' : '');
      et.textContent = MESES[f.mes];
      if (f.mes === 0) {
        const anio = document.createElement('b');
        anio.textContent = f.anio;
        et.appendChild(anio);
      }
      col.appendChild(area);
      col.appendChild(et);
      grafico.appendChild(col);
    });
    leyenda.hidden = false;

    const total = 'Pagarías ' + plata(cuota * n) + ' en ' + n + (n === 1 ? ' cuota' : ' cuotas') + '. La última sería en ' + nombreMes(n) + '.';
    const faltan = meses.filter((m) => m.con < 0);
    const peor = meses.reduce((a, b) => (b.con < a.con ? b : a));
    if (faltan.length) {
      mensaje('rojo', 'No te alcanza en ' + faltan.length + ' de los próximos 12 meses. En ' + nombreMes(peor.k) + ' te faltarían ' + plata(-peor.con) + '.', total);
    } else if (plan && peor.con < plan) {
      mensaje('ambar', 'Te alcanza, pero no para tu plan. En ' + nombreMes(peor.k) + ' te quedarían ' + plata(peor.con) + ' y hoy apartas ' + plata(plan) + ' entre ahorro y deudas.', total);
    } else {
      mensaje('verde', 'Te alcanza. En el mes más justo, ' + nombreMes(peor.k) + ', te quedan ' + plata(peor.con - plan) + ' libres después de tu plan.', total);
    }
  }

  [inCuota, inCuotas].forEach((el) => el.addEventListener('input', pintar));
  [inAhorro, inExtra].forEach((el) => { if (el) el.addEventListener('input', pintar); });
  pintar();
})();
