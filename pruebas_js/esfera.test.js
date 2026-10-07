const test = require('node:test');
const assert = require('node:assert/strict');
const { Nodo, crearDocumento, ejecutar, DatosFormulario, reloj, esperar } = require('./dom_minimo');

function caja(top, alto = 40) {
  return { top, bottom: top + alto, left: 0, right: 400, width: 400, height: alto };
}

function montar({ telefono = true, voz = 'Llevas gastado la mitad', bienvenida = false, hora = 9, scrollY = 0, audio = 'audio/mpeg', rechazar = false, diferido = false } = {}) {
  const documento = crearDocumento(`
<div class="ini-hero">
  <div class="ini-accesos"></div>
  <div data-esfera data-voz-url="/voz/"${voz ? ` data-voz="${voz}"` : ''}${bienvenida ? ' data-bienvenida' : ''}>
    <span data-esfera-hola data-voz="Ana"></span>
    <span data-esfera-cambio data-voz="Gastaste menos que ayer"></span>
    <p data-saludo></p>
    <button type="button" data-esfera-hablar></button>
    <p data-esfera-ayuda><i class="fas fa-hand-pointer"></i><span>Toca la esfera para escucharlo</span></p>
  </div>
</div>
<div data-esfera-hoja><button type="button" data-esfera-asa></button><div data-pestanas></div></div>
<nav class="bottomnav"></nav>
<input type="hidden" name="csrfmiddlewaretoken" value="ficha">`);
  const $ = (selector) => documento.querySelector(selector);
  const raiz = documento.documentElement;
  const bajada = () => Number(raiz.style['--esfera-p'] || 0) * parseFloat(raiz.style['--esfera-d'] || '0');
  $('.ini-hero').rect = caja(100, 400);
  $('.ini-accesos').rect = caja(200);
  $('.bottomnav').rect = caja(780, 60);
  $('[data-esfera-hoja]').getBoundingClientRect = () => caja(300 + bajada(), 500);
  $('[data-pestanas]').getBoundingClientRect = () => caja(300 + bajada(), 40);

  const r = reloj();
  const mq = { matches: telefono, addEventListener() {} };
  const ventana = Object.assign(new Nodo('window'), {
    matchMedia: () => mq,
    scrollY,
    innerHeight: 800,
    scrollTo: (x, y) => { ventana.scrollY = y; },
  });
  const pedidos = [];
  let liberar = null;
  const fetch = (url, opciones) => {
    pedidos.push({ url, opciones });
    const respuesta = { ok: Boolean(audio), headers: { get: () => audio || 'text/html' }, blob: async () => new Blob(['mp3']) };
    if (!diferido) return Promise.resolve(respuesta);
    return new Promise((listo) => { liberar = () => listo(respuesta); });
  };
  ventana.fetch = fetch;
  const audios = [];
  class AudioFalso {
    constructor() { this.paused = true; this.src = ''; this.oyentes = {}; audios.push(this); }
    addEventListener(tipo, funcion) { (this.oyentes[tipo] = this.oyentes[tipo] || []).push(funcion); }
    emitir(tipo) { (this.oyentes[tipo] || []).forEach((f) => f()); }
    play() {
      if (rechazar) return Promise.reject(new Error('NotAllowedError'));
      this.paused = false;
      return Promise.resolve();
    }
    pause() { this.paused = true; this.emitir('pause'); }
  }
  let blobs = 0;
  class FechaFalsa extends Date {
    constructor(...a) {
      if (a.length) super(...a); else super(2026, 9, 7, hora, 30);
    }
  }
  ejecutar('pantallas/inicio-esfera.js', {
    document: documento, window: ventana, fetch, FormData: DatosFormulario, Audio: AudioFalso, Blob, Date: FechaFalsa,
    URL: { createObjectURL: () => `blob:${(blobs += 1)}` },
    performance: { now: () => r.ahora },
    MutationObserver: class { observe() {} },
    setTimeout: r.setTimeout, clearTimeout: r.clearTimeout, requestAnimationFrame: (f) => r.setTimeout(f, 0),
  });
  const ayuda = $('[data-esfera-ayuda]');
  return {
    documento, ventana, mq, pedidos, audios, reloj: r, $, raiz,
    esfera: $('[data-esfera]'),
    asa: $('[data-esfera-asa]'),
    bola: $('[data-esfera-hablar]'),
    ayuda,
    liberar: () => liberar(),
    abierta: () => raiz.classList.contains('esfera-abierta'),
    texto: () => ayuda.querySelector('span').textContent,
    icono: () => ayuda.querySelector('i').className,
    api: ventana.finappEsfera,
    arrastrar(desde, hasta) {
      this.asa.emitir('pointerdown', { clientY: desde, pointerType: 'touch', button: 0 });
      const evento = ventana.emitir('pointermove', { clientY: hasta, cancelable: true });
      ventana.emitir('pointerup');
      return evento;
    },
  };
}

