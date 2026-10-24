(() => {
  const tarjeta = document.querySelector('[data-saldo-futuro]');
  if (!tarjeta || !window.fetch) return;
  const SVG = 'http://www.w3.org/2000/svg';

  function el(tag, clase, texto) {
    const n = document.createElement(tag);
    if (clase) n.className = clase;
    if (texto !== undefined) n.textContent = texto;
    return n;
  }

  function trazo(tag, atributos) {
    const n = document.createElementNS(SVG, tag);
    Object.keys(atributos).forEach((k) => n.setAttribute(k, atributos[k]));
    return n;
  }

  function dibujar(svg, d, ancho, alto) {
    svg.textContent = '';
    const saldos = d.dias.map((x) => x.s);
    const max = Math.max(d.inicio, ...saldos, 1);
    const min = Math.min(0, d.inicio, ...saldos);
    const margen = 6;
    const n = d.dias.length;
    const x = (i) => (n <= 1 ? ancho : (i / (n - 1)) * ancho);
    const y = (s) => margen + ((max - s) / (max - min || 1)) * (alto - margen * 2);
    let linea = `M0,${y(d.inicio)} L0,${y(saldos[0])}`;
    for (let i = 1; i < n; i += 1) linea += ` L${x(i)},${y(saldos[i - 1])} L${x(i)},${y(saldos[i])}`;
    if (n === 1) linea += ` L${ancho},${y(saldos[0])}`;
    const fondo = Math.min(alto, y(min));
    svg.appendChild(trazo('path', { class: 'sf-area', d: `${linea} L${n === 1 ? ancho : x(n - 1)},${fondo} L0,${fondo} Z` }));
    if (min < 0) svg.appendChild(trazo('line', { class: 'sf-cero', x1: 0, x2: ancho, y1: y(0), y2: y(0) }));
    svg.appendChild(trazo('path', { class: 'sf-trazo', d: linea }));
    d.dias.forEach((dia, i) => {
      if (dia.cobro) svg.appendChild(trazo('circle', { class: 'sf-punto', cx: x(i), cy: y(dia.s), r: alto > 80 ? 4.5 : 3.5 }));
    });
    svg.appendChild(trazo('circle', { class: 'sf-punta', cx: 0, cy: y(d.inicio), r: alto > 80 ? 5 : 4 }));
    svg.appendChild(trazo('circle', { class: 'sf-punta', cx: n === 1 ? ancho : x(n - 1), cy: y(saldos[n - 1]), r: alto > 80 ? 5 : 4 }));
  }

  function tarjetaMeses(contenedor, meses) {
    contenedor.textContent = '';
    meses.forEach((m) => {
      const caja = el('span', `sf-mes${m.justo ? ' justo' : ''}${m.negativo ? ' negativo' : ''}`);
      caja.appendChild(el('span', 'sf-mes-nombre', m.corto));
      caja.appendChild(el('span', 'sf-mes-monto', m.libre));
      contenedor.appendChild(caja);
    });
  }

  function detalle(d) {
    const fin = document.querySelector('[data-sf-fin]');
    if (!fin) return;
    document.querySelector('[data-sf-etq]').textContent = d.fin_negativo ? `Al ${d.ultimo} te faltarían` : `Llegas al ${d.ultimo} con`;
    fin.textContent = d.fin;
    fin.classList.toggle('negativo', d.fin_negativo);
    document.querySelector('[data-sf-ultimo]').textContent = d.ultimo;
    dibujar(document.querySelector('[data-sf-grande]'), d, 320, 104);

    const cobros = document.querySelector('[data-sf-cobros]');
    cobros.textContent = '';
    if (!d.cobros.length) cobros.appendChild(el('span', 'sf-vacio', 'No te quedan cobros este mes.'));
    d.cobros.forEach((c) => {
      const fila = el('div', 'sf-cobro');
      fila.appendChild(el('i'));
      fila.appendChild(el('span', 'sf-cobro-dia', c.dia));
      fila.appendChild(el('span', 'sf-cobro-nombre', c.nombre));
      fila.appendChild(el('span', 'sf-cobro-monto', c.monto));
      cobros.appendChild(fila);
    });
    if (d.mas_cobros) cobros.appendChild(el('span', 'sf-vacio', `Y ${d.mas_cobros} cobro${d.mas_cobros === 1 ? '' : 's'} más.`));

    const lista = document.querySelector('[data-sf-lista]');
    lista.textContent = '';
    d.meses.forEach((m) => {
      const fila = el('div', `sf-fila${m.justo ? ' justo' : ''}`);
      const cab = el('div', `sf-fila-cab${m.negativo ? ' negativo' : ''}`);
      cab.appendChild(el('span', 'sf-fila-nombre', m.nombre));
      if (m.justo) cab.appendChild(el('span', 'sf-chip', 'El más justo'));
      cab.appendChild(el('span', 'sf-fila-monto', m.libre));
      const barra = el('span', 'sf-barra');
      const lleno = el('span');
      lleno.style.setProperty('--pct', m.pct);
      barra.appendChild(lleno);
      fila.appendChild(cab);
      fila.appendChild(barra);
      lista.appendChild(fila);
    });

    document.querySelector('[data-sf-nota]').textContent = d.pocos_datos
      ? 'Con menos de 2 meses de historia, los meses que vienen son una estimación gruesa. Suma las cuotas, suscripciones y préstamos que ya conoces.'
      : 'Los meses que vienen usan tu mes típico de los últimos meses, más las cuotas, suscripciones y préstamos que ya conoces.';
  }

  function pintar(d) {
    if (!d || !d.ok || !d.dias || !d.dias.length) return;
    const sub = tarjeta.querySelector('[data-sf-sub]');
    sub.textContent = d.fin_negativo ? `A fin de mes te faltarían ${d.fin}` : `Llegas a fin de mes con ${d.fin}`;
    sub.classList.toggle('negativo', d.fin_negativo);
    dibujar(tarjeta.querySelector('[data-sf-chica]'), d, 320, 64);
    tarjetaMeses(tarjeta.querySelector('[data-sf-meses]'), d.meses);
    detalle(d);
    tarjeta.hidden = false;
  }

  fetch(tarjeta.dataset.url, { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
    .then((r) => (r.ok ? r.json() : null))
    .then(pintar)
    .catch(() => {});
})();
