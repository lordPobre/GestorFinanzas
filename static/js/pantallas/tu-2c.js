(() => {
  const sub = document.getElementById('mas');
  if (!sub) return;
  const LLAVE = 'tu2c-mas';
  const LLAVE_VER = 'tu2c-ver';
  const botones = Array.from(sub.querySelectorAll('[data-tu2c-ver]'));

  function ver(nombre) {
    if (!botones.some((b) => b.dataset.tu2cVer === nombre)) return;
    sub.dataset.ver = nombre;
    botones.forEach((b) => b.setAttribute('aria-pressed', b.dataset.tu2cVer === nombre ? 'true' : 'false'));
  }

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

  botones.forEach((b) => b.addEventListener('click', () => ver(b.dataset.tu2cVer)));
  document.querySelectorAll('[data-tu2c-abrir]').forEach((a) => a.addEventListener('click', (e) => { e.preventDefault(); abrir(); }));
  document.querySelectorAll('[data-tu2c-volver]').forEach((a) => a.addEventListener('click', cerrar));
  sub.addEventListener('submit', () => {
    try {
      window.sessionStorage.setItem(LLAVE, '1');
      window.sessionStorage.setItem(LLAVE_VER, sub.dataset.ver || '');
    } catch (err) { return; }
  });

  let volver = false;
  let guardada = '';
  try {
    volver = window.sessionStorage.getItem(LLAVE) === '1';
    guardada = window.sessionStorage.getItem(LLAVE_VER) || '';
    window.sessionStorage.removeItem(LLAVE);
    window.sessionStorage.removeItem(LLAVE_VER);
  } catch (err) {
    volver = false;
  }
  ver(!sub.hasAttribute('data-ver-fijo') && guardada ? guardada : sub.dataset.ver);
  if (volver || window.location.hash === '#mas') sub.classList.add('abierta');
})();
