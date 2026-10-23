const test = require('node:test');
const assert = require('node:assert/strict');
const { crearDocumento, ejecutar } = require('./dom_minimo');

function montar() {
  const documento = crearDocumento(
    '<form id="formRegistro"></form><input id="campoDesc"><button data-preset-tipo="EGRESO"></button>',
    { marcas: '/static/data/marcas.json' });
  const pedidos = [];
  const fetch = (url) => {
    pedidos.push(url);
    return Promise.resolve({ ok: true, json: () => ({ marcas: [], glifos: {} }) });
  };
  ejecutar('pantallas/anotar.js', { document: documento, window: { fetch, addEventListener() {} }, fetch });
  return { documento, pedidos };
}

test('las marcas no se piden al cargar la página', () => {
  assert.equal(montar().pedidos.length, 0);
});

test('se piden una sola vez al empezar a escribir', () => {
  const { documento, pedidos } = montar();
  const campo = documento.getElementById('campoDesc');
  campo.emitir('focus');
  campo.emitir('input');
  documento.querySelector('[data-preset-tipo]').click();
  assert.deepEqual(pedidos, ['/static/data/marcas.json']);
});

test('abrir el panel ya las pide', () => {
  const { documento, pedidos } = montar();
  documento.querySelector('[data-preset-tipo]').click();
  assert.equal(pedidos.length, 1);
});
