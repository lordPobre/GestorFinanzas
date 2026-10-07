const test = require('node:test');
const assert = require('node:assert/strict');
const { crearDocumento, ejecutar } = require('./dom_minimo');

const GASTOS = [['Comida', 'Comida y Supermercado'], ['Transporte', 'Transporte']];
const INGRESOS = [['Sueldo', 'Sueldo'], ['Extra', 'Ingreso extra']];

const TECLAS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0', 'del']
  .map((k) => `<button data-key="${k}"></button>`).join('');

const HTML = `
<div class="modal-overlay" id="modalGasto">
  <form id="formRegistro">
    <input id="campoTipo"><input id="campoCategoria"><input id="campoMonto"><input id="campoSinPagar">
    <div id="segTipo"><button data-tipo="EGRESO"></button><button data-tipo="INGRESO"></button></div>
    <div id="montoView"></div>
    <div id="avisoMonto"></div>
    <span id="labelCat"></span>
    <div id="chipsGasto"></div>
    <span id="labelFecha"></span>
    <div id="bloquePago">
      <div id="segPago"><button data-pagado="1" class="on-green"></button><button data-pagado="0"></button></div>
      <div id="notaPago"></div>
    </div>
    <div class="preview-box"><span data-preview data-base="100000" data-dias="10"></span><span data-preview-dia></span></div>
    <div class="keypad">${TECLAS}</div>
  </form>
</div>
<button id="presetIngreso" data-preset-tipo="INGRESO"></button>`;

function montar({ abrir = false, egresos = JSON.stringify(GASTOS), ingresos = JSON.stringify(INGRESOS) } = {}) {
  const documento = crearDocumento(HTML, abrir ? { abrirPanel: '1' } : {});
  const chips = documento.getElementById('chipsGasto');
  chips.dataset.egreso = egresos;
  chips.dataset.ingreso = ingresos;
  ejecutar('pantallas/base-4.js', { document: documento });
  const $ = (id) => documento.getElementById(id);
  const apretar = (teclas) => {
    for (const k of teclas) documento.querySelector(`.keypad [data-key="${k}"]`).click();
  };
  const valores = (lista) => lista.map((b) => b.dataset.value).join(',');
  return { documento, $, apretar, valores };
}

test('al abrir queda listo para anotar un gasto', () => {
  const { $, valores } = montar();
  assert.equal($('campoTipo').value, 'EGRESO');
  assert.equal(valores($('chipsGasto').querySelectorAll('button')), 'Comida,Transporte');
  assert.equal($('chipsGasto').querySelector('.chip.on').dataset.value, 'Comida');
  assert.equal($('campoCategoria').value, 'Comida');
  assert.equal($('labelCat').textContent, 'Categoría');
  assert.equal($('labelFecha').textContent, 'Fecha del gasto');
  assert.equal($('bloquePago').style.display, 'block');
  assert.equal($('montoView').textContent, '$0');
});

test('pasar a ingreso cambia las categorías, los textos y oculta si ya se pagó', () => {
  const { documento, $, valores } = montar();
  documento.querySelector('#segTipo [data-tipo="INGRESO"]').click();
  assert.equal($('campoTipo').value, 'INGRESO');
  assert.equal(valores($('chipsGasto').querySelectorAll('button')), 'Sueldo,Extra');
  assert.equal($('campoCategoria').value, 'Sueldo');
  assert.equal($('labelCat').textContent, 'De dónde viene');
  assert.equal($('labelFecha').textContent, 'Fecha del ingreso');
  assert.equal($('bloquePago').style.display, 'none');
  assert.equal(documento.querySelector('#segTipo [data-tipo="INGRESO"]').className, 'on-green');
  assert.equal(documento.querySelector('#segTipo [data-tipo="EGRESO"]').className, '');
  assert.equal(documento.querySelector('[data-preview]').dataset.sign, '1');
});

