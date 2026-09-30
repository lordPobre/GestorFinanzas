(() => {
  const lista = document.querySelector('.mov-list');
  const seg = document.querySelector('[data-mov-filtros]');
  if (!lista || !seg) return;
  const filas = lista.querySelectorAll('[data-mov-tipo]');
  const resumen = document.querySelector('[data-mov-resumen]');
  const vacio = lista.querySelector('[data-mov-vacio]');
  const nombres = {
    todo: ['movimiento', 'movimientos'],
    unico: ['gasto único', 'gastos únicos'],
    cuota: ['cuota pagada', 'cuotas pagadas'],
    ingreso: ['ingreso', 'ingresos'],
  };
  const plata = (n) => '$' + Math.round(n).toLocaleString('es-CL');

  function aplicar(filtro) {
    if (!nombres[filtro]) filtro = 'todo';
    let n = 0;
    let suma = 0;
    filas.forEach((f) => {
      const ver = filtro === 'todo' || f.dataset.movTipo === filtro;
      f.hidden = !ver;
      if (ver) { n += 1; suma += Number(f.dataset.monto) || 0; }
    });
    seg.querySelectorAll('[data-mov-filtro]').forEach((b) => {
      const on = b.dataset.movFiltro === filtro;
      b.classList.toggle('on', on);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    if (vacio) vacio.hidden = n > 0;
    if (resumen) {
      const [uno, varios] = nombres[filtro];
      resumen.querySelector('span').textContent = n + ' ' + (n === 1 ? uno : varios);
      resumen.querySelector('b').textContent = filtro === 'todo' || !n ? '' : plata(suma);
    }
  }

  seg.addEventListener('click', (e) => {
    const b = e.target.closest('[data-mov-filtro]');
    if (b) aplicar(b.dataset.movFiltro);
  });
  document.addEventListener('click', (e) => {
    const a = e.target.closest('[data-mov-abrir]');
    if (a) aplicar(a.dataset.movAbrir);
  });
  aplicar('todo');
})();
