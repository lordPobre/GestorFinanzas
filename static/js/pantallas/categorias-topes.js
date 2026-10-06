(function () {
  var script = document.currentScript;
  var simbolo = (script && script.dataset.simbolo) || '$';
  var modal = document.getElementById('modalTope');
  if (!modal) return;
  var titulo = modal.querySelector('[data-tope-titulo]');
  var sub = modal.querySelector('[data-tope-sub]');
  var campos = modal.querySelectorAll('[data-tope-campo]');
  var input = modal.querySelector('#id_tope_monto');
  var avisar = modal.querySelector('[data-tope-avisar]');
  var sugeridos = modal.querySelector('[data-tope-sugeridos]');
  var quitar = modal.querySelector('[data-tope-quitar]');
  function plata(n) { return simbolo + Math.round(n).toLocaleString('es-CL'); }
  function chip(texto, valor) {
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'chip'; b.textContent = texto;
    b.addEventListener('click', function () { input.value = valor; });
    sugeridos.appendChild(b);
  }
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-tope-cat]');
    if (!b) return;
    var promedio = parseInt(b.dataset.topePromedio || '0', 10) || 0;
    var actual = parseInt(b.dataset.topeMonto || '0', 10) || 0;
    titulo.textContent = 'Tope para ' + b.dataset.topeNombre;
    sub.textContent = promedio > 0 ? 'En los últimos 3 meses gastaste en promedio ' + plata(promedio) + ' al mes.' : 'No hay gastos de esta categoría en los últimos 3 meses.';
    campos.forEach(function (c) { c.value = b.dataset.topeCat; });
    input.value = actual || promedio || '';
    avisar.checked = b.dataset.topeAvisar === '1';
    sugeridos.textContent = '';
    if (promedio > 0) {
      chip('Tu promedio · ' + plata(promedio), promedio);
      chip('10 % menos · ' + plata(promedio * 0.9), Math.round(promedio * 0.9));
    }
    sugeridos.hidden = promedio <= 0;
    quitar.hidden = !actual;
  });
})();
