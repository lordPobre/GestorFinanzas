const test = require('node:test');
const assert = require('node:assert/strict');
const { crearDocumento, ejecutar, memoria, reloj } = require('./dom_minimo');

const RUTAS = {
  inicio: '/', importar: '/importar/', cuotas: '/cuotas/', suscripciones: '/suscripciones/',
  prestamos: '/me-deben/', metas: '/metas/', estadisticas: '/estadisticas/', analisis: '/analisis/', perfil: '/perfil/',
};
const PASO = 'finapp.tour.paso';
const INICIO = '<section data-tour="saldo"></section><button type="button" data-tour="salud"></button>'
  + '<button type="button" data-tour="registrar"></button><button type="button" class="i2c-esfera"></button>';
const TU = '<a href="#mas" data-tu2c-abrir></a><section id="mas" data-ver="avisos">'
  + '<button type="button" data-tu2c-ver="seguridad"></button><button type="button" data-tu2c-ver="datos"></button>'
  + '<a href="#" data-tu2c-volver></a><div data-tour="seguridad"></div><a href="#" data-tour="dos-pasos"></a></section>';

function montar({ telefono = false, ruta = '/', busqueda = '', guardado = {}, html = INICIO, oculto = '' } = {}) {
  const documento = crearDocumento(html);
  documento.documentElement.classList.add('f2c');
  if (oculto) documento.querySelector(oculto).offsetParent = null;
  const mas = documento.querySelector('#mas');
  if (mas) {
    documento.querySelector('[data-tu2c-abrir]').addEventListener('click', () => mas.classList.add('abierta'));
    documento.querySelectorAll('[data-tu2c-ver]').forEach((b) => b.addEventListener('click', () => {
      mas.setAttribute('data-ver', b.getAttribute('data-tu2c-ver'));
    }));
  }
  const almacen = memoria(guardado);
  const r = reloj();
  const location = { pathname: ruta, search: busqueda, hash: '', href: ruta + busqueda };
  const ventana = {
    matchMedia: () => ({ matches: telefono }),
    addEventListener() {},
    scrollTo() {},
    scrollY: 0,
    innerHeight: 800,
    innerWidth: 400,
    history: { replaceState() {} },
  };
  ejecutar('tour.js', {
    document: documento, window: ventana, location, localStorage: almacen,
    setTimeout: r.setTimeout, clearTimeout: r.clearTimeout, requestAnimationFrame: (f) => r.setTimeout(f, 0),
  });
  ventana.finappTour.iniciar({ rutas: RUTAS });
  const $ = (selector) => documento.querySelector(selector);
  return {
    location,
    mas,
    paso: () => $('.tour-eyebrow').textContent,
    titulo: () => $('.tour-titulo').textContent,
    texto: () => $('.tour-texto').textContent,
    siguiente: () => $('[data-tour-accion="siguiente"]').click(),
  };
}

test('con el 2c el tour no tiene el paso de deslizar y la esfera es la de Inicio', () => {
  const t = montar({ busqueda: '?tour=1' });
  assert.equal(t.paso(), 'Paso 1 de 19');
  assert.match(t.texto(), /cuánto te toca por día/);
  t.siguiente();
  assert.equal(t.titulo(), 'La salud de tu mes');
  t.siguiente();
  assert.equal(t.titulo(), 'Anotar un gasto o un ingreso');
  t.siguiente();
  assert.equal(t.paso(), 'Paso 4 de 19');
  assert.equal(t.titulo(), 'La esfera de tu mes');
  t.siguiente();
  assert.equal(t.location.href, '/importar/');
});

test('en el teléfono con el 2c Anotar se muestra en la barra de abajo', () => {
  const t = montar({ telefono: true, busqueda: '?tour=1' });
  assert.equal(t.paso(), 'Paso 1 de 19');
  t.siguiente();
  assert.equal(t.titulo(), 'Anotar un gasto o un ingreso');
  t.siguiente();
  assert.equal(t.titulo(), 'La esfera de tu mes');
});

test('en Cuotas del teléfono apunta al botón que se ve y no corta el tour', () => {
  const html = '<div class="c2c-cab"><button type="button" class="c2c-nueva" data-tour="cuotas"></button></div>'
    + '<button type="button" class="c2c-nueva-tel"></button>';
  const t = montar({ telefono: true, ruta: '/cuotas/', guardado: { [PASO]: '5', 'finapp.tour.sigue': '1' }, html, oculto: '[data-tour="cuotas"]' });
  assert.equal(t.paso(), 'Paso 6 de 19');
  assert.equal(t.titulo(), 'Tus compras en cuotas');
});

test('si después de Siguiente el paso no tiene qué mostrar, el tour sigue en la pantalla que viene', () => {
  const t = montar({ telefono: true, ruta: '/cuotas/', guardado: { [PASO]: '5', 'finapp.tour.sigue': '1' }, html: '<p></p>' });
  assert.equal(t.location.href, '/suscripciones/');
});

test('los pasos de Tú abren Privacidad y seguridad en la parte que toca', () => {
  const t = montar({ ruta: '/perfil/', guardado: { [PASO]: '12' }, html: TU });
  assert.equal(t.mas.classList.contains('abierta'), true);
  assert.equal(t.mas.getAttribute('data-ver'), 'seguridad');
  assert.equal(t.paso(), 'Paso 13 de 19');
  assert.equal(t.titulo(), 'Tu seguridad, en un solo lugar');
  t.siguiente();
  assert.equal(t.titulo(), 'Verificación en dos pasos');
});
