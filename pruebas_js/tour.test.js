const test = require('node:test');
const assert = require('node:assert/strict');
const { crearDocumento, ejecutar, memoria, reloj } = require('./dom_minimo');

const RUTAS = {
  inicio: '/', importar: '/importar/', cuotas: '/cuotas/', suscripciones: '/suscripciones/',
  prestamos: '/me-deben/', metas: '/metas/', estadisticas: '/estadisticas/', analisis: '/analisis/', perfil: '/perfil/',
};
const PASO = 'finapp.tour.paso';
const LISTO = 'finapp.tour.listo';
const VERSION = 'finapp.tour.version';
const MODO = 'finapp.tour.modo';

function esferaFalsa(disponible = true) {
  const e = {
    abierta_: false,
    cierres: 0,
    disponible: () => disponible,
    abierta: () => e.abierta_,
    abrir: () => { e.abierta_ = true; },
    cerrar: () => { e.abierta_ = false; e.cierres += 1; },
  };
  return e;
}

function montar({ telefono = false, ruta = '/', busqueda = '', guardado = {}, objetivos = ['saldo', 'salud', 'registrar'], esfera } = {}) {
  const documento = crearDocumento(`
${objetivos.map((o) => `<div data-tour="${o}"></div>`).join('')}
<div id="segPerfil"><button type="button" data-panel="seguridad"></button><button type="button" data-panel="datos"></button></div>
<button type="button" data-tour-iniciar></button>
<button type="button" data-pasos-ocultar></button>
<li data-paso-tour></li>`);
  const pestanas = documento.querySelectorAll('#segPerfil [data-panel]');
  pestanas.forEach((b) => b.addEventListener('click', () => {
    pestanas.forEach((x) => x.classList.remove('on'));
    b.classList.add('on');
  }));
  const almacen = memoria(guardado);
  const r = reloj();
  const location = { pathname: ruta, search: busqueda, hash: '', href: ruta + busqueda };
  const direcciones = [];
  const ventana = {
    matchMedia: () => ({ matches: telefono }),
    addEventListener() {},
    scrollTo() {},
    scrollY: 0,
    innerHeight: 800,
    innerWidth: 400,
    history: { replaceState: (estado, titulo, url) => direcciones.push(url) },
    finappEsfera: esfera,
  };
  ejecutar('tour.js', {
    document: documento, window: ventana, location, localStorage: almacen,
    setTimeout: r.setTimeout, clearTimeout: r.clearTimeout, requestAnimationFrame: (f) => r.setTimeout(f, 0),
  });
  ventana.finappTour.iniciar({ rutas: RUTAS });
  const $ = (selector) => documento.querySelector(selector);
  return {
    documento,
    datos: almacen.datos,
    location,
    direcciones,
    reloj: r,
    $,
    abierto: () => Boolean($('.tour-capa') && $('.tour-capa').classList.contains('on')),
    paso: () => $('.tour-eyebrow').textContent,
    titulo: () => $('.tour-titulo').textContent,
    boton: (accion) => $(`[data-tour-accion="${accion}"]`),
    pildora: () => {
      const p = $('.tour-pildora');
      return p && p.classList.contains('on') ? p.querySelector('.tour-pildora-txt').textContent : null;
    },
    tecla: (key) => documento.emitir('keydown', { key }),
  };
}

test('sin tour pendiente o ya terminado no muestra nada', () => {
  for (const guardado of [{}, { [LISTO]: '1', [VERSION]: '4' }]) {
    const t = montar({ guardado });
    assert.equal(t.$('.tour-capa'), null);
    assert.equal(t.pildora(), null);
  }
  assert.equal(montar({ guardado: { [LISTO]: '1', [VERSION]: '4' } }).$('[data-paso-tour]').classList.contains('hecho'), true);
});

