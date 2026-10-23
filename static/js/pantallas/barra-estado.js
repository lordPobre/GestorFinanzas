(function () {
  var raiz = document.documentElement;
  var pendiente = false;
  function marcar() {
    pendiente = false;
    raiz.classList.toggle('con-scroll', (window.scrollY || window.pageYOffset || 0) > 4);
  }
  marcar();
  window.addEventListener('scroll', function () {
    if (pendiente) return;
    pendiente = true;
    requestAnimationFrame(marcar);
  }, { passive: true });
})();
