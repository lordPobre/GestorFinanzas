const test = require('node:test');
const assert = require('node:assert/strict');
const { crearDocumento, ejecutar } = require('./dom_minimo');

const RUTAS = { anotar: '/a.js', tope: '/t.js', panel: '/p.js', marcas: '/m.json' };

function montar({ abrir = false } = {}) {
  const documento = crearDocumento(`
<div class="modal-overlay" id="modalGasto"></div>
<div class="modal-overlay open" id="modalAnotar"><button id="enHoja" data-open="#modalGasto" data-preset-tipo="INGRESO"></button></div>
<button id="gasto" data-open="#modalGasto" data-preset-tipo="EGRESO"></button>
<button id="otro" data-open="#modalMas"></button>`, { ...RUTAS, ...(abrir ? { abrirPanel: '1' } : {}) });
  const abiertos = [];
  let observador = null;
  const ventana = {
    addEventListener() {},
    finappOpen: (id) => abiertos.push(id),
    MutationObserver: class { constructor(f) { observador = f; } observe() {} },
  };
  ejecutar('pantallas/panel-carga.js', { document: documento, window: ventana });
  const scripts = () => documento.querySelectorAll('script');
  const terminar = () => { let n = 0; while (n < scripts().length) { scripts()[n].onload(); n += 1; } };
  return { documento, abiertos, scripts, terminar, observar: () => observador() };
}

test('al cargar la página no pide nada', () => {
  assert.equal(montar().scripts().length, 0);
});

test('el primer toque carga los tres archivos en orden y recién ahí abre el panel', () => {
  const { documento, abiertos, scripts, terminar } = montar();
  const evento = documento.getElementById('gasto').click();
  assert.equal(evento.defaultPrevented, true);
  assert.equal(abiertos.length, 0);
  assert.deepEqual(scripts().map((s) => s.src), ['/a.js']);
  assert.equal(scripts()[0].dataset.marcas, '/m.json');
  terminar();
  assert.deepEqual(scripts().map((s) => s.src), ['/a.js', '/t.js', '/p.js']);
  assert.equal(scripts()[2].dataset.presetTipo, 'EGRESO');
  assert.deepEqual(abiertos, ['#modalGasto']);
});

test('después de cargar no se mete en los toques', () => {
  const { documento, scripts, terminar } = montar();
  documento.getElementById('gasto').click();
  terminar();
  assert.equal(documento.getElementById('gasto').click().defaultPrevented, false);
  assert.equal(scripts().length, 3);
});

test('tocar varias veces mientras carga no repite nada', () => {
  const { documento, abiertos, scripts, terminar } = montar();
  documento.getElementById('gasto').click();
  documento.getElementById('gasto').click();
  assert.equal(scripts().length, 1);
  terminar();
  assert.equal(scripts().length, 3);
  assert.equal(abiertos.length, 1);
});

test('el botón de la hoja pasa el ingreso y cierra la hoja', () => {
  const { documento, scripts, terminar } = montar();
  documento.getElementById('enHoja').click();
  assert.equal(documento.getElementById('modalAnotar').classList.contains('open'), false);
  terminar();
  assert.equal(scripts()[2].dataset.presetTipo, 'INGRESO');
});

test('otros modales no cargan el panel', () => {
  const { documento, scripts } = montar();
  documento.getElementById('otro').click();
  assert.equal(scripts().length, 0);
});

test('con data-abrir-panel carga al tiro y le pide al panel que se abra', () => {
  const { scripts, terminar, abiertos } = montar({ abrir: true });
  terminar();
  assert.equal(scripts().length, 3);
  assert.equal(scripts()[2].dataset.abrirPanel, '1');
  assert.equal(abiertos.length, 0);
});

test('si otro script abre el panel, igual se carga', () => {
  const { documento, scripts, observar } = montar();
  documento.getElementById('modalGasto').classList.add('open');
  observar();
  assert.equal(scripts().length, 1);
});
