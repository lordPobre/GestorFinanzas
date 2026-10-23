(function () {
  var script = (document.currentScript || document.querySelector('script[data-js="panel-carga"]'));
  var modal = document.getElementById('modalGasto');
  if (!script || !modal) return;
  var d = script.dataset;
  var nonce = script.nonce || '';
  var hoja = document.getElementById('modalAnotar');
  var estado = 'nada';

  if (hoja) {
    hoja.addEventListener('click', function (e) {
      if (e.target.closest('[data-open]')) hoja.classList.remove('open');
    });
  }

  function poner(src, datos, luego) {
    var s = document.createElement('script');
    s.src = src;
    if (nonce) s.nonce = nonce;
    Object.keys(datos).forEach(function (k) { if (datos[k]) s.dataset[k] = datos[k]; });
    s.onload = luego;
    s.onerror = luego;
    document.body.appendChild(s);
  }

  function cargar(preset, abrir, luego) {
    if (estado !== 'nada') return;
    estado = 'cargando';
    poner(d.anotar, { marcas: d.marcas }, function () {
      poner(d.tope, {}, function () {
        poner(d.panel, { presetTipo: preset || '', abrirPanel: abrir ? '1' : '' }, function () {
          estado = 'listo';
          if (luego) luego();
        });
      });
    });
  }

  document.addEventListener('click', function (e) {
    if (estado === 'listo') return;
    var boton = e.target.closest && e.target.closest('[data-open="#modalGasto"], [data-preset-tipo]');
    if (!boton) return;
    e.preventDefault();
    e.stopPropagation();
    if (hoja && boton.closest('#modalAnotar')) hoja.classList.remove('open');
    cargar(boton.getAttribute('data-preset-tipo'), false, function () {
      if (window.finappOpen) window.finappOpen('#modalGasto');
    });
  }, true);

  if (window.MutationObserver) {
    new window.MutationObserver(function () {
      if (estado === 'nada' && modal.classList.contains('open')) cargar('', false);
    }).observe(modal, { attributes: true, attributeFilter: ['class'] });
  }

  if (d.abrirPanel === '1') cargar('', true);
})();
