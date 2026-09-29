(function () {
  function cerrar(excepto) {
    document.querySelectorAll('details.topbar-cuenta[open]').forEach(function (d) {
      if (d !== excepto) d.removeAttribute('open');
    });
  }
  document.addEventListener('click', function (e) {
    cerrar(e.target.closest('details.topbar-cuenta'));
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') cerrar(null);
  });
})();
