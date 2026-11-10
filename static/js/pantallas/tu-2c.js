(() => {
  const sub = document.getElementById('mas');
  if (!sub) return;
  const LLAVE = 'tu2c-mas';

  function abrir() {
    sub.classList.add('abierta');
    window.scrollTo(0, 0);
  }

  function cerrar(e) {
    if (e) e.preventDefault();
    sub.classList.remove('abierta');
    if (window.location.hash === '#mas' && window.history && window.history.replaceState) {
      window.history.replaceState(null, '', window.location.pathname + window.location.search);
    }
    window.scrollTo(0, 0);
  }

  document.querySelectorAll('[data-tu2c-abrir]').forEach((a) => a.addEventListener('click', (e) => { e.preventDefault(); abrir(); }));
  document.querySelectorAll('[data-tu2c-volver]').forEach((a) => a.addEventListener('click', cerrar));
  sub.addEventListener('submit', () => { try { window.sessionStorage.setItem(LLAVE, '1'); } catch (err) { return; } });

  let volver = false;
  try {
    volver = window.sessionStorage.getItem(LLAVE) === '1';
    window.sessionStorage.removeItem(LLAVE);
  } catch (err) {
    volver = false;
  }
  if (volver || window.location.hash === '#mas') sub.classList.add('abierta');
})();
