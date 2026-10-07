const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const VACIOS = new Set(['input', 'br', 'img', 'meta', 'link', 'hr']);

function camello(nombre) {
  return nombre.replace(/-([a-z])/g, (_, letra) => letra.toUpperCase());
}

class Clases {
  constructor(nodo) { this.nodo = nodo; }
  todas() { return this.nodo.className.split(/\s+/).filter(Boolean); }
  contains(clase) { return this.todas().includes(clase); }
  add(...clases) {
    const lista = this.todas();
    clases.forEach((c) => { if (!lista.includes(c)) lista.push(c); });
    this.nodo.className = lista.join(' ');
  }
  remove(...clases) { this.nodo.className = this.todas().filter((c) => !clases.includes(c)).join(' '); }
  toggle(clase, forzar) {
    const poner = forzar === undefined ? !this.contains(clase) : Boolean(forzar);
    if (poner) this.add(clase); else this.remove(clase);
    return poner;
  }
}

class Nodo {
  constructor(etiqueta = 'div', atributos = {}) {
    this.tagName = etiqueta.toUpperCase();
    this.hijos = [];
    this.padre = null;
    this.atributos = {};
    this.dataset = {};
    this.className = '';
    this.classList = new Clases(this);
    this.style = { setProperty(clave, valor) { this[clave] = valor; } };
    this.hidden = false;
    this.value = '';
    this.texto = '';
    this.oyentes = {};
    this.clientWidth = 600;
    this.offsetWidth = 120;
    this.offsetHeight = 50;
    Object.entries(atributos).forEach(([k, v]) => this.setAttribute(k, v));
  }

  setAttribute(clave, valor) {
    const texto = String(valor);
    if (clave === 'class') this.className = texto;
    else if (clave === 'id') this.id = texto;
    else if (clave === 'hidden') this.hidden = true;
    else if (clave === 'value') this.value = texto;
    if (clave.startsWith('data-')) this.dataset[camello(clave.slice(5))] = texto;
    else this.atributos[clave] = texto;
  }

  getAttribute(clave) {
    if (clave === 'class') return this.className || null;
    if (clave === 'id') return this.id || null;
    if (clave.startsWith('data-')) {
      const valor = this.dataset[camello(clave.slice(5))];
      return valor === undefined ? null : valor;
    }
    return clave in this.atributos ? this.atributos[clave] : null;
  }

  hasAttribute(clave) { return this.getAttribute(clave) !== null; }

  removeAttribute(clave) {
    if (clave.startsWith('data-')) delete this.dataset[camello(clave.slice(5))];
    else delete this.atributos[clave];
  }

  get textContent() { return this.texto + this.hijos.map((h) => h.textContent).join(''); }
  set textContent(valor) { this.texto = String(valor); this.hijos = []; }

  set innerHTML(html) {
    this.texto = '';
    this.hijos = [];
    analizar(html).forEach((h) => this.appendChild(h));
  }

  get children() { return this.hijos; }

  get nextElementSibling() {
    if (!this.padre) return null;
    const hermanos = this.padre.hijos;
    return hermanos[hermanos.indexOf(this) + 1] || null;
  }

  appendChild(hijo) {
    if (hijo.padre) hijo.remove();
    hijo.padre = this;
    this.hijos.push(hijo);
    return hijo;
  }

  remove() {
    if (!this.padre) return;
    this.padre.hijos = this.padre.hijos.filter((h) => h !== this);
    this.padre = null;
  }

