(() => {
  const llenar = (el) => {
    const min = Number(el.min) || 0;
    const max = Number(el.max) || 0;
    const pct = max > min ? (Number(el.value) - min) / (max - min) * 100 : 0;
    el.style.setProperty('--lleno', Math.max(0, Math.min(100, pct)) + '%');
  };
  document.querySelectorAll('.pl-slider').forEach((el) => {
    llenar(el);
    el.addEventListener('input', () => llenar(el));
  });
  const ahorro = document.getElementById('planAhorro');
  const extra = document.getElementById('planExtra');
  if (ahorro && extra) ahorro.addEventListener('input', () => window.requestAnimationFrame(() => llenar(extra)));

  const raiz = document.querySelector('.pl2c[data-herr]');
  const botones = Array.from(document.querySelectorAll('[data-herr-ir]'));
  if (!raiz || !botones.length) return;
  const CLAVE = 'fintora-plan-herramienta';

  function elegir(nombre) {
    const boton = botones.find((b) => b.dataset.herrIr === nombre) || botones[0];
    raiz.dataset.herr = boton.dataset.herrIr;
    botones.forEach((b) => b.setAttribute('aria-pressed', b === boton ? 'true' : 'false'));
    try { window.sessionStorage.setItem(CLAVE, raiz.dataset.herr); } catch (e) { }
    window.dispatchEvent(new Event('resize'));
  }

  botones.forEach((b) => b.addEventListener('click', () => elegir(b.dataset.herrIr)));

  let guardada = '';
  try { guardada = window.sessionStorage.getItem(CLAVE) || ''; } catch (e) { }
  elegir(guardada || 'sim');
})();
