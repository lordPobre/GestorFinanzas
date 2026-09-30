(() => {
  const botones = document.querySelectorAll('[data-cifra-btn]');
  const vistas = document.querySelectorAll('[data-cifra-vista]');
  if (!botones.length) return;
  botones.forEach((btn) => {
    btn.addEventListener('click', () => {
      const elegida = btn.dataset.cifraBtn;
      botones.forEach((b) => {
        const on = b === btn;
        b.classList.toggle('activo', on);
        b.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
      vistas.forEach((v) => { v.hidden = v.dataset.cifraVista !== elegida; });
    });
  });
})();