test('tocar una categoría la marca y la deja en el formulario', () => {
  const { $ } = montar();
  $('chipsGasto').querySelector('[data-value="Transporte"]').click();
  assert.equal($('campoCategoria').value, 'Transporte');
  assert.equal($('chipsGasto').querySelectorAll('.on').length, 1);
  assert.equal($('chipsGasto').querySelector('.on').dataset.value, 'Transporte');
});

test('el teclado arma el monto y descuenta un gasto de lo que queda', () => {
  const { documento, $, apretar } = montar();
  apretar(['1', '2', '5', '0', '0']);
  assert.equal($('campoMonto').value, '12500');
  assert.equal($('montoView').textContent, '$12.500');
  assert.equal(documento.querySelector('[data-preview]').textContent, '$87.500');
  assert.equal(documento.querySelector('[data-preview-dia]').textContent, '$8.750');
  apretar(['del']);
  assert.equal($('campoMonto').value, '1250');
});

test('el teclado no deja ceros a la izquierda ni más de nueve dígitos', () => {
  const { $, apretar } = montar();
  apretar(['0', '0', '5']);
  assert.equal($('campoMonto').value, '5');
  apretar(['del', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0']);
  assert.equal($('campoMonto').value, '123456789');
});

test('un ingreso suma a lo que queda', () => {
  const { documento, apretar } = montar();
  documento.querySelector('#segTipo [data-tipo="INGRESO"]').click();
  apretar(['5', '0', '0', '0', '0']);
  assert.equal(documento.querySelector('[data-preview]').textContent, '$150.000');
});

test('un gasto mayor a lo que queda pinta la cifra en coral', () => {
  const { documento, apretar } = montar();
  apretar(['1', '5', '0', '0', '0', '0']);
  const vista = documento.querySelector('[data-preview]');
  assert.equal(vista.textContent, '$-50.000');
  assert.equal(vista.style.color, 'var(--coral)');
});

test('enviar sin monto no guarda y avisa', () => {
  const { $ } = montar();
  const evento = $('formRegistro').emitir('submit');
  assert.equal(evento.defaultPrevented, true);
  assert.equal($('avisoMonto').style.display, 'block');
  assert.equal($('montoView').style.color, 'var(--coral)');
});

test('con monto el formulario se envía y el aviso se esconde', () => {
  const { $, apretar } = montar();
  $('formRegistro').emitir('submit');
  apretar(['9']);
  assert.equal($('avisoMonto').style.display, 'none');
  assert.equal($('formRegistro').emitir('submit').defaultPrevented, false);
});

test('«lo pago después» lo deja pendiente y «ya lo pagué» lo devuelve', () => {
  const { documento, $ } = montar();
  documento.querySelector('#segPago [data-pagado="0"]').click();
  assert.equal($('campoSinPagar').value, '1');
  assert.match($('notaPago').textContent, /Queda en la lista de pagos del mes/);
  assert.equal(documento.querySelector('#segPago [data-pagado="0"]').className, 'on-coral');
  documento.querySelector('#segPago [data-pagado="1"]').click();
  assert.equal($('campoSinPagar').value, '');
  assert.match($('notaPago').textContent, /Cuenta como gasto del mes/);
  assert.equal(documento.querySelector('#segPago [data-pagado="1"]').className, 'on-green');
});

test('el botón de ingreso abre el panel ya en ingreso y sin el aviso', () => {
  const { $ } = montar();
  $('formRegistro').emitir('submit');
  $('presetIngreso').click();
  assert.equal($('campoTipo').value, 'INGRESO');
  assert.equal($('avisoMonto').style.display, 'none');
});

test('con data-abrir-panel el panel queda abierto al cargar', () => {
  const { documento, $ } = montar({ abrir: true });
  assert.equal($('modalGasto').classList.contains('open'), true);
  assert.equal(documento.body.style.overflow, 'hidden');
  assert.equal(montar().$('modalGasto').classList.contains('open'), false);
});

test('acepta las categorías aunque vengan codificadas dos veces', () => {
  const { $, valores } = montar({ egresos: JSON.stringify(JSON.stringify(GASTOS)) });
  assert.equal(valores($('chipsGasto').querySelectorAll('button')), 'Comida,Transporte');
});
