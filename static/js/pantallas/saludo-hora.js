(function () {
  var SALUDOS = [
    { desde: 6, hasta: 12, texto: 'Buenos días', icono: 'fa-sun', tono: 'dia' },
    { desde: 12, hasta: 20, texto: 'Buenas tardes', icono: 'fa-cloud-sun', tono: 'tarde' }
  ];
  var NOCHE = { texto: 'Buenas noches', icono: 'fa-moon', tono: 'noche' };

  function elegir(h) {
    for (var i = 0; i < SALUDOS.length; i++) {
      if (h >= SALUDOS[i].desde && h < SALUDOS[i].hasta) return SALUDOS[i];
    }
    return NOCHE;
  }

  function cada(selector, funcion) {
    var nodos = document.querySelectorAll(selector);
    for (var i = 0; i < nodos.length; i++) funcion(nodos[i]);
  }

  function pintar() {
    var s = elegir(new Date().getHours());
    cada('[data-saludo]', function (n) { n.textContent = s.texto; });
    cada('[data-saludo-icono]', function (n) { n.className = 'fas ' + s.icono; });
    cada('[data-saludo-caja]', function (n) { n.setAttribute('data-tono', s.tono); });
  }

  pintar();
  document.addEventListener('DOMContentLoaded', pintar);
  window.setInterval(pintar, 60000);
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) pintar();
  });
})();
