(() => {
  const lista = document.querySelector('.mov-list');
  const seg = document.querySelector('[data-mov-filtros]');
  if (!lista || !seg) return;
  const resumen = document.querySelector('[data-mov-resumen]');
  const vacio = lista.querySelector('[data-mov-vacio]');
  const nombres = {
    todo: ['movimiento', 'movimientos'],
    unico: ['gasto único', 'gastos únicos'],
    cuota: ['cuota pagada', 'cuotas pagadas'],
    ingreso: ['ingreso', 'ingresos'],
  };
  const plata = (n) => '$' + Math.round(n).toLocaleString('es-CL');
  const filas = () => lista.querySelectorAll('[data-mov-tipo]');
  let actual = 'todo';

  function aplicar(filtro) {
    if (!nombres[filtro]) filtro = 'todo';
    actual = filtro;
    let n = 0;
    let suma = 0;
    filas().forEach((f) => {
      const ver = filtro === 'todo' || f.dataset.movTipo === filtro;
      f.hidden = !ver;
      if (ver) { n += 1; suma += Number(f.dataset.monto) || 0; }
    });
    seg.querySelectorAll('[data-mov-filtro]').forEach((b) => {
      const on = b.dataset.movFiltro === filtro;
      b.classList.toggle('on', on);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    lista.querySelectorAll('[data-mov-dia]').forEach((d) => {
      let s = d.nextElementSibling;
      let alguno = false;
      while (s && !s.hasAttribute('data-mov-dia')) {
        if (s.hasAttribute('data-mov-tipo') && !s.hidden) { alguno = true; break; }
        s = s.nextElementSibling;
      }
      d.hidden = !alguno;
    });
    if (vacio) vacio.hidden = n > 0;
    if (resumen) {
      const [uno, varios] = nombres[filtro];
      resumen.querySelector('span').textContent = n + ' ' + (n === 1 ? uno : varios);
      resumen.querySelector('b').textContent = filtro === 'todo' || !n ? '' : plata(suma);
      resumen.hidden = filtro === 'todo';
    }
  }

  function recontar() {
    const cuenta = { todo: 0, unico: 0, cuota: 0, ingreso: 0 };
    let entro = 0;
    let salio = 0;
    filas().forEach((f) => {
      const tipo = f.dataset.movTipo;
      const monto = Number(f.dataset.monto) || 0;
      cuenta.todo += 1;
      if (tipo in cuenta) cuenta[tipo] += 1;
      if (tipo === 'ingreso') entro += monto; else salio += monto;
    });
    seg.querySelectorAll('[data-mov-filtro]').forEach((b) => {
      const cifra = b.querySelector('b');
      if (cifra) cifra.textContent = cuenta[b.dataset.movFiltro] || 0;
    });
    const caja = lista.closest('.modal-box') || document;
    const e = caja.querySelector('[data-mov-entro]');
    const s = caja.querySelector('[data-mov-salio]');
    if (e) e.textContent = plata(entro);
    if (s) s.textContent = plata(salio);
    aplicar(actual);
  }

  seg.addEventListener('click', (e) => {
    const b = e.target.closest('[data-mov-filtro]');
    if (b) aplicar(b.dataset.movFiltro);
  });
  document.addEventListener('click', (e) => {
    const a = e.target.closest('[data-mov-abrir]');
    if (a) aplicar(a.dataset.movAbrir);
  });
  window.finappMovimientos = { recontar };
  aplicar('todo');
})();
