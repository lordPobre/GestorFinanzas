const test = require('node:test');
const assert = require('node:assert/strict');
const { Nodo, crearDocumento, ejecutar, DatosFormulario, esperar } = require('./dom_minimo');

const HTML = `
<div data-lp-chat>
  <button type="button" data-lp-chat-abrir aria-expanded="false"></button>
  <div data-lp-chat-fondo hidden></div>
  <div data-lp-chat-panel hidden>
    <button type="button" data-lp-chat-cerrar></button>
    <div data-lp-chat-cuerpo>
      <div data-lp-sugerencias><button type="button">¿Es gratis?</button><button type="button">¿Guardan mis claves?</button></div>
    </div>
    <form data-lp-chat-form data-url="/ayuda/chat/"><input type="text" name="pregunta"></form>
  </div>
  <input type="hidden" name="csrfmiddlewaretoken" value="ficha">
  <template data-lp-plantilla-form>
    <form class="lp-chat-contacto" data-url="/ayuda/contacto/">
      <input type="email" name="correo" required>
      <textarea name="mensaje" required></textarea>
      <p class="lp-chat-error" hidden></p>
      <button type="submit">Enviar</button>
    </form>
  </template>
</div>`;

function respuesta(estado, cuerpo) {
  return { status: estado, json: async () => cuerpo };
}

function montar(responder = () => respuesta(200, { ok: true, texto: 'Sí, es gratis.' })) {
  const documento = crearDocumento(HTML);
  const pedidos = [];
  const fetch = (url, opciones) => {
    pedidos.push({ url, opciones });
    return new Promise((listo) => { listo(responder(url, opciones, pedidos.length)); });
  };
  const ventana = { matchMedia: () => ({ matches: false }), addEventListener() {} };
  ejecutar('pantallas/landing.js', { document: documento, window: ventana, fetch, FormData: DatosFormulario });
  documento.emitir('DOMContentLoaded');
  const $ = (selector) => documento.querySelector(selector);
  const cuerpo = $('[data-lp-chat-cuerpo]');
  const campo = $('[data-lp-chat-form] input');
  return {
    documento,
    pedidos,
    $,
    cuerpo,
    campo,
    preguntar(texto) {
      campo.value = texto;
      $('[data-lp-chat-form]').emitir('submit');
    },
    burbujas: (quien) => cuerpo.querySelectorAll(`.lp-burbuja-${quien}`).map((b) => b.textContent),
  };
}

test('el botón abre y cierra el chat y mueve el foco', () => {
  const { documento, $, campo } = montar();
  const boton = $('[data-lp-chat-abrir]');
  boton.click();
  assert.equal($('[data-lp-chat-panel]').hidden, false);
  assert.equal($('[data-lp-chat-fondo]').hidden, false);
  assert.equal(boton.getAttribute('aria-expanded'), 'true');
  assert.equal(documento.documentElement.classList.contains('lp-chat-abierto'), true);
  assert.equal(Nodo.enfocado, campo);
  boton.click();
  assert.equal($('[data-lp-chat-panel]').hidden, true);
  assert.equal(boton.getAttribute('aria-expanded'), 'false');
  assert.equal(documento.documentElement.classList.contains('lp-chat-abierto'), false);
  assert.equal(Nodo.enfocado, boton);
});

test('se cierra con la X, con el fondo y con Escape', () => {
  const { documento, $ } = montar();
  const panel = $('[data-lp-chat-panel]');
  for (const cerrar of [
    () => $('[data-lp-chat-cerrar]').click(),
    () => $('[data-lp-chat-fondo]').click(),
    () => documento.emitir('keydown', { key: 'Escape' }),
  ]) {
    $('[data-lp-chat-abrir]').click();
    assert.equal(panel.hidden, false);
    cerrar();
    assert.equal(panel.hidden, true);
  }
});

test('una pregunta va con la ficha CSRF y la respuesta aparece como burbuja', async () => {
  const chat = montar();
  chat.preguntar('  ¿Cuánto cuesta?  ');
  assert.deepEqual(chat.burbujas('yo'), ['¿Cuánto cuesta?']);
  assert.equal(chat.campo.value, '');
  assert.equal(chat.$('[data-lp-sugerencias]'), null);
  assert.ok(chat.cuerpo.querySelector('.lp-escribiendo'));
  const { url, opciones } = chat.pedidos[0];
  assert.equal(url, '/ayuda/chat/');
  assert.equal(opciones.method, 'POST');
  assert.equal(opciones.headers['X-CSRFToken'], 'ficha');
  assert.equal(opciones.headers['X-Requested-With'], 'XMLHttpRequest');
  assert.equal(opciones.headers['Content-Type'], 'application/json');
  assert.equal(opciones.body, JSON.stringify({ mensajes: [{ rol: 'user', texto: '¿Cuánto cuesta?' }] }));
  await esperar();
  assert.equal(chat.cuerpo.querySelector('.lp-escribiendo'), null);
  assert.deepEqual(chat.burbujas('bot'), ['Sí, es gratis.']);
});