test('?tour=1 empieza en el primer paso y limpia la dirección', () => {
  const t = montar({ busqueda: '?tour=1' });
  assert.equal(t.abierto(), true);
  assert.equal(t.paso(), 'Paso 1 de 20');
  assert.equal(t.titulo(), 'Cuánto puedes gastar');
  assert.equal(t.boton('atras'), null);
  assert.equal(t.boton('omitir').textContent, 'Saltar el tour');
  assert.equal(t.boton('siguiente').textContent, 'Siguiente');
  assert.equal(t.documento.querySelectorAll('.tour-punto').length, 20);
  assert.deepEqual(t.direcciones, ['/']);
  assert.equal(t.datos[PASO], '0');
});

test('Siguiente, Atrás y las flechas recorren la pantalla; el paso de otra pantalla navega', () => {
  const t = montar({ busqueda: '?tour=1' });
  t.boton('siguiente').click();
  assert.equal(t.paso(), 'Paso 2 de 20');
  assert.equal(t.titulo(), 'La salud de tu mes');
  assert.equal(t.datos[PASO], '1');
  t.boton('atras').click();
  assert.equal(t.paso(), 'Paso 1 de 20');
  t.tecla('ArrowRight');
  t.tecla('Enter');
  assert.equal(t.titulo(), 'Anotar un gasto o un ingreso');
  t.tecla('ArrowLeft');
  assert.equal(t.paso(), 'Paso 2 de 20');
  t.boton('siguiente').click();
  t.boton('siguiente').click();
  assert.equal(t.location.href, '/importar/');
  assert.equal(t.datos[PASO], '3');
});

test('un paso cuyo elemento no se ve o no está se salta', () => {
  const oculto = montar({ busqueda: '?tour=1' });
  oculto.$('[data-tour="salud"]').offsetParent = null;
  oculto.boton('siguiente').click();
  assert.equal(oculto.paso(), 'Paso 3 de 20');
  const sinElemento = montar({ busqueda: '?tour=1', objetivos: ['saldo', 'registrar'] });
  sinElemento.boton('siguiente').click();
  assert.equal(sinElemento.titulo(), 'Anotar un gasto o un ingreso');
});

test('al volver a la app sigue en el paso guardado o lo ofrece en la píldora', () => {
  const aqui = montar({ ruta: '/importar/', guardado: { [PASO]: '3' }, objetivos: ['cartola'] });
  assert.equal(aqui.paso(), 'Paso 4 de 20');
  assert.equal(aqui.titulo(), 'Subir la cartola del banco');
  const otra = montar({ guardado: { [PASO]: '3' } });
  assert.equal(otra.abierto(), false);
  assert.equal(otra.pildora(), 'Seguir el tour · 4/20');
  otra.$('.tour-pildora').click();
  assert.equal(otra.location.href, '/importar/');
});

test('Escape o tocar el fondo cierran sin terminar y dejan la píldora', () => {
  const t = montar({ busqueda: '?tour=1' });
  t.tecla('Escape');
  assert.equal(t.abierto(), false);
  assert.equal(t.pildora(), 'Seguir el tour · 1/20');
  assert.equal(t.datos[LISTO], undefined);
  t.$('.tour-pildora').click();
  assert.equal(t.abierto(), true);
  t.$('.tour-capa').click();
  assert.equal(t.abierto(), false);
  assert.equal(t.datos[LISTO], undefined);
});

test('Saltar el tour o la X de la píldora lo terminan para siempre', () => {
  const t = montar({ busqueda: '?tour=1' });
  t.boton('omitir').click();
  assert.equal(t.abierto(), false);
  assert.equal(t.datos[LISTO], '1');
  assert.equal(t.datos[VERSION], '4');
  assert.equal(t.datos[PASO], undefined);
  assert.equal(t.$('[data-paso-tour]').classList.contains('hecho'), true);
  assert.equal(t.$('.tour-fin').textContent, 'Listo. Puedes repetir el tour desde tu perfil.');
  t.reloj.pasar(4200);
  assert.equal(t.$('.tour-fin').classList.contains('irse'), true);
  t.reloj.pasar(600);
  assert.equal(t.$('.tour-fin'), null);
  assert.equal(montar({ guardado: { ...t.datos } }).pildora(), null);

  const conPildora = montar({ guardado: { [PASO]: '3' } });
  conPildora.$('[data-tour-cerrar]').click();
  assert.equal(conPildora.datos[LISTO], '1');
  assert.equal(conPildora.pildora(), null);
});

