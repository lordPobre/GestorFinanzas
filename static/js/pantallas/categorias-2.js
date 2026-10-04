(() => {
  document.querySelectorAll('[data-ct-lista]').forEach((lista) => {
    const filas = [...lista.querySelectorAll('[data-monto]')];
    const total = filas.reduce((suma, f) => suma + (parseFloat(f.dataset.monto) || 0), 0);
    filas.forEach((f) => {
      const pct = total > 0 ? Math.round((parseFloat(f.dataset.monto) || 0) / total * 100) : 0;
      const barra = f.querySelector('[data-ct-barra]');
      const texto = f.querySelector('[data-ct-pct]');
      if (barra) requestAnimationFrame(() => { barra.style.width = pct + '%'; });
      if (texto) texto.textContent = pct + ' %';
    });
  });
})();
