(function () {
  var VERSION_TOUR = 4;
  var script = (document.currentScript || document.querySelector('script[data-js="tour-arranque"]'));
  if (!script || !script.dataset.src) return;
  var d = script.dataset;
  var nonce = script.nonce || '';
  var rutas = {
    inicio: d.rutaInicio,
    cuotas: d.rutaCuotas,
    suscripciones: d.rutaSuscripciones,
    prestamos: d.rutaPrestamos,
    metas: d.rutaMetas,
    estadisticas: d.rutaEstadisticas,
    analisis: d.rutaAnalisis,
    importar: d.rutaImportar,
    perfil: d.rutaPerfil
  };
  var estado = 'nada';
  var esperando = [];

  function leer(clave) {
    try { return localStorage.getItem(clave); } catch (e) { return null; }
  }

  function cargar(luego) {
    if (estado === 'listo') { if (luego) luego(); return; }
    if (luego) esperando.push(luego);
    if (estado === 'cargando') return;
    estado = 'cargando';
    var s = document.createElement('script');
    s.src = d.src;
    if (nonce) s.nonce = nonce;
    s.onload = function () {
      if (!window.finappTour) return;
      window.finappTour.iniciar({ rutas: rutas });
      estado = 'listo';
      var cola = esperando;
      esperando = [];
      cola.forEach(function (f) { f(); });
    };
    (document.head || document.body).appendChild(s);
  }

  var terminado = leer('finapp.tour.listo') === '1';
  var vista = Number(leer('finapp.tour.version')) || 1;
  var hayQueMostrar = /[?&]tour=1(&|$)/.test(location.search)
    || leer('finapp.tour.modo') === 'novedades'
    || (!terminado && leer('finapp.tour.paso') !== null)
    || (terminado && vista < VERSION_TOUR)
    || !!document.querySelector('[data-paso-tour]');
  if (hayQueMostrar) cargar();

  document.addEventListener('click', function (e) {
    if (estado === 'listo') return;
    var boton = e.target.closest && e.target.closest('[data-tour-iniciar], [data-pasos-ocultar]');
    if (!boton) return;
    e.preventDefault();
    cargar(function () { boton.click(); });
  }, true);
})();
