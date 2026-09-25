document.addEventListener('click', function (e) {
  var chip = e.target.closest('[data-montos] > button');
  if (chip) {
    e.preventDefault();
    var grupo = chip.parentElement;
    var campo = document.querySelector(grupo.dataset.montos);
    grupo.querySelectorAll('button').forEach(function (b) { b.classList.remove('on'); });
    chip.classList.add('on');
    if (campo) { campo.value = chip.dataset.monto; campo.focus(); }
    return;
  }

  var col = e.target.closest('.aporte-col');
  if (col) {
    e.preventDefault();
    var abierta = col.classList.contains('on');
    col.closest('.aportes-chart')
       .querySelectorAll('.aporte-col.on')
       .forEach(function (c) { c.classList.remove('on'); });
    if (!abierta) col.classList.add('on');
    return;
  }

  document.querySelectorAll('.aporte-col.on').forEach(function (c) {
    c.classList.remove('on');
  });
});

(function () {
  if (!('IntersectionObserver' in window)) return;
  var pendientes = document.querySelectorAll('.meta-card');
  if (!pendientes.length) return;

  pendientes.forEach(function (card) {

    card.querySelectorAll('.progress-fill.viva, .aporte-barra')
        .forEach(function (el) { el.style.animationPlayState = 'paused'; });
  });

  var obs = new IntersectionObserver(function (entradas) {
    entradas.forEach(function (en) {
      if (!en.isIntersecting) return;
      en.target.querySelectorAll('.progress-fill.viva, .aporte-barra')
               .forEach(function (el) { el.style.animationPlayState = ''; });
      obs.unobserve(en.target);
    });
  }, { threshold: .25 });

  pendientes.forEach(function (card) { obs.observe(card); });
})();
