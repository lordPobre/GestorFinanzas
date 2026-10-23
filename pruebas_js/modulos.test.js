const test = require('node:test');
const assert = require('node:assert/strict');
const { crearDocumento, ejecutar } = require('./dom_minimo');

test('como módulo, panel-carga lee sus datos desde su etiqueta', () => {
  const documento = crearDocumento(`
<script data-js="panel-carga" data-anotar="/a.js" data-tope="/t.js" data-panel="/p.js" data-marcas="/m.json"></script>
<div id="modalGasto"></div>
<button id="gasto" data-open="#modalGasto" data-preset-tipo="EGRESO"></button>`);
  documento.currentScript = null;
  ejecutar('pantallas/panel-carga.js', { document: documento, window: { addEventListener() {} } });
  documento.getElementById('gasto').click();
  const pedidos = documento.querySelectorAll('script').filter((s) => !s.dataset.js);
  assert.equal(pedidos.length, 1);
  assert.equal(pedidos[0].src, '/a.js');
  assert.equal(pedidos[0].dataset.marcas, '/m.json');
});

test('como módulo, tour-arranque lee sus datos desde su etiqueta', () => {
  const documento = crearDocumento('<script data-js="tour-arranque" data-src="/tour.js"></script>');
  documento.currentScript = null;
  const memoria = { getItem: () => null, setItem() {}, removeItem() {} };
  ejecutar('pantallas/tour-arranque.js', {
    document: documento, window: { addEventListener() {} }, localStorage: memoria, location: { search: '?tour=1' },
  });
  const pedidos = documento.querySelectorAll('script').filter((s) => !s.dataset.js);
  assert.equal(pedidos.length, 1);
  assert.equal(pedidos[0].src, '/tour.js');
});