test('al cargar en el teléfono queda cerrada, medida y con el saludo de la hora', () => {
  const e = montar();
  assert.equal(e.abierta(), false);
  assert.equal(e.raiz.style['--esfera-p'], '0.0000');
  assert.equal(e.raiz.style['--esfera-d'], '416px');
  assert.equal(e.esfera.style['--esfera-top'], '94px');
  assert.equal(e.esfera.getAttribute('aria-hidden'), 'true');
  assert.equal(e.bola.tabIndex, -1);
  assert.equal(e.asa.getAttribute('aria-label'), 'Bajar la hoja para ver el resumen');
  assert.equal(e.pedidos.length, 0);
  assert.equal(e.$('[data-saludo]').textContent, 'Buenos días');
  assert.equal(montar({ hora: 15 }).$('[data-saludo]').textContent, 'Buenas tardes');
  assert.equal(montar({ hora: 22 }).$('[data-saludo]').textContent, 'Buenas noches');
});

test('tocar el asa sube al inicio, abre la esfera y pide la voz una sola vez', async () => {
  const e = montar({ scrollY: 120 });
  e.asa.click();
  assert.equal(e.ventana.scrollY, 0);
  assert.equal(e.abierta(), true);
  assert.equal(e.raiz.style['--esfera-p'], '1.0000');
  assert.equal(e.esfera.getAttribute('aria-hidden'), 'false');
  assert.equal(e.bola.tabIndex, 0);
  assert.equal(e.asa.getAttribute('aria-label'), 'Subir la hoja');
  assert.equal(e.pedidos.length, 1);
  const { url, opciones } = e.pedidos[0];
  assert.equal(url, '/voz/');
  assert.equal(opciones.method, 'POST');
  assert.equal(opciones.headers['X-CSRFToken'], 'ficha');
  assert.equal(opciones.body.get('frase'), 'Llevas gastado la mitad');
  assert.equal(opciones.body.has('cambio'), false);
  await esperar();
  e.asa.click();
  assert.equal(e.abierta(), false);
  e.asa.click();
  assert.equal(e.abierta(), true);
  assert.equal(e.pedidos.length, 1);
});

test('en el computador el asa no la abre', () => {
  const e = montar({ telefono: false });
  e.asa.click();
  e.api.abrir();
  assert.equal(e.abierta(), false);
  assert.equal(e.api.disponible(), false);
  assert.equal(e.pedidos.length, 0);
});

test('arrastrar la hoja la abre o la cierra según cuánto se mueva', () => {
  const e = montar();
  e.asa.emitir('pointerdown', { clientY: 100, pointerType: 'touch', button: 0 });
  e.ventana.emitir('pointermove', { clientY: 104, cancelable: true });
  assert.equal(e.raiz.classList.contains('esfera-arrastrando'), false);
  const movida = e.ventana.emitir('pointermove', { clientY: 308, cancelable: true });
  assert.equal(movida.defaultPrevented, true);
  assert.equal(e.raiz.classList.contains('esfera-arrastrando'), true);
  assert.equal(e.raiz.style['--esfera-p'], '0.5000');
  e.ventana.emitir('pointerup');
  assert.equal(e.raiz.classList.contains('esfera-arrastrando'), false);
  assert.equal(e.abierta(), true);
  e.asa.click();
  assert.equal(e.abierta(), true);
  e.reloj.pasar(401);
  e.asa.click();
  assert.equal(e.abierta(), false);

  e.arrastrar(100, 180);
  assert.equal(e.abierta(), false);
  assert.equal(e.raiz.style['--esfera-p'], '0.0000');
  e.api.abrir();
  e.arrastrar(500, 350);
  assert.equal(e.abierta(), false);
});

