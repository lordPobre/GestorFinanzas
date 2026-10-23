(() => {
  const modal = document.getElementById('modalMovimientos');
  if (!modal) return;
  const nombres = {
    todo: ['movimiento', 'movimientos'],
    unico: ['gasto único', 'gastos únicos'],
    cuota: ['cuota pagada', 'cuotas pagadas'],
    ingreso: ['ingreso', 'ingresos'],
  };
  const plata = (n) => '$' + Math.round(n).toLocaleString('es-CL');
  const lista = () => modal.querySelector('.mov-list');
  const filas = () => {
    const l = lista();
    return l ? l.querySelectorAll('[data-mov-tipo]') : [];
  };
  let actual = 'todo';
  let pedido = null;

  function aplicar(filtro) {
    if (!nombres[filtro]) filtro = 'todo';
    actual = filtro;
    modal.querySelectorAll('[data-mov-filtro]').forEach((b) => {
      const on = b.dataset.movFiltro === filtro;
      b.classList.toggle('on', on);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    const l = lista();
    if (!l) return;
    let n = 0;
    let suma = 0;
    filas().forEach((f) => {
      const ver = filtro === 'todo' || f.dataset.movTipo === filtro;
      f.hidden = !ver;
      if (ver) { n += 1; suma += Number(f.dataset.monto) || 0; }
    });
    l.querySelectorAll('[data-mov-dia]').forEach((d) => {
      let s = d.nextElementSibling;
      let alguno = false;
      while (s && !s.hasAttribute('data-mov-dia')) {
        if (s.hasAttribute('data-mov-tipo') && !s.hidden) { alguno = true; break; }
        s = s.nextElementSibling;
      }
      d.hidden = !alguno;
    });
    const vacio = l.querySelector('[data-mov-vacio]');
    if (vacio) vacio.hidden = n > 0;
    const resumen = modal.querySelector('[data-mov-resumen]');
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
    modal.querySelectorAll('[data-mov-filtro]').forEach((b) => {
      const cifra = b.querySelector('b');
      if (cifra) cifra.textContent = cuenta[b.dataset.movFiltro] || 0;
    });
    const e = modal.querySelector('[data-mov-entro]');
    const s = modal.querySelector('[data-mov-salio]');
    if (e) e.textContent = plata(entro);
    if (s) s.textContent = plata(salio);
    aplicar(actual);
  }

  function avisar(texto) {
    const estado = modal.querySelector('[data-movimientos-estado]');
    if (estado) estado.textContent = texto;
  }

  function cargar() {
    if (pedido || modal.dataset.cargado || !modal.dataset.fragmento) return;
    avisar('Cargando…');
    pedido = fetch(modal.dataset.fragmento, { credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' } })
      .then((r) => {
        if (!r.ok || r.redirected) throw new Error(String(r.status));
        return r.text();
      })
      .then((html) => {
        const tpl = document.createElement('template');
        tpl.innerHTML = html;
        const caja = tpl.content.querySelector('[data-movimientos-caja]');
        const vieja = modal.querySelector('.modal-box');
        if (!caja || !vieja) throw new Error('fragmento');
        vieja.replaceWith(caja);
        modal.dataset.cargado = '1';
        if (window.finappEstilos) window.finappEstilos(caja);
        if (window.finappSwipe) window.finappSwipe(caja);
        aplicar(actual);
        if (modal.classList.contains('open')) {
          const cerrar = caja.querySelector('[data-close]');
          if (cerrar) cerrar.focus();
        }
      })
      .catch(() => {
        avisar('No se pudo cargar. Cierra y vuelve a abrirlo.');
      })
      .then(() => { pedido = null; });
  }

  const abridor = (e) => e.target.closest && e.target.closest('[data-open="#modalMovimientos"]');

  modal.addEventListener('click', (e) => {
    const b = e.target.closest('[data-mov-filtro]');
    if (b) aplicar(b.dataset.movFiltro);
  });
  document.addEventListener('click', (e) => {
    const a = e.target.closest && e.target.closest('[data-mov-abrir]');
    if (a) aplicar(a.dataset.movAbrir);
    if (abridor(e)) cargar();
  });
  document.addEventListener('pointerover', (e) => { if (abridor(e)) cargar(); }, { passive: true });
  document.addEventListener('focusin', (e) => { if (abridor(e)) cargar(); });
  new MutationObserver(() => {
    if (modal.classList.contains('open')) cargar();
  }).observe(modal, { attributes: true, attributeFilter: ['class'] });
  if (modal.classList.contains('open')) cargar();

  window.finappMovimientos = { recontar };
})();
