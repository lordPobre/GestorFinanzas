const test = require('node:test');
const assert = require('node:assert/strict');
const { crearDocumento, ejecutar } = require('./dom_minimo');

const HTML = '<input type="hidden" id="id_tipo_prestamo" value="UNICO">'
  + '<div id="segTipoPrestamo"><button class="on" data-value="UNICO">Pago único</button><button data-value="CUOTAS">En cuotas</button></div>'
  + '<input id="id_monto_prestamo" value="">'
  + '<div id="campoCuotas"><input id="id_cuotas_prestamo" value="3"></div>'
  + '<div id="prestamoPreview"></div>';

function montar() {
  const documento = crearDocumento(HTML);
  ejecutar('pantallas/prestamos.js', { document: documento });
  return (id) => documento.getElementById(id);
}

test('las cuotas parten ocultas y aparecen al elegir En cuotas', () => {
  const $ = montar();
  const [unico, cuotas] = $('segTipoPrestamo').children;
  assert.equal($('campoCuotas').style.display, 'none');
  cuotas.click();
  assert.equal($('campoCuotas').style.display, 'block');
  assert.equal($('id_tipo_prestamo').value, 'CUOTAS');
  assert.equal(cuotas.className, 'on');
  assert.equal(unico.className, '');
});

test('volver a Pago único las oculta y el resumen sigue al monto', () => {
  const $ = montar();
  const [unico, cuotas] = $('segTipoPrestamo').children;
  cuotas.click();
  $('id_monto_prestamo').value = '180000';
  $('id_monto_prestamo').emitir('input');
  assert.match($('prestamoPreview').textContent, /al mes durante 3 meses$/);
  unico.click();
  assert.equal($('campoCuotas').style.display, 'none');
  assert.match($('prestamoPreview').textContent, / de una vez$/);
});
