const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const CODIGO = fs.readFileSync(
  path.join(__dirname, '..', 'static', 'js', 'pantallas', 'anotar-tope.js'), 'utf8');

class Nodo {
  constructor(etiqueta) {
    this.tagName = etiqueta;
    this.hijos = [];
    this.style = {};
    this.dataset = {};
    this.hidden = false;
    this.className = '';
    this.value = '';
    this.texto = '';
    this.oyentes = {};
  }
  get textContent() { return this.texto + this.hijos.map((h) => h.textContent).join(''); }
  set textContent(valor) { this.texto = String(valor); this.hijos = []; }
  appendChild(hijo) { this.hijos.push(hijo); return hijo; }
  addEventListener(tipo, funcion) { (this.oyentes[tipo] = this.oyentes[tipo] || []).push(funcion); }
  emitir(tipo) { (this.oyentes[tipo] || []).forEach((f) => f({ target: this })); }
}

const TOPES = { Comida: ['Comida y Supermercado', 100000, 30000] };

function montar({ tipo = 'EGRESO', categoria = 'Comida', monto = '', fecha = '2026-10-07' } = {}) {
  const ids = {};
  for (const id of ['avisoTope', 'formRegistro', 'campoTipo', 'campoCategoria', 'campoMonto', 'campoFecha', 'montoView']) {
    ids[id] = new Nodo('div');
  }
  ids.avisoTope.dataset = { topes: JSON.stringify(TOPES), simbolo: '$', mes: '2026-10' };
  ids.avisoTope.hidden = true;
  ids.campoTipo.value = tipo;
  ids.campoCategoria.value = categoria;
  ids.campoMonto.value = monto;
  ids.campoFecha.value = fecha;
  const contexto = {
    document: {
      getElementById: (id) => ids[id] || null,
      createElement: (etiqueta) => new Nodo(etiqueta),
      addEventListener() {},
    },
    MutationObserver: class { observe() {} },
    setTimeout,
  };
  vm.createContext(contexto);
  vm.runInContext(CODIGO, contexto);
  return ids;
}

test('sin monto no muestra nada', () => {
  assert.equal(montar().avisoTope.hidden, true);
});

test('bajo el 80 % no muestra nada', () => {
  assert.equal(montar({ monto: '10000' }).avisoTope.hidden, true);
});

test('al llegar al 80 % avisa en amarillo con lo que queda', () => {
  const caja = montar({ monto: '50000' }).avisoTope;
  assert.equal(caja.hidden, false);
  assert.equal(caja.className, 'anotar-tope amarillo');
  assert.match(caja.textContent, /Con esto llegas al 80 % de tu tope de Comida y Supermercado/);
  assert.match(caja.textContent, /Te quedarían \$20\.000\./);
});

test('al pasarse avisa en coral con el exceso', () => {
  const caja = montar({ monto: '90000' }).avisoTope;
  assert.equal(caja.className, 'anotar-tope rojo');
  assert.match(caja.textContent, /Con esto pasas tu tope de Comida y Supermercado/);
  assert.match(caja.textContent, /Quedarías \$20\.000 por encima\./);
});

test('la barra separa lo que llevas de lo nuevo', () => {
  const caja = montar({ monto: '60000' }).avisoTope;
  const barra = caja.hijos[2];
  assert.equal(barra.className, 'anotar-tope-barra');
  assert.equal(barra.hijos[0].style.width, '30%');
  assert.equal(barra.hijos[1].style.width, '60%');
});

test('un ingreso, otra categoría u otro mes no avisan', () => {
  assert.equal(montar({ tipo: 'INGRESO', monto: '90000' }).avisoTope.hidden, true);
  assert.equal(montar({ categoria: 'Transporte', monto: '90000' }).avisoTope.hidden, true);
  assert.equal(montar({ fecha: '2026-09-30', monto: '90000' }).avisoTope.hidden, true);
});

test('cambiar la fecha al mes del tope vuelve a revisar', () => {
  const ids = montar({ fecha: '2026-09-30', monto: '90000' });
  ids.campoFecha.value = '2026-10-07';
  ids.campoFecha.emitir('change');
  assert.equal(ids.avisoTope.hidden, false);
});
