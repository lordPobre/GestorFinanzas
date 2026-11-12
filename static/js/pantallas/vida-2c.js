(() => {
  const numero = (valor) => {
    const n = parseFloat(String(valor || '').replace(',', '.'));
    return Number.isFinite(n) ? n : null;
  };

  document.querySelectorAll('[data-izq-pct]').forEach((el) => {
    const n = numero(el.dataset.izqPct);
    if (n !== null) el.style.left = n + '%';
  });
  document.querySelectorAll('[data-arriba-pct]').forEach((el) => {
    const n = numero(el.dataset.arribaPct);
    if (n !== null) el.style.top = n + '%';
  });

  const cumple = (consulta) => !!(window.matchMedia && window.matchMedia(consulta).matches);
  if (cumple('(prefers-reduced-motion: reduce)') || !cumple('(min-width: 721px)')) return;
  if (typeof document.documentElement.animate !== 'function') return;

  const main = document.querySelector('.f2c-main');
  if (!main) return;

  const suave = 'cubic-bezier(.3, .7, .2, 1)';
  const miles = (n) => String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, '.');

  function contar(el, retraso) {
    const fin = numero(el.dataset.cuenta);
    const final = el.textContent;
    const partes = /^(\D*?)(\d{1,3}(?:\.\d{3})*)(\D*)$/.exec(final.trim());
    if (!fin || fin <= 0 || !partes) return;
    const empieza = performance.now() + retraso;
    el.textContent = partes[1] + '0' + partes[3];
    const paso = (t) => {
      const k = Math.max(0, Math.min(1, (t - empieza) / 900));
      el.textContent = k < 1 ? partes[1] + miles(fin * (1 - Math.pow(1 - k, 3))) + partes[3] : final;
      if (k < 1) requestAnimationFrame(paso);
    };
    requestAnimationFrame(paso);
  }

  function crecer(raiz, retraso) {
    const opciones = (i) => ({ duration: 720, delay: retraso + Math.min(i, 24) * 18, easing: suave, fill: 'backwards' });
    raiz.querySelectorAll('[data-ancho-pct]').forEach((el, i) => {
      el.animate([{ transform: 'scaleX(0)' }, { transform: 'none' }], opciones(i));
    });
    raiz.querySelectorAll('[data-alto-pct]').forEach((el, i) => {
      el.animate([{ transform: 'scaleY(0)' }, { transform: 'none' }], opciones(i));
    });
    raiz.querySelectorAll('[data-traza]').forEach((el) => {
      const largo = typeof el.getTotalLength === 'function' ? el.getTotalLength() : 0;
      if (!largo) return;
      el.style.strokeDasharray = String(largo);
      const a = el.animate([{ strokeDashoffset: largo }, { strokeDashoffset: 0 }],
        { duration: 1200, delay: retraso + 150, easing: suave, fill: 'backwards' });
      a.onfinish = () => { el.style.strokeDasharray = ''; };
    });
    raiz.querySelectorAll('[data-aparece]').forEach((el) => {
      el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 400, delay: retraso + 1150, fill: 'backwards' });
    });
    raiz.querySelectorAll('[data-cuenta]').forEach((el) => contar(el, retraso));
  }

  function entrar(el, orden) {
    const retraso = Math.min(orden, 6) * 70;
    el.style.opacity = '';
    el.animate([{ opacity: 0, transform: 'translateY(14px)' }, { opacity: 1, transform: 'none' }],
      { duration: 480, delay: retraso, easing: suave, fill: 'backwards' });
    crecer(el, retraso + 120);
  }

  const bloques = Array.from(main.querySelectorAll(
    '.i2c-col > *, .f2c-pagina > .v2c-esc, .f2c-pagina > .tu2c-quien, .f2c-col > :not(.me2c-lista), .me2c-lista > *'
  )).filter((el) => el.offsetParent !== null);
  if (!bloques.length) return;

  const enVista = (el) => {
    const r = el.getBoundingClientRect();
    return r.top < window.innerHeight && r.bottom > 0;
  };
  const visibles = bloques.filter(enVista);
  visibles.forEach((el, i) => entrar(el, i));

  if (!('IntersectionObserver' in window)) return;
  const despues = bloques.filter((el) => !visibles.includes(el));
  const observador = new IntersectionObserver((entradas) => {
    entradas.filter((e) => e.isIntersecting).forEach((e, i) => {
      observador.unobserve(e.target);
      entrar(e.target, i);
    });
  }, { rootMargin: '0px 0px -6% 0px' });
  despues.forEach((el) => {
    el.style.opacity = '0';
    observador.observe(el);
  });
})();
