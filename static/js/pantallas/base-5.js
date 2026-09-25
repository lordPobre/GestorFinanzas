(function () {
  var script = document.currentScript;
  if (!window.finappTour || !script) return;
  var d = script.dataset;
  window.finappTour.iniciar({
    rutas: {
      inicio: d.rutaInicio,
      cuotas: d.rutaCuotas,
      suscripciones: d.rutaSuscripciones,
      prestamos: d.rutaPrestamos,
      metas: d.rutaMetas,
      estadisticas: d.rutaEstadisticas,
      analisis: d.rutaAnalisis,
      importar: d.rutaImportar,
      perfil: d.rutaPerfil
    }
  });
})();
