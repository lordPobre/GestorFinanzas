const test = require('node:test');
const assert = require('node:assert/strict');
const { crearDocumento, ejecutar } = require('./dom_minimo');

function montar(html) {
  const documento = crearDocumento(html);
  const ventana = { addEventListener() {} };
  ejecutar('pantallas/estilos.js', { document: documento, window: ventana });
  return { documento, ventana, $: (s) => documento.querySelector(s) };
}

test('los anchos salen del dato, también con coma decimal', () => {
  const { $ } = montar('<span id="a" data-ancho-pct="40"></span><span id="b" data-ancho-pct="12,5"></span><span id="c" data-ancho-pct="nada"></span>');
  assert.equal($('#a').style.width, '40%');
  assert.equal($('#b').style.width, '12.5%');
  assert.equal($('#c').style.width, undefined);
});

test('las cuotas arman sus columnas y un número raro se ignora', () => {
  const { $ } = montar('<div id="p" data-columnas="6"></div><div id="q" data-columnas="0"></div><div id="r" data-columnas="seis"></div>');
  assert.equal($('#p').style.gridTemplateColumns, 'repeat(6, minmax(0, 1fr))');
  assert.equal($('#q').style.gridTemplateColumns, undefined);
  assert.equal($('#r').style.gridTemplateColumns, undefined);
});

test('la meta recibe su porcentaje y su color, y un color raro se ignora', () => {
  const { $ } = montar('<a id="m" data-pct-var="65" data-color-var="#53d258"></a><a id="x" data-pct-var="10" data-color-var="red;background:url(x)"></a>');
  assert.equal($('#m').style['--pct'], '65');
  assert.equal($('#m').style['--color'], '#53d258');
  assert.equal($('#x').style['--color'], undefined);
});

test('el logo de una marca toma su fondo y su tinta', () => {
  const { $ } = montar('<span id="s" class="marca-app" data-fondo="#1ed760" data-tinta="#000000"></span>');
  assert.equal($('#s').style.background, '#1ed760');
  assert.equal($('#s').style.color, '#000000');
});

test('la barra de una encuesta toma su alto, y los colores aceptan var() y rgba()', () => {
  const { $ } = montar('<i id="b" data-alto-pct="41.5%" data-fondo="var(--surface-2)" data-tinta="rgba(83,210,88,.14)"></i><i id="m" data-fondo="url(x)" data-tinta="var(--x);color:red"></i>');
  assert.equal($('#b').style.height, '41.5%');
  assert.equal($('#b').style.background, 'var(--surface-2)');
  assert.equal($('#b').style.color, 'rgba(83,210,88,.14)');
  assert.equal($('#m').style.background, undefined);
  assert.equal($('#m').style.color, undefined);
});

test('un ícono toma solo su color y un color raro se ignora', () => {
  const { $ } = montar('<i id="c" data-color="#53d258"></i><i id="d" data-color="verde"></i>');
  assert.equal($('#c').style.color, '#53d258');
  assert.equal($('#c').style.background, undefined);
  assert.equal($('#d').style.color, undefined);
});

test('el ícono de categoría usa el color con transparencia de fondo', () => {
  const { $ } = montar('<span id="i" data-color-cat="#ffaa2c"></span><span id="j" data-color-cat="naranja"></span>');
  assert.equal($('#i').style.background, '#ffaa2c29');
  assert.equal($('#i').style.color, '#ffaa2c');
  assert.equal($('#j').style.background, undefined);
});

test('no anima al aplicar y deja la función para contenido nuevo', () => {
  const { documento, ventana } = montar('<div id="lista"></div>');
  assert.equal(documento.documentElement.classList.contains('sin-transicion'), false);
  const lista = documento.querySelector('#lista');
  lista.innerHTML = '<span id="n" data-ancho-pct="30"></span>';
  ventana.finappEstilos(lista);
  assert.equal(documento.querySelector('#n').style.width, '30%');
});
