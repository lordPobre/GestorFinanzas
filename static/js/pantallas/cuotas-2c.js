(() => {
  const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
  const plata = (n) => '$' + Math.round(n).toLocaleString('es-CL');

  const caja = document.querySelector('#modalEditarDeuda');
  if (caja) {
    const form = caja.querySelector('[data-ed-form]');
    const eliminar = caja.querySelector('[data-ed-eliminar]');
    const campo = (k) => caja.querySelector('[data-ed-' + k + ']');
    const pintar = () => {
      const v = Number(campo('cuota').value || 0);
      const n = Number(campo('cuotas').value || 0);
      if (!(v > 0 && n > 0)) {
        campo('total').textContent = '$0';
        campo('fin').textContent = 'Pon la cuota y cuántas son';
        return;
      }
      campo('total').textContent = plata(v * n);
      let texto = n + (n === 1 ? ' cuota' : ' cuotas') + ' de ' + plata(v);
      const inicio = campo('inicio').value;
      if (inicio) {
        const f = new Date(inicio + 'T00:00:00');
        f.setMonth(f.getMonth() + n - 1);
        texto += ' · última en ' + MESES[f.getMonth()] + ' ' + f.getFullYear();
      }
      campo('fin').textContent = texto;
    };
    ['cuota', 'cuotas', 'inicio'].forEach((k) => campo(k).addEventListener('input', pintar));
    document.querySelectorAll('[data-editar-compra]').forEach((b) => b.addEventListener('click', () => {
      const d = b.dataset;
      form.action = d.accion;
      eliminar.action = d.eliminar;
      campo('acreedor').value = d.acreedor || '';
      campo('cuota').value = d.cuota || '';
      campo('cuotas').value = d.cuotas || '';
      campo('inicio').value = d.inicio || '';
      const sel = campo('categoria');
      if (sel && Array.from(sel.options).some((o) => o.value === d.categoria)) sel.value = d.categoria;
      const p = Number(d.pagadas || 0);
      campo('pagadas').textContent = p ? (p === 1 ? 'Llevas 1 cuota pagada.' : 'Llevas ' + p + ' cuotas pagadas.') : 'Todavía no pagas ninguna cuota.';
      pintar();
    }));
  }

  const mm = document.querySelector('[data-mes-a-mes]');
  if (mm) {
    const titulo = mm.querySelector('[data-mm-titulo]');
    const linea = mm.querySelector('[data-mm-linea]');
    const nota = mm.querySelector('[data-mm-nota]');
    const barras = Array.from(mm.querySelectorAll('.c2c-barra'));
    barras.forEach((b) => b.addEventListener('click', () => {
      barras.forEach((x) => {
        x.classList.toggle('on', x === b);
        x.setAttribute('aria-pressed', x === b ? 'true' : 'false');
      });
      if (titulo) titulo.textContent = b.dataset.titulo;
      if (linea) linea.textContent = b.dataset.linea;
      if (nota) nota.textContent = b.dataset.nota;
    }));
  }
})();
