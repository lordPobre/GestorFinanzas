const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { crearDocumento, ejecutar, memoria } = require('./dom_minimo');

function montar({ guardado = {}, buscar = '', html = '' } = {}) {
  const documento = crearDocumento(`<button data-tour-iniciar></button>${html}`,
    { src: '/static/js/tour.js', rutaInicio: '/' });
  const ventana = { addEventListener() {} };
  ejecutar('pantallas/tour-arranque.js', {
    document: documento, window: ventana, localStorage: memoria(guardado), location: { search: buscar },
  });
  return { documento, ventana, scripts: () => documento.querySelectorAll('script') };
}

test('sin nada guardado no carga el tour', () => {
  assert.equal(montar().scripts().length, 0);
});

test('con ?tour=1 carga el tour desde su dirección', () => {
  const scripts = montar({ buscar: '?tour=1' }).scripts();
  assert.equal(scripts.length, 1);
  assert.equal(scripts[0].src, '/static/js/tour.js');
});

test('con un paso a medias lo carga; terminado y al día no', () => {
  assert.equal(montar({ guardado: { 'finapp.tour.paso': '2' } }).scripts().length, 1);
  assert.equal(montar({ guardado: { 'finapp.tour.listo': '1', 'finapp.tour.version': '4' } }).scripts().length, 0);
});

test('quien hizo una versión anterior lo carga para ver lo nuevo', () => {
  assert.equal(montar({ guardado: { 'finapp.tour.listo': '1', 'finapp.tour.version': '3' } }).scripts().length, 1);
  assert.equal(montar({ guardado: { 'finapp.tour.listo': '1', 'finapp.tour.version': '4', 'finapp.tour.modo': 'novedades' } }).scripts().length, 1);
});

test('tocar «Ver el tour» lo carga, lo inicia y repite el toque', () => {
  const { documento, ventana, scripts } = montar();
  const boton = documento.querySelector('[data-tour-iniciar]');
  const evento = boton.click();
  assert.equal(evento.defaultPrevented, true);
  assert.equal(scripts().length, 1);
  boton.click();
  assert.equal(scripts().length, 1);

  const inicios = [];
  let toques = 0;
  ventana.finappTour = {
    iniciar(cfg) {
      inicios.push(cfg);
      boton.addEventListener('click', () => { toques += 1; });
    },
  };
  scripts()[0].onload();
  assert.equal(inicios.length, 1);
  assert.equal(inicios[0].rutas.inicio, '/');
  assert.equal(toques, 2);
});

test('la versión que mira el arranque es la del tour', () => {
  const leer = (archivo) => fs.readFileSync(path.join(__dirname, '..', 'static', 'js', archivo), 'utf8');
  const delTour = leer('tour.js').match(/var VERSION = (\d+);/)[1];
  const delArranque = leer('pantallas/tour-arranque.js').match(/var VERSION_TOUR = (\d+);/)[1];
  assert.equal(delArranque, delTour);
});
