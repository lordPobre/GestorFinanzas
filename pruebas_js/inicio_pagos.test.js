const test = require('node:test');
const assert = require('node:assert/strict');
const { crearDocumento, ejecutar, memoria } = require('./dom_minimo');

const HOY = '2026-10-07';

function pago({ fecha, monto = 1000, atrasado = false }) {
  return `<div class="ini-pago${atrasado ? ' atrasado' : ''}" data-fecha="${fecha}" data-monto="${monto}"></div>`;
}

function fila({ fecha, atrasado = false }) {
  return `<div class="ini-fila${atrasado ? ' atrasado' : ''}" data-fecha="${fecha}"></div>`;
}

function montar({ pagos = [], filas = [], barras = null, guardada = null } = {}) {
  const html = `
<div data-pestanas><button data-pestana="pagar"></button><button data-pestana="movimientos"></button></div>
<div class="ini-panel"><section data-panel="pagar"></section><section data-panel="movimientos"></section></div>
<div data-lista-pagar>${filas.map(fila).join('')}<p data-lista-pagar-vacia hidden></p></div>
<div data-linea data-hoy="${HOY}">
  <p data-linea-sub></p>
  <div data-regla>
    <div data-regla-dias></div>
    <span data-regla-hecho></span>
    <span data-regla-hoy></span>
    <p data-regla-vacia hidden></p>
    ${pagos.map(pago).join('')}
  </div>
</div>
<div data-barras></div>
<p data-comparar></p>`;
  const documento = crearDocumento(html);
  if (barras) Object.assign(documento.querySelector('[data-barras]').dataset, barras);
  const sesion = memoria(guardada ? { 'fintora-pestana-inicio': guardada } : {});
  ejecutar('pantallas/dashboard.js', { document: documento, sessionStorage: sesion });
  const regla = documento.querySelector('[data-regla]');
  return {
    documento,
    sesion,
    regla,
    sub: documento.querySelector('[data-linea-sub]').textContent,
    vacia: documento.querySelector('[data-regla-vacia]'),
    tarjetas: regla.querySelectorAll('.ini-pago'),
  };
}

test('sin pestaña guardada muestra «Por pagar»', () => {
  const { documento } = montar();
  const pagar = documento.querySelector('[data-pestana="pagar"]');
  assert.equal(pagar.classList.contains('on'), true);
  assert.equal(pagar.getAttribute('aria-selected'), 'true');
  assert.equal(documento.querySelector('[data-panel="pagar"]').classList.contains('oculto-tel'), false);
  assert.equal(documento.querySelector('[data-panel="movimientos"]').classList.contains('oculto-tel'), true);
});

test('cambiar de pestaña la recuerda en la sesión', () => {
  const { documento, sesion } = montar();
  documento.querySelector('[data-pestana="movimientos"]').click();
  assert.equal(sesion.datos['fintora-pestana-inicio'], 'movimientos');
  assert.equal(documento.querySelector('[data-panel="pagar"]').classList.contains('oculto-tel'), true);
  assert.equal(montar({ guardada: 'movimientos' }).documento
    .querySelector('[data-pestana="movimientos"]').classList.contains('on'), true);
});

test('una pestaña guardada que ya no existe vuelve a «Por pagar»', () => {
  const { documento } = montar({ guardada: 'antigua' });
  assert.equal(documento.querySelector('[data-pestana="pagar"]').classList.contains('on'), true);
});

test('en el teléfono marca como pronto lo que vence en 7 días', () => {
  const { documento } = montar({
    filas: [{ fecha: '2026-10-10' }, { fecha: '2026-10-20' }, { fecha: '2026-10-01', atrasado: true }],
  });
  const filas = documento.querySelectorAll('.ini-fila');
  assert.equal(filas[0].classList.contains('pronto'), true);
  assert.equal(filas[1].classList.contains('pronto'), false);
  assert.equal(filas[2].classList.contains('pronto'), false);
  assert.equal(documento.querySelector('[data-lista-pagar-vacia]').hidden, true);
});