test('la bola habla con la voz lista y otro toque o el final la callan', async () => {
  const e = montar();
  e.api.abrir();
  await esperar();
  e.bola.click();
  const audio = e.audios[0];
  assert.equal(audio.src, 'blob:1');
  assert.equal(audio.paused, false);
  assert.equal(e.esfera.classList.contains('hablando'), true);
  assert.equal(e.texto(), 'Hablando… toca para detener');
  assert.equal(e.icono(), 'fas fa-volume-high');
  e.bola.click();
  assert.equal(audio.paused, true);
  assert.equal(e.esfera.classList.contains('hablando'), false);
  assert.equal(e.texto(), 'Toca la esfera para escucharlo');
  assert.equal(e.icono(), 'fas fa-hand-pointer');
  e.bola.click();
  audio.emitir('ended');
  assert.equal(e.texto(), 'Toca la esfera para escucharlo');
});

test('si la voz no ha llegado avisa que la prepara y suena al llegar', async () => {
  const e = montar({ diferido: true });
  e.api.abrir();
  e.bola.click();
  assert.equal(e.audios[0].src, 'blob:1');
  assert.equal(e.esfera.classList.contains('cargando'), true);
  assert.equal(e.texto(), 'Preparando la voz…');
  assert.equal(e.icono(), 'fas fa-spinner fa-spin');
  assert.equal(e.pedidos.length, 1);
  e.liberar();
  await esperar();
  assert.equal(e.audios[0].src, 'blob:2');
  assert.equal(e.esfera.classList.contains('cargando'), false);
  assert.equal(e.esfera.classList.contains('hablando'), true);
});

test('sin voz del servidor o con el audio bloqueado avisa y luego vuelve la ayuda', async () => {
  const sinVoz = montar({ audio: null });
  sinVoz.api.abrir();
  await esperar();
  sinVoz.bola.click();
  await esperar();
  assert.equal(sinVoz.pedidos.length, 2);
  assert.equal(sinVoz.texto(), 'La voz no está disponible ahora');
  assert.equal(sinVoz.icono(), 'fas fa-circle-exclamation');
  assert.equal(sinVoz.esfera.classList.contains('cargando'), false);
  sinVoz.reloj.pasar(3600);
  assert.equal(sinVoz.texto(), 'Toca la esfera para escucharlo');

  const bloqueado = montar({ rechazar: true });
  bloqueado.api.abrir();
  await esperar();
  bloqueado.bola.click();
  await esperar();
  assert.equal(bloqueado.texto(), 'Toca de nuevo para escucharlo');
  assert.equal(bloqueado.esfera.classList.contains('hablando'), false);
});

test('sin frase de voz se oculta la ayuda y la bola no hace nada', () => {
  const e = montar({ voz: null });
  assert.equal(e.ayuda.hidden, true);
  e.api.abrir();
  e.bola.click();
  assert.equal(e.pedidos.length, 0);
  assert.equal(e.audios.length, 0);
});

test('la bienvenida abre sola, manda el saludo con el nombre y se quita al cerrar', () => {
  const e = montar({ bienvenida: true });
  assert.equal(e.raiz.classList.contains('esfera-bienvenida'), true);
  e.reloj.pasar(0);
  assert.equal(e.abierta(), true);
  assert.equal(e.esfera.style['--esfera-top'], '233px');
  const datos = e.pedidos[0].opciones.body;
  assert.equal(datos.get('cambio'), 'Gastaste menos que ayer');
  assert.equal(datos.get('saludo'), 'Buenos días');
  assert.equal(datos.get('nombre'), 'Ana');
  e.api.cerrar();
  assert.equal(e.raiz.classList.contains('esfera-bienvenida'), false);
  assert.equal(e.abierta(), false);
});

test('cerrar la hoja corta el audio y pasar al computador la cierra', async () => {
  const e = montar();
  e.api.abrir();
  await esperar();
  e.bola.click();
  e.api.cerrar();
  assert.equal(e.audios[0].paused, true);
  assert.equal(e.esfera.classList.contains('hablando'), false);
  assert.equal(e.abierta(), false);
  e.api.abrir();
  e.mq.matches = false;
  e.ventana.emitir('resize');
  assert.equal(e.abierta(), false);
});
