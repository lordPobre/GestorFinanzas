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
})();
