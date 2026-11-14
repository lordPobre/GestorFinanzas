const raiz = document.querySelector('[data-repetidos]');

if (raiz) {
  const casillas = [...raiz.querySelectorAll('.rp2c-check')];
  const simbolo = raiz.dataset.simbolo || '$';
  const formato = new Intl.NumberFormat('es-CL', { maximumFractionDigits: 0 });
  const poner = (selector, texto) => raiz.querySelectorAll(selector).forEach((el) => { el.textContent = texto; });

  const pintar = () => {
    const marcadas = casillas.filter((c) => c.checked);
    const n = marcadas.length;
    const suma = marcadas.reduce((s, c) => s + (Number(c.dataset.monto) || 0), 0);
    poner('[data-rp-n]', `${n} de ${casillas.length}`);
    poner('[data-rp-corto]', n === 1 ? '1 marcada' : `${n} marcadas`);
    poner('[data-rp-total]', `${simbolo}${formato.format(Math.round(suma))}`);
    poner('[data-rp-largo]', n ? `Borrar ${n} repetida${n === 1 ? '' : 's'}` : 'Nada marcado');
    poner('[data-rp-btn-corto]', n ? `Borrar ${n}` : 'Nada marcado');
    raiz.querySelectorAll('[data-rp-btn]').forEach((b) => { b.disabled = n === 0; });
  };

  raiz.addEventListener('change', (e) => {
    if (e.target.matches('.rp2c-check')) pintar();
  });
}