  descendientes() { return this.hijos.flatMap((h) => [h, ...h.descendientes()]); }
  querySelectorAll(selector) { return this.descendientes().filter((n) => n.matches(selector)); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  matches(selector) { return selector.split(',').some((s) => coincide(this, s.trim())); }

  closest(selector) {
    let nodo = this;
    while (nodo) {
      if (nodo.matches(selector)) return nodo;
      nodo = nodo.padre;
    }
    return null;
  }

  addEventListener(tipo, funcion) { (this.oyentes[tipo] = this.oyentes[tipo] || []).push(funcion); }

  emitir(tipo, extra = {}) {
    const evento = {
      type: tipo,
      target: this,
      defaultPrevented: false,
      detenido: false,
      preventDefault() { this.defaultPrevented = true; },
      stopPropagation() { this.detenido = true; },
      ...extra,
    };
    let nodo = this;
    while (nodo && !evento.detenido) {
      (nodo.oyentes[tipo] || []).forEach((f) => f.call(nodo, evento));
      nodo = nodo.padre;
    }
    return evento;
  }

  click() { return this.emitir('click'); }
}

function partes(simple) {
  const resultado = { etiqueta: null, id: null, clases: [], atributos: [] };
  simple.replace(/\[([\w-]+)(?:="([^"]*)")?\]/g, (_, clave, valor) => { resultado.atributos.push([clave, valor]); });
  const resto = simple.replace(/\[[^\]]*\]/g, '');
  const etiqueta = resto.match(/^[a-z][a-z0-9]*/i);
  if (etiqueta) resultado.etiqueta = etiqueta[0].toUpperCase();
  resto.replace(/#([\w-]+)/g, (_, valor) => { resultado.id = valor; });
  resto.replace(/\.([\w-]+)/g, (_, valor) => { resultado.clases.push(valor); });
  return resultado;
}

function coincideSimple(nodo, simple) {
  const p = partes(simple);
  if (p.etiqueta && nodo.tagName !== p.etiqueta) return false;
  if (p.id && nodo.id !== p.id) return false;
  if (!p.clases.every((c) => nodo.classList.contains(c))) return false;
  return p.atributos.every(([clave, valor]) => {
    const actual = nodo.getAttribute(clave);
    return actual !== null && (valor === undefined || actual === valor);
  });
}

function coincide(nodo, selector) {
  const tramos = selector.split(/\s+/).filter(Boolean);
  if (!tramos.length || !coincideSimple(nodo, tramos[tramos.length - 1])) return false;
  let i = tramos.length - 2;
  let ancestro = nodo.padre;
  while (i >= 0 && ancestro) {
    if (coincideSimple(ancestro, tramos[i])) i -= 1;
    ancestro = ancestro.padre;
  }
  return i < 0;
}

function analizar(html) {
  const raiz = new Nodo('raiz');
  let actual = raiz;
  const patron = /<\/([a-z0-9]+)\s*>|<([a-z0-9]+)((?:\s+[\w-]+(?:="[^"]*")?)*)\s*\/?>|([^<]+)/gi;
  let m;
  while ((m = patron.exec(html))) {
    if (m[1]) {
      actual = actual.padre || raiz;
    } else if (m[2]) {
      const atributos = {};
      (m[3] || '').replace(/([\w-]+)(?:="([^"]*)")?/g, (_, clave, valor) => {
        atributos[clave] = valor === undefined ? '' : valor;
      });
      const nodo = actual.appendChild(new Nodo(m[2], atributos));
      if (!VACIOS.has(m[2].toLowerCase())) actual = nodo;
    } else if (m[4] && m[4].trim()) {
      actual.texto += m[4].trim();
    }
  }
  return raiz.hijos.slice();
}

function crearDocumento(html, datosScript = {}) {
  const documento = new Nodo('#document');
  documento.body = documento.appendChild(new Nodo('body'));
  documento.body.innerHTML = html;
  documento.getElementById = (id) => documento.descendientes().find((n) => n.id === id) || null;
  documento.createElement = (etiqueta) => new Nodo(etiqueta);
  documento.currentScript = { dataset: datosScript };
  return documento;
}

function memoria(inicial = {}) {
  const datos = { ...inicial };
  return {
    datos,
    getItem: (clave) => (clave in datos ? datos[clave] : null),
    setItem: (clave, valor) => { datos[clave] = String(valor); },
  };
}

function ejecutar(archivo, globales) {
  const codigo = fs.readFileSync(path.join(__dirname, '..', 'static', 'js', archivo), 'utf8');
  const contexto = {
    window: { addEventListener() {} },
    setTimeout,
    clearTimeout,
    requestAnimationFrame: (f) => setTimeout(f, 0),
    cancelAnimationFrame: clearTimeout,
    ...globales,
  };
  vm.createContext(contexto);
  vm.runInContext(codigo, contexto);
  return contexto;
}

module.exports = { Nodo, crearDocumento, ejecutar, memoria };