test('el último paso abre su pestaña del perfil y Terminar cierra el tour', () => {
  const t = montar({ ruta: '/perfil/', guardado: { [PASO]: '19' }, objetivos: ['exportar'] });
  assert.equal(t.$('#segPerfil [data-panel="datos"]').classList.contains('on'), true);
  assert.equal(t.paso(), 'Paso 20 de 20');
  assert.equal(t.boton('siguiente').textContent, 'Terminar');
  t.boton('siguiente').click();
  assert.equal(t.abierto(), false);
  assert.equal(t.datos[LISTO], '1');
});

test('quien ya hizo una versión anterior recibe solo lo nuevo', () => {
  const inicio = montar({ guardado: { [LISTO]: '1', [VERSION]: '2' } });
  assert.equal(inicio.pildora(), 'Ver lo nuevo · 6');
  inicio.$('.tour-pildora').click();
  assert.equal(inicio.datos[MODO], 'novedades');
  assert.equal(inicio.datos[PASO], '0');
  assert.equal(inicio.location.href, '/perfil/');

  const perfil = montar({ ruta: '/perfil/', guardado: { ...inicio.datos }, objetivos: ['seguridad'] });
  assert.equal(perfil.paso(), 'Nuevo 1 de 6');
  assert.equal(perfil.titulo(), 'Tu seguridad, en un solo lugar');
  assert.equal(perfil.$('#segPerfil [data-panel="seguridad"]').classList.contains('on'), true);
  assert.equal(perfil.boton('omitir').textContent, 'Ya está');
  perfil.boton('omitir').click();
  assert.equal(perfil.datos[VERSION], '4');
  assert.equal(perfil.datos[MODO], undefined);
  assert.equal(perfil.$('.tour-fin').textContent, 'Eso es todo lo nuevo. El tour completo sigue en tu perfil.');
});

test('en el teléfono abre la esfera para su paso, la cierra al seguir y se la salta si no está', () => {
  const esfera = esferaFalsa();
  const t = montar({ telefono: true, busqueda: '?tour=1', objetivos: ['saldo', 'salud', 'registrar', 'esfera'], esfera });
  t.boton('siguiente').click();
  assert.equal(t.titulo(), 'Anotar un gasto o un ingreso');
  t.boton('siguiente').click();
  assert.equal(esfera.abierta(), true);
  t.reloj.pasar(600);
  assert.equal(t.paso(), 'Paso 3 de 20');
  assert.equal(t.titulo(), 'La esfera de tu mes');
  t.boton('siguiente').click();
  assert.equal(esfera.cierres, 1);
  assert.equal(t.location.href, '/importar/');

  const sinEsfera = montar({ telefono: true, busqueda: '?tour=1', objetivos: ['saldo', 'registrar', 'esfera'], esfera: esferaFalsa(false) });
  sinEsfera.boton('siguiente').click();
  sinEsfera.boton('siguiente').click();
  assert.equal(sinEsfera.abierto(), false);
  assert.equal(sinEsfera.pildora(), 'Seguir el tour · 4/20');
});

test('desde la lista de pasos se repite el tour o se oculta la lista', () => {
  const t = montar({ guardado: { [LISTO]: '1', [VERSION]: '4' } });
  t.$('[data-tour-iniciar]').click();
  assert.equal(t.datos[LISTO], undefined);
  assert.equal(t.paso(), 'Paso 1 de 20');
  t.$('[data-pasos-ocultar]').click();
  assert.equal(t.datos['finapp.pasos.oculto'], '1');
  assert.equal(t.documento.documentElement.classList.contains('pasos-ocultos'), true);
});
