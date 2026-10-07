const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const CODIGO = fs.readFileSync(path.join(__dirname, '..', 'static', 'js', 'sw.js'), 'utf8');
const ORIGEN = 'https://fintora.cl';

function cargar(ventanas = []) {
  const oyentes = {};
  const avisos = [];
  const abiertas = [];
  const self = {
    location: { origin: ORIGEN },
    addEventListener: (tipo, funcion) => { oyentes[tipo] = funcion; },
    registration: {
      showNotification: (titulo, opciones) => { avisos.push({ titulo, opciones }); return Promise.resolve(); },
    },
    clients: {
      matchAll: async () => ventanas,
      openWindow: async (url) => { abiertas.push(url); },
      claim: async () => {},
    },
    skipWaiting: () => {},
  };
  const contexto = { self, URL, caches: {}, fetch: async () => {}, Response: class {}, console };
  vm.createContext(contexto);
  vm.runInContext(CODIGO, contexto);
  return { oyentes, avisos, abiertas };
}

function evento(extra) {
  const esperas = [];
  return { esperas, waitUntil: (promesa) => esperas.push(promesa), ...extra };
}

test('el aviso usa el título, el cuerpo y la etiqueta que manda el servidor', () => {
  const { oyentes, avisos } = cargar();
  oyentes.push(evento({ data: { json: () => ({ titulo: 'Hoy vence Luz', cuerpo: 'Toca para verlo', url: '/', etiqueta: 'cobros-hoy' }) } }));
  assert.equal(avisos.length, 1);
  assert.equal(avisos[0].titulo, 'Hoy vence Luz');
  assert.equal(avisos[0].opciones.body, 'Toca para verlo');
  assert.equal(avisos[0].opciones.tag, 'cobros-hoy');
  assert.equal(avisos[0].opciones.data.url, '/');
});

test('sin datos muestra un aviso genérico de Fintora', () => {
  const { oyentes, avisos } = cargar();
  oyentes.push(evento({ data: null }));
  assert.equal(avisos[0].titulo, 'Fintora');
  assert.equal(avisos[0].opciones.tag, 'fintora');
});

test('si el contenido no es JSON lo muestra como texto', () => {
  const { oyentes, avisos } = cargar();
  oyentes.push(evento({ data: { json: () => { throw new Error('no'); }, text: () => 'hola' } }));
  assert.equal(avisos[0].opciones.body, 'hola');
});

test('tocar un aviso que apunta fuera de Fintora no abre nada', () => {
  const { oyentes, abiertas } = cargar();
  const e = evento({ notification: { close() {}, data: { url: 'https://malo.example/x' } } });
  oyentes.notificationclick(e);
  assert.equal(e.esperas.length, 0);
  assert.deepEqual(abiertas, []);
});

test('sin pestañas abiertas abre una nueva en la dirección del aviso', async () => {
  const { oyentes, abiertas } = cargar();
  const e = evento({ notification: { close() {}, data: { url: '/categorias/' } } });
  oyentes.notificationclick(e);
  await Promise.all(e.esperas);
  assert.deepEqual(abiertas, [`${ORIGEN}/categorias/`]);
});

test('con una pestaña de Fintora abierta la usa', async () => {
  const pestana = {
    url: `${ORIGEN}/`,
    focus: async () => { pestana.enfocada = true; },
    navigate: async (url) => { pestana.destino = url; },
  };
  const { oyentes, abiertas } = cargar([pestana]);
  const e = evento({ notification: { close() {}, data: { url: '/categorias/' } } });
  oyentes.notificationclick(e);
  await Promise.all(e.esperas);
  assert.equal(pestana.enfocada, true);
  assert.equal(pestana.destino, `${ORIGEN}/categorias/`);
  assert.deepEqual(abiertas, []);
});