test('en el teléfono sin pagos muestra el mensaje de lista vacía', () => {
  const { documento } = montar();
  assert.equal(documento.querySelector('[data-lista-pagar-vacia]').hidden, false);
});

test('la línea suma lo atrasado y lo de los próximos días', () => {
  const { sub, vacia, tarjetas, regla } = montar({
    pagos: [
      { fecha: '2026-10-06', monto: 50000, atrasado: true },
      { fecha: '2026-10-09', monto: 31000 },
      { fecha: '2026-10-16', monto: 9990 },
      { fecha: '2026-10-30', monto: 20000 },
    ],
  });
  assert.equal(sub, '$90.990 por pagar en 3 pagos');
  assert.equal(vacia.hidden, true);
  assert.equal(tarjetas[1].classList.contains('pronto'), true);
  assert.equal(tarjetas[2].classList.contains('luego'), true);
  assert.equal(tarjetas[3].hidden, true);
  assert.equal(regla.querySelectorAll('.ini-palito').length, 3);
  assert.equal(regla.querySelectorAll('.ini-palito.atraso').length, 1);
});

test('varios atrasados se juntan en una sola tarjeta que abre la lista', () => {
  const { sub, regla } = montar({
    pagos: [
      { fecha: '2026-10-01', monto: 10000, atrasado: true },
      { fecha: '2026-10-03', monto: 20000, atrasado: true },
      { fecha: '2026-10-05', monto: 5000, atrasado: true },
    ],
  });
  const atrasados = regla.querySelectorAll('.ini-pago.atrasado');
  assert.equal(atrasados.length, 1);
  assert.equal(atrasados[0].classList.contains('grupo'), true);
  assert.equal(atrasados[0].getAttribute('data-open'), '#modalAtrasados');
  assert.match(atrasados[0].textContent, /3 pagos atrasados/);
  assert.match(atrasados[0].textContent, /\$35\.000 en total/);
  assert.equal(sub, '$35.000 por pagar en 3 pagos');
});

test('lo que no cabe en la línea se cuenta aparte', () => {
  const pagos = Array.from({ length: 5 }, () => ({ fecha: '2026-10-08', monto: 1000 }));
  const { sub, regla } = montar({ pagos });
  assert.equal(sub, '$3.000 por pagar en 3 pagos · 2 más en el calendario');
  assert.equal(regla.querySelectorAll('.ini-pago').filter((t) => t.hidden).length, 2);
  assert.equal(regla.style.height, '246px');
});

test('sin pagos cercanos la línea lo dice', () => {
  const { sub, vacia } = montar({ pagos: [{ fecha: '2026-11-15' }] });
  assert.equal(sub, 'Nada por pagar en estos días');
  assert.equal(vacia.hidden, false);
});

test('las barras comparan el gasto del mes con el anterior', () => {
  const meses = JSON.stringify(['agosto 2026', 'septiembre 2026', 'octubre 2026']);
  const menos = montar({ barras: { meses, gastos: '[60000, 80000, 70000]', cuotas: '[0, 20000, 10000]' } });
  const comparar = menos.documento.querySelector('[data-comparar]');
  assert.equal(comparar.textContent, 'Gastas 20% menos que en septiembre');
  assert.equal(comparar.classList.contains('sube'), false);
  const columnas = menos.documento.querySelectorAll('.ini-barra-col');
  assert.equal(columnas.length, 3);
  assert.equal(columnas[2].classList.contains('actual'), true);
  assert.equal(columnas[1].querySelector('i').style.height, '90%');

  const mas = montar({ barras: { meses, gastos: '[60000, 80000, 100000]', cuotas: '[0, 20000, 20000]' } });
  const subeTexto = mas.documento.querySelector('[data-comparar]');
  assert.equal(subeTexto.textContent, 'Gastas 20% más que en septiembre');
  assert.equal(subeTexto.classList.contains('sube'), true);
});