test('cada pregunta lleva la conversación, con un máximo de 12 mensajes', async () => {
  const chat = montar((url, opciones, n) => respuesta(200, { ok: true, texto: `Respuesta ${n}` }));
  chat.preguntar('Primera');
  await esperar();
  chat.preguntar('Segunda');
  const segunda = JSON.parse(chat.pedidos[1].opciones.body).mensajes;
  assert.equal(JSON.stringify(segunda), JSON.stringify([
    { rol: 'user', texto: 'Primera' },
    { rol: 'assistant', texto: 'Respuesta 1' },
    { rol: 'user', texto: 'Segunda' },
  ]));
  await esperar();
  for (let i = 3; i <= 7; i += 1) {
    chat.preguntar(`Pregunta ${i}`);
    await esperar();
  }
  const ultima = JSON.parse(chat.pedidos[6].opciones.body).mensajes;
  assert.equal(ultima.length, 12);
  assert.equal(ultima[0].texto, 'Respuesta 1');
  assert.equal(ultima[11].texto, 'Pregunta 7');
});

test('no manda preguntas vacías, corta las largas y espera la respuesta antes de otra', async () => {
  const chat = montar();
  chat.preguntar('   ');
  assert.equal(chat.pedidos.length, 0);
  chat.preguntar('x'.repeat(900));
  assert.equal(JSON.parse(chat.pedidos[0].opciones.body).mensajes[0].texto.length, 600);
  chat.preguntar('Otra');
  assert.equal(chat.pedidos.length, 1);
  await esperar();
  chat.preguntar('Otra');
  assert.equal(chat.pedidos.length, 2);
});

test('tocar una sugerencia la pregunta', () => {
  const chat = montar();
  chat.$('[data-lp-sugerencias] button').click();
  assert.deepEqual(chat.burbujas('yo'), ['¿Es gratis?']);
  assert.equal(chat.pedidos.length, 1);
});

test('sin respuesta ofrece dejar el correo con la pregunta ya escrita', async () => {
  const casos = [
    [() => respuesta(429, {}), 'Llegaste al límite de preguntas por ahora. Déjame tu correo y te respondemos.'],
    [() => respuesta(200, { ok: true, texto: '' }), 'No tengo esa respuesta. Déjame tu correo y alguien del equipo te escribe.'],
    [() => respuesta(500, { ok: false }), 'No pude responder ahora. Déjame tu correo y te escribimos.'],
    [() => { throw new Error('sin red'); }, 'No pude responder ahora. Déjame tu correo y te escribimos.'],
  ];
  for (const [responder, mensaje] of casos) {
    const chat = montar((...a) => (chat.pedidos.length > 1 ? respuesta(200, { ok: true, texto: 'Ok' }) : responder(...a)));
    chat.preguntar('¿Puedo pagar con tarjeta?');
    await esperar();
    assert.equal(chat.cuerpo.querySelector('.lp-escribiendo'), null);
    assert.deepEqual(chat.burbujas('bot'), [mensaje]);
    const form = chat.cuerpo.querySelector('.lp-chat-contacto');
    assert.equal(form.querySelector('textarea').value, '¿Puedo pagar con tarjeta?');
    assert.equal(Nodo.enfocado, form.querySelector('input[type="email"]'));
    chat.preguntar('Otra cosa');
    assert.equal(JSON.parse(chat.pedidos[1].opciones.body).mensajes.length, 1);
  }
});

test('solo queda un formulario de contacto a la vez', async () => {
  const chat = montar(() => respuesta(200, { ok: true, texto: '' }));
  chat.preguntar('Uno');
  await esperar();
  chat.preguntar('Dos');
  await esperar();
  const formularios = chat.cuerpo.querySelectorAll('.lp-chat-contacto');
  assert.equal(formularios.length, 1);
  assert.equal(formularios[0].querySelector('textarea').value, 'Dos');
});

test('el formulario de contacto revisa el correo antes de enviar', async () => {
  const chat = montar(() => respuesta(200, { ok: true, texto: '' }));
  chat.preguntar('Hola');
  await esperar();
  const form = chat.cuerpo.querySelector('.lp-chat-contacto');
  form.querySelector('input[type="email"]').value = 'no-es-correo';
  const evento = form.emitir('submit');
  assert.equal(evento.defaultPrevented, true);
  assert.equal(chat.pedidos.length, 1);
  const error = form.querySelector('.lp-chat-error');
  assert.equal(error.hidden, false);
  assert.equal(error.textContent, 'Revisa el correo y escribe tu pregunta.');
});

test('enviar el contacto avisa a qué correo se responde o muestra el error', async () => {
  let resultado = { ok: true };
  const chat = montar((url) => (url === '/ayuda/contacto/' ? respuesta(200, resultado) : respuesta(200, { ok: true, texto: '' })));
  chat.preguntar('Hola');
  await esperar();
  let form = chat.cuerpo.querySelector('.lp-chat-contacto');
  form.querySelector('input[type="email"]').value = 'ana@correo.cl';
  resultado = { ok: false, msg: 'Escribe un correo válido.' };
  form.emitir('submit');
  assert.equal(form.querySelector('button').disabled, true);
  const { url, opciones } = chat.pedidos[1];
  assert.equal(url, '/ayuda/contacto/');
  assert.equal(opciones.headers['X-CSRFToken'], 'ficha');
  assert.equal(opciones.body.get('correo'), 'ana@correo.cl');
  assert.equal(opciones.body.get('mensaje'), 'Hola');
  await esperar();
  assert.equal(form.querySelector('.lp-chat-error').textContent, 'Escribe un correo válido.');
  assert.equal(form.querySelector('button').disabled, false);
  resultado = { ok: true };
  form.emitir('submit');
  await esperar();
  form = chat.cuerpo.querySelector('.lp-chat-contacto');
  assert.equal(form, null);
  assert.equal(chat.burbujas('bot').at(-1), 'Listo. Te respondemos a ana@correo.cl.');
});
