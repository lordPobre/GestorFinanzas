(function () {
  var barra = document.querySelector('[data-pp-filtros]');
  if (!barra) return;
  var vacio = document.querySelector('[data-pp-vacio]');

  function aplicar(filtro) {
    var visibles = 0;
    document.querySelectorAll('[data-pp-tipo]').forEach(function (fila) {
      var ver = filtro === 'todo' || fila.getAttribute('data-pp-tipo') === filtro;
      fila.hidden = !ver;
      if (ver && !fila.classList.contains('pagada')) visibles++;
    });
    document.querySelectorAll('[data-pp-grupo]').forEach(function (grupo) {
      grupo.hidden = !grupo.querySelector('[data-pp-tipo]:not([hidden])');
    });
    barra.querySelectorAll('[data-pp-filtro]').forEach(function (b) {
      var on = b.getAttribute('data-pp-filtro') === filtro;
      b.classList.toggle('on', on);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    if (vacio) vacio.hidden = visibles > 0 || filtro === 'todo';
  }

  barra.addEventListener('click', function (e) {
    var b = e.target.closest('[data-pp-filtro]');
    if (b) aplicar(b.getAttribute('data-pp-filtro'));
  });
})();
